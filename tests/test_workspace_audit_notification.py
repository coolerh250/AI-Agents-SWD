"""Stage 47 -- workspace audit decision types + notification denylist."""

from __future__ import annotations

from workspace_operator_fakes import FakeWorkspaceStore, setup_reviewed_project

from shared.sdk.notifications.real_delivery_policy import (
    DEFAULT_REAL_DELIVERY_DENYLIST,
    _matches_pattern,
)
from shared.sdk.workspace_operator import WorkspaceExecutionRequest, run_workspace_execution
from shared.sdk.workspace_operator.audit_events import WORKSPACE_DECISION_TYPES
from shared.sdk.workspace_operator.events import WORKSPACE_NOTIFICATION_EVENTS


def test_workspace_events_default_denied() -> None:
    for event in WORKSPACE_NOTIFICATION_EVENTS:
        assert any(_matches_pattern(event, p) for p in DEFAULT_REAL_DELIVERY_DENYLIST), event


def test_codegen_events_default_denied() -> None:
    assert any(_matches_pattern("codegen.file_written", p) for p in DEFAULT_REAL_DELIVERY_DENYLIST)


def test_expected_decision_types_present() -> None:
    assert "workspace_execution_started" in WORKSPACE_DECISION_TYPES
    assert "workspace_execution_completed" in WORKSPACE_DECISION_TYPES
    assert "workspace_execution_failed" in WORKSPACE_DECISION_TYPES
    assert "workspace_files_generated" in WORKSPACE_DECISION_TYPES


async def test_audit_events_emitted(tmp_path, monkeypatch) -> None:
    root = tmp_path / "aiagents-workspaces"
    root.mkdir()
    monkeypatch.setenv("WORKSPACE_OPERATOR_ALLOWED_ROOTS", str(root))
    recorded: list[str] = []

    async def _capture(**kwargs):
        recorded.append(kwargs.get("decision_type"))

    async def _noop(*a, **k):
        return None

    monkeypatch.setattr("shared.sdk.audit.publisher.publish_audit_event", _capture)
    monkeypatch.setattr("shared.sdk.notifications.client.send_notification", _noop)

    project_id, project_store, review_store = await setup_reviewed_project()
    await run_workspace_execution(
        request=WorkspaceExecutionRequest(project_id=project_id),
        project_store=project_store,
        review_store=review_store,
        workspace_store=FakeWorkspaceStore(),
        base_root=str(root),
        emit_events=True,
    )
    assert "workspace_execution_started" in recorded
    assert "workspace_created" in recorded
    assert "workspace_files_generated" in recorded
    assert "workspace_execution_completed" in recorded
