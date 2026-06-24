"""Step 54.3 -- container security evidence model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "container-security-evidence-model.yaml"

REQUIRED = {
    "local_sbom_baseline",
    "image_inventory_report",
    "image_digest_status",
    "dockerfile_security_inventory",
    "runtime_security_alignment",
    "image_policy_report",
    "image_vulnerability_scan_report_future",
    "signing_attestation_future",
}


def _e() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["containerSecurityEvidence"]


def test_evidence_types() -> None:
    keys = {e["key"] for e in _e()["evidenceTypes"]}
    assert REQUIRED <= keys


def test_no_secret_runtime_not_committed() -> None:
    e = _e()
    assert e["noSecretValueAllowed"] is True
    assert e["runtimeReportsCommitted"] is False
    assert e["releaseRiskReferenceable"] is True
    assert e["productionReady"] is False
