"""Step 62 -- operator review package."""

from __future__ import annotations

from shared.sdk.production_readiness import build_operator_review_package


def _pkg(**overrides):
    base = dict(
        readiness_decision={"decision": "ready_for_operator_review"},
        evidence_inventory=[{"name": "x", "production_scope": False}],
        blocking_results=[{"name": "r", "severity": "prerequisite", "active": True}],
        missing_prerequisites=["production_cluster_identified"],
        known_limitations=["nonproduction only"],
    )
    base.update(overrides)
    return build_operator_review_package(**base)


def test_not_approval_not_ready() -> None:
    pkg = _pkg()
    assert pkg["production_ready"] is False
    assert pkg["production_approval"] is False
    assert pkg["production_action_allowed"] is False


def test_blocking_status_explicit() -> None:
    pkg = _pkg()
    pb = pkg["production_action_blocking_status"]
    assert pb["production_deploy_blocked"] is True
    assert pb["production_failover_blocked"] is True


def test_no_token_propagation() -> None:
    # A stray token in the decision dict must not surface in the summary (only known keys
    # are copied) and forbidden keys are redacted.
    pkg = _pkg(readiness_decision={"decision": "ready_for_operator_review", "token": "abc"})
    assert pkg["readiness_summary"].get("decision") == "ready_for_operator_review"
    assert "token" not in pkg["readiness_summary"]
