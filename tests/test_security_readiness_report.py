"""Step 54.4 -- security readiness report generator."""

from __future__ import annotations

from scripts.generate_security_readiness_report import build_security_readiness_report


def test_not_production_ready_gate_disabled() -> None:
    rep = build_security_readiness_report()
    assert rep["productionReady"] is False
    assert rep["releaseGateEnabled"] is False


def test_blockers_and_limitations_listed() -> None:
    rep = build_security_readiness_report()
    assert rep["productionBlockers"]
    assert rep["nonProductionLimitations"]


def test_next_steps_reference_step_55_and_56() -> None:
    nxt = build_security_readiness_report()["nextRequiredSteps"]
    assert "step_55_non_production_cluster_smoke" in nxt
    assert "step_56_real_argocd_manual_sync" in nxt


def test_release_risk_status_not_production() -> None:
    rep = build_security_readiness_report()
    assert rep["releaseRiskStatus"] not in ("production_ready", "production_approved")
