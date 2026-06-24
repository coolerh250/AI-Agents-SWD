"""Step 54.3 -- SBOM / container security /operations/safety fields (SDK level)."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.container_security import container_safety_fields

ROOT = Path(__file__).resolve().parents[1]

EXPECT_TRUE = [
    "security_sbom_baseline_enabled",
    "security_sbom_generation_local_only",
    "security_container_image_inventory_present",
    "security_image_digest_policy_defined",
    "security_dockerfile_security_inventory_present",
    "security_container_runtime_alignment_present",
    "security_image_policy_scan_enabled",
    "security_image_policy_findings_present",
]
EXPECT_FALSE = [
    "security_sbom_external_upload_enabled",
    "security_sbom_runtime_reports_committed",
    "security_sbom_production_ready",
    "security_image_digest_pinning_complete",
    "security_latest_tag_detected",
    "security_dockerfile_non_root_complete",
    "security_image_vulnerability_cve_scan_performed",
    "security_image_signing_configured",
    "security_image_attestation_configured",
    "security_registry_login_enabled",
    "security_image_push_enabled",
    "security_container_production_ready",
]


def _f() -> dict:
    return container_safety_fields(ROOT)


def test_true_fields() -> None:
    f = _f()
    for k in EXPECT_TRUE:
        assert f[k] is True, k


def test_false_fields() -> None:
    f = _f()
    for k in EXPECT_FALSE:
        assert f[k] is False, k


def test_vulnerability_scan_limited_policy_baseline() -> None:
    assert _f()["security_image_vulnerability_scan_configured"] == "limited_policy_baseline"


def test_does_not_emit_production_executed_count() -> None:
    assert "production_executed_true_count" not in _f()
