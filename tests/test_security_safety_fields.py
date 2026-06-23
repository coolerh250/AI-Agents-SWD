"""Step 54.1 -- security & supply chain /operations/safety fields (SDK level)."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.security_foundation import (
    load_security_foundation_summary,
    security_safety_fields,
)

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "infra" / "security" / "security-foundation-summary.yaml"

EXPECT_TRUE = [
    "security_foundation_enabled",
    "security_image_digest_policy_defined",
    "security_image_vulnerability_policy_defined",
    "security_threat_model_required",
    "security_release_risk_summary_required",
    "security_evidence_model_defined",
    "security_finding_taxonomy_defined",
    "security_gate_fail_closed_policy_defined",
    "supply_chain_inventory_present",
]
EXPECT_FALSE = [
    "security_sast_configured",
    "security_dependency_scan_configured",
    "security_secret_scan_configured",
    "security_sbom_configured",
    "security_production_ready",
    "supply_chain_github_write_enabled",
    "supply_chain_pr_creation_enabled",
    "supply_chain_image_push_enabled",
    "supply_chain_registry_login_enabled",
    "supply_chain_external_scanner_upload_enabled",
]


def _fields() -> dict:
    return security_safety_fields(load_security_foundation_summary(SUMMARY))


def test_status_modeled_not_enforced() -> None:
    assert _fields()["security_foundation_status"] == "modeled_not_enforced"


def test_true_fields() -> None:
    f = _fields()
    for k in EXPECT_TRUE:
        assert f[k] is True, k


def test_false_fields() -> None:
    f = _fields()
    for k in EXPECT_FALSE:
        assert f[k] is False, k


def test_does_not_emit_production_executed_count() -> None:
    # owned by the DB-based production-safety summary, not this spread
    assert "production_executed_true_count" not in _fields()


def test_absent_summary_is_unknown_not_fake_pass() -> None:
    f = security_safety_fields(None)
    assert f["security_foundation_status"] == "unknown"
    assert f["security_production_ready"] is False
