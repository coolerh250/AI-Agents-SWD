"""Step 54.4 -- integrated security /operations/safety fields (SDK level)."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.security_integrated import integrated_safety_fields

ROOT = Path(__file__).resolve().parents[1]

EXPECT_TRUE = [
    "security_threat_model_present",
    "security_agent_threat_model_present",
    "security_supply_chain_threat_model_present",
    "security_runtime_gitops_threat_model_present",
    "security_release_risk_summary_model_present",
    "security_release_risk_summary_generated",
    "security_evidence_package_schema_present",
    "security_evidence_package_generated",
    "security_readiness_report_generated",
    "security_missing_evidence_blocks_production",
    "security_critical_finding_blocks_production",
    "security_step54_integrated",
]
EXPECT_FALSE = [
    "security_release_gate_enabled",
    "security_step54_production_ready",
]


def _f() -> dict:
    return integrated_safety_fields(ROOT)


def test_all_fields_present() -> None:
    f = _f()
    for k in EXPECT_TRUE + EXPECT_FALSE:
        assert k in f, f"missing {k}"


def test_expected_true() -> None:
    f = _f()
    for k in EXPECT_TRUE:
        assert f[k] is True, f"{k} should be True"


def test_expected_false() -> None:
    f = _f()
    for k in EXPECT_FALSE:
        assert f[k] is False, f"{k} should be False"
