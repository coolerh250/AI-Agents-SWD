"""Stage 45 -- project audit decision types + notification denylist."""

from __future__ import annotations

from shared.sdk.notifications.real_delivery_policy import (
    DEFAULT_REAL_DELIVERY_DENYLIST,
    RealDeliveryPolicy,
    classify_real_delivery,
    load_policy_from_env,
)
from shared.sdk.project_planning.audit_events import (
    STAGE_45_DECISION_TYPES,
    safe_project_artifact_refs,
)
from shared.sdk.project_planning.events import PROJECT_NOTIFICATION_EVENTS


def test_decision_types_present() -> None:
    for expected in (
        "project_planning_started",
        "project_brief_created",
        "project_task_graph_created",
        "project_task_graph_validated",
        "project_work_item_assigned",
        "project_planning_completed",
        "project_planning_failed",
        "project_delivery_readiness_evaluated",
    ):
        assert expected in STAGE_45_DECISION_TYPES


def test_project_namespace_in_denylist() -> None:
    assert "project.*" in DEFAULT_REAL_DELIVERY_DENYLIST


def test_project_events_default_denied_real_mode() -> None:
    # Even with real mode forced on, project.* must be blocked.
    policy = RealDeliveryPolicy(
        real_mode_enabled=True,
        allowlist=[],
        denylist=list(DEFAULT_REAL_DELIVERY_DENYLIST),
        test_channel_id="123",
    )
    for event in PROJECT_NOTIFICATION_EVENTS:
        decision = classify_real_delivery(
            {"event_type": event, "production_executed": False}, policy
        )
        assert decision.decision == "real_blocked"
        assert decision.external_sent is False


def test_loaded_policy_blocks_project_events() -> None:
    policy = load_policy_from_env({}, real_mode_enabled=True)
    decision = classify_real_delivery({"event_type": "project.planning_completed"}, policy)
    assert decision.external_sent is False


def test_artifact_refs_carry_no_secret_and_production_false() -> None:
    refs = safe_project_artifact_refs(
        project_id="p1", graph_snapshot_id="g1", work_items_count=9, template="fastapi_todo_service"
    )
    assert refs["production_executed"] is False
    assert refs["planning_only"] is True
    blob = str(refs).upper()
    assert "TOKEN" not in blob and "API_KEY" not in blob
