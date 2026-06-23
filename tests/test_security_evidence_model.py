"""Step 54.1 -- security evidence model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "security-evidence-model.yaml"

REQUIRED = {
    "sast_report",
    "dependency_scan_report",
    "secret_scan_report",
    "sbom",
    "image_digest_report",
    "image_vulnerability_report",
    "threat_model",
    "release_risk_summary",
    "qa_report",
    "audit_evidence",
}


def _e() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["securityEvidence"]


def test_file_exists_and_parses() -> None:
    assert F.is_file()
    assert _e()


def test_required_evidence_types() -> None:
    keys = {e["key"] for e in _e()["evidenceTypes"]}
    assert REQUIRED <= keys


def test_no_secret_value_allowed_and_fields() -> None:
    e = _e()
    assert e["noSecretValueAllowed"] is True
    assert {"hash", "path", "generatedAt", "tool", "scope", "status"} <= set(
        e["requiredEvidenceFields"]
    )


def test_delivery_package_referenceable() -> None:
    assert _e()["deliveryPackageReferenceable"] is True
