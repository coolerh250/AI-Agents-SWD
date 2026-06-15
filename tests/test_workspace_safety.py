"""Stage 47 -- workspace operator safety: flags + precondition refusals."""

from __future__ import annotations

from workspace_operator_fakes import FakeWorkspaceStore, setup_reviewed_project

from shared.sdk.workspace_operator import WorkspaceExecutionRequest, run_workspace_execution
from shared.sdk.workspace_operator.runner import check_preconditions
from shared.sdk.workspace_operator.safety import workspace_safety_flags


def test_default_flags_are_controlled_only(monkeypatch) -> None:
    for var in (
        "ENABLE_WORKSPACE_OPERATOR_REAL_LLM",
        "ENABLE_WORKSPACE_OPERATOR_GITHUB_WRITE",
        "ENABLE_WORKSPACE_OPERATOR_REPO_WRITE",
        "ENABLE_WORKSPACE_OPERATOR_DEPLOY",
    ):
        monkeypatch.delenv(var, raising=False)
    flags = workspace_safety_flags()
    assert flags["workspace_operator_controlled_only"] is True
    assert flags["workspace_operator_real_llm_enabled"] is False
    assert flags["workspace_operator_github_write_enabled"] is False
    assert flags["workspace_operator_repo_write_enabled"] is False
    assert flags["workspace_operator_deploy_enabled"] is False


async def test_refuses_invalid_graph(tmp_path, monkeypatch) -> None:
    root = tmp_path / "aiagents-workspaces"
    root.mkdir()
    monkeypatch.setenv("WORKSPACE_OPERATOR_ALLOWED_ROOTS", str(root))
    project_id, project_store, review_store = await setup_reviewed_project(
        graph_validation_status="invalid"
    )
    result = await run_workspace_execution(
        request=WorkspaceExecutionRequest(project_id=project_id),
        project_store=project_store,
        review_store=review_store,
        workspace_store=FakeWorkspaceStore(),
        base_root=str(root),
        emit_events=False,
    )
    assert result.status == "failed"
    assert result.blocked_reason == "project_graph_invalid"
    assert result.workspace_id is None


async def test_refuses_missing_review() -> None:
    from project_planning_fakes import FakeProjectStore

    from design_review_fakes import populate_project_store

    project_store = FakeProjectStore()
    project_id = await populate_project_store(project_store)

    class _EmptyReview:
        async def get_latest_review(self, pid):
            return None

        async def list_findings(self, rid):
            return []

        async def list_gates(self, pid):
            return []

    ok, reason, _ctx = await check_preconditions(
        project_id=project_id, project_store=project_store, review_store=_EmptyReview()
    )
    assert ok is False
    assert reason == "design_review_missing"


async def test_refuses_blocking_findings() -> None:
    from project_planning_fakes import FakeProjectStore

    from design_review_fakes import populate_project_store

    project_store = FakeProjectStore()
    project_id = await populate_project_store(project_store)

    class _BlockingReview:
        async def get_latest_review(self, pid):
            return {"id": "r1", "decision": "planning_only"}

        async def list_findings(self, rid):
            return [{"severity": "critical", "status": "open"}]

        async def list_gates(self, pid):
            return []

    ok, reason, _ctx = await check_preconditions(
        project_id=project_id, project_store=project_store, review_store=_BlockingReview()
    )
    assert ok is False
    assert reason in ("blocking_findings_present", "critical_findings_present")
