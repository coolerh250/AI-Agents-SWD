"""Step 60 -- release readiness evaluation (production always blocked)."""

from __future__ import annotations

from shared.sdk.release_governance import evaluate


def test_production_target_blocked_by_policy() -> None:
    r = evaluate(target_environment="production")
    assert r.decision == "blocked_by_policy"
    assert r.production_ready is False


def test_missing_evidence_blocks() -> None:
    r = evaluate(target_environment="nonprod")
    assert r.decision == "blocked_by_missing_evidence"
    assert r.production_ready is False
    assert r.missing_evidence


def test_complete_reaches_operator_review_not_production() -> None:
    r = evaluate(
        target_environment="nonprod",
        evidence={"security_readiness": "pass", "rollback_plan": {"o": 1}, "audit_events": ["e"]},
        rollback_present=True,
        security_status="pass",
        runtime_status="healthy",
        gitops_status="healthy",
        sandbox_pr_reviewed=True,
    )
    assert r.decision == "ready_for_operator_review"
    assert r.production_ready is False
