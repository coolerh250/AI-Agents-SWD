"""Step 60 -- release governance runtime (SDK end-to-end, no DB)."""

from __future__ import annotations

from shared.sdk.release_governance import (
    build_audit_metadata,
    build_candidate,
    build_intent,
)
from shared.sdk.release_governance.audit import EVENTS


def test_candidate_then_intent_flow() -> None:
    cand = build_candidate(project_id="p", version_label="v1")
    assert cand.target_environment == "nonprod"
    intent = build_intent(
        release_candidate_id=cand.release_candidate_id, requested_action="validate_only"
    )
    assert intent.status == "validated"
    assert intent.to_dict()["production_executed"] is False


def test_audit_metadata_redacted_and_no_production() -> None:
    meta = build_audit_metadata(
        event_type="release_candidate_created",
        actor="tester",
        role="operator",
        reason="r",
        candidate_id="c",
        target_environment="nonprod",
        policy_decision="created_nonproduction",
        extra={"token": "should-be-dropped"},
    )
    assert meta["event_type"] in EVENTS
    assert meta["production_executed"] is False
    assert meta["token"] == "[redacted]"


def test_blocked_intent_records_reason() -> None:
    intent = build_intent(release_candidate_id="c", requested_action="deploy_production")
    assert intent.status == "blocked"
    assert intent.policy_decision == "blocked"
