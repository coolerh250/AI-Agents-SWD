"""Stage 48 -- mini delivery audit decision types + notification denylist."""

from __future__ import annotations


from shared.sdk.mini_delivery_pilot.audit_events import MINI_DELIVERY_DECISION_TYPES
from shared.sdk.mini_delivery_pilot.events import DELIVERY_PILOT_NOTIFICATION_EVENTS
from shared.sdk.notifications.real_delivery_policy import (
    DEFAULT_REAL_DELIVERY_DENYLIST,
    _matches_pattern,
)


def test_delivery_pilot_events_default_denied() -> None:
    for event in DELIVERY_PILOT_NOTIFICATION_EVENTS:
        assert any(_matches_pattern(event, p) for p in DEFAULT_REAL_DELIVERY_DENYLIST), event


def test_acceptance_and_qa_evidence_denied() -> None:
    for event in ("acceptance.criteria_satisfied", "qa_evidence.report_ready"):
        assert any(_matches_pattern(event, p) for p in DEFAULT_REAL_DELIVERY_DENYLIST)


def test_expected_decision_types_present() -> None:
    assert "mini_delivery_pilot_started" in MINI_DELIVERY_DECISION_TYPES
    assert "mini_delivery_pilot_completed" in MINI_DELIVERY_DECISION_TYPES
    assert "mini_delivery_acceptance_evaluated" in MINI_DELIVERY_DECISION_TYPES


async def test_audit_events_emitted(tmp_path, monkeypatch) -> None:
    recorded: list[str] = []

    async def _capture(**kwargs):
        recorded.append(kwargs.get("decision_type"))

    async def _noop(*a, **k):
        return None

    monkeypatch.setattr("shared.sdk.audit.publisher.publish_audit_event", _capture)
    monkeypatch.setattr("shared.sdk.notifications.client.send_notification", _noop)

    # run with emit_events=True via the agent path is heavy; emit via runner directly.
    from design_review_fakes import FakeDesignReviewStore, FakeDiscussionStore
    from project_planning_fakes import FakeProjectStore
    from workspace_operator_fakes import FakeWorkspaceStore

    from shared.sdk.mini_delivery_pilot import MiniDeliveryPilotRequest, run_mini_delivery_pilot

    root = tmp_path / "aiagents-workspaces"
    root.mkdir()
    monkeypatch.setenv("WORKSPACE_OPERATOR_ALLOWED_ROOTS", str(root))
    await run_mini_delivery_pilot(
        request=MiniDeliveryPilotRequest(),
        project_store=FakeProjectStore(),
        discussion_store=FakeDiscussionStore(),
        review_store=FakeDesignReviewStore(),
        workspace_store=FakeWorkspaceStore(),
        pilot_store=__import__("mini_delivery_fakes").FakeMiniDeliveryPilotStore(),
        workspace_base_root=str(root),
        emit_events=True,
    )
    assert "mini_delivery_pilot_started" in recorded
    assert "mini_delivery_pilot_completed" in recorded
    assert "mini_delivery_acceptance_evaluated" in recorded
