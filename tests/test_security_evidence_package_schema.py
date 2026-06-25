"""Step 54.4 -- security evidence package schema."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "infra" / "security"


def _schema() -> dict:
    data = (
        yaml.safe_load((SEC / "security-evidence-package-schema.yaml").read_text(encoding="utf-8"))
        or {}
    )
    return data["securityEvidencePackageSchema"]


def test_not_production_ready_no_committed_runtime() -> None:
    s = _schema()
    assert s["productionReady"] is False
    assert s["committedRuntimePackageAllowed"] is False


def test_evidence_fields_present() -> None:
    fields = _schema()["fields"]["evidence"]
    for key in (
        "sast",
        "dependencyScan",
        "secretScan",
        "sbom",
        "imagePolicy",
        "dockerfileSecurity",
        "threatModel",
        "releaseRisk",
        "audit",
        "qa",
    ):
        assert key in fields


def test_redaction_rules_enforced() -> None:
    red = _schema()["redaction"]
    assert red["noSecret"] is True
    assert red["noRawToken"] is True
    assert red["noChainOfThought"] is True
    assert red["referencesOnly"] is True


def test_evidence_status_enum_has_no_clean() -> None:
    enum = set(_schema()["evidenceStatusEnum"])
    assert "missing_evidence" in enum
    assert "not_run" in enum
    assert "clean" not in enum
