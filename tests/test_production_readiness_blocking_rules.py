"""Step 62 -- production readiness blocking rules."""

from __future__ import annotations

from shared.sdk.production_readiness import blocking_rules


def test_hard_guards_inactive_by_default() -> None:
    res = blocking_rules.evaluate()
    hard_active = [r.name for r in res if r.severity == "hard" and r.active]
    assert hard_active == []


def test_prerequisite_caps_active() -> None:
    res = blocking_rules.evaluate()
    prereq_active = [r.name for r in res if r.severity == "prerequisite" and r.active]
    assert "tenant_isolation_not_implemented" in prereq_active
    assert "runtime_nonproduction_only" in prereq_active
    assert len(prereq_active) >= 5


def test_production_action_activates_hard_guard() -> None:
    res = blocking_rules.evaluate(production_action_requested=True)
    assert any(r.name == "production_action_requested" and r.active for r in res)


def test_production_executed_nonzero_activates_hard_guard() -> None:
    res = blocking_rules.evaluate(production_executed_true_count=3)
    assert any(r.name == "production_executed_true_count_nonzero" and r.active for r in res)


def test_missing_marker_activates_evidence_blocker() -> None:
    res = blocking_rules.evaluate(marker_status={"IDENTITY_FOUNDATION_BASELINE_VERIFY": "FAIL"})
    assert any(r.name == "missing_identity_evidence" and r.active for r in res)
