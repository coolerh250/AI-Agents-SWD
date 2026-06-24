"""Step 54.3 -- container security baseline is never production-ready; baselines preserved."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.sdk.container_security import container_safety_fields, readiness_view

ROOT = Path(__file__).resolve().parents[1]


def test_safety_and_readiness_not_production_ready() -> None:
    f = container_safety_fields(ROOT)
    assert f["security_container_production_ready"] is False
    assert f["security_sbom_production_ready"] is False
    r = readiness_view(ROOT)
    assert r["productionReady"] is False
    assert r["productionGateEnabled"] is False
    assert r["blockers"]


def test_no_unsafe_image_supply_chain_flags() -> None:
    f = container_safety_fields(ROOT)
    for k in (
        "security_registry_login_enabled",
        "security_image_push_enabled",
        "security_image_signing_configured",
        "security_image_attestation_configured",
        "security_sbom_external_upload_enabled",
        "security_image_vulnerability_cve_scan_performed",
    ):
        assert f[k] is False, k


def test_prior_stage_artifacts_preserved() -> None:
    for p in (
        "infra/security/security-foundation-summary.yaml",
        "infra/security/security-scan-status-summary-model.yaml",
        "infra/kubernetes/runtime-baseline-summary.yaml",
        "infra/identity/identity-posture-summary.yaml",
        "infra/secrets/secret-foundation-summary.yaml",
    ):
        assert (ROOT / p).is_file(), p
    sec = yaml.safe_load(
        (ROOT / "infra" / "security" / "security-foundation-summary.yaml").read_text("utf-8")
    )
    assert sec["securityFoundation"]["productionReady"] is False
