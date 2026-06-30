"""Step 62 -- production readiness decision."""

from __future__ import annotations

from shared.sdk.production_readiness import blocking_rules, decision, prerequisites


def test_max_decision_is_operator_review() -> None:
    res = blocking_rules.evaluate()
    d = decision.evaluate(
        blocking_results=res, missing_prerequisites=prerequisites.missing_prerequisites()
    )
    assert d.decision == "ready_for_operator_review"
    dd = d.to_dict()
    assert dd["production_ready"] is False
    assert dd["production_approved"] is False
    assert dd["production_action_allowed"] is False


def test_production_action_blocked_by_policy() -> None:
    res = blocking_rules.evaluate(production_action_requested=True)
    assert decision.evaluate(blocking_results=res).decision == "blocked_by_policy"


def test_production_executed_blocked_by_policy() -> None:
    res = blocking_rules.evaluate(production_executed_true_count=1)
    assert decision.evaluate(blocking_results=res).decision == "blocked_by_policy"


def test_missing_evidence_blocks() -> None:
    res = blocking_rules.evaluate(
        marker_status={"BACKUP_RESTORE_DR_OPERATIONS_BASELINE_VERIFY": "FAIL"}
    )
    assert decision.evaluate(blocking_results=res).decision == "blocked_by_missing_evidence"
