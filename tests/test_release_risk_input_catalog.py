"""Step 54.1 -- release risk input catalog."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "release-risk-input-catalog.yaml"

EXPECTED = {
    "sast_result",
    "dependency_scan_result",
    "secret_scan_result",
    "sbom_presence",
    "image_digest_status",
    "image_vulnerability_result",
    "threat_model_status",
    "qa_verification",
    "security_findings",
    "human_acceptance",
    "approval_status",
    "rollback_plan",
    "backup_status",
    "production_identity_status",
    "secret_readiness",
    "runtime_readiness",
}


def _r() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["releaseRisk"]


def test_file_exists_and_parses() -> None:
    assert F.is_file()
    assert _r()


def test_expected_inputs_present() -> None:
    keys = {i["key"] for i in _r()["inputs"]}
    assert EXPECTED <= keys


def test_all_modeled_not_enforced_and_not_gated() -> None:
    r = _r()
    assert r["productionGateIntegrated"] is False
    for i in r["inputs"]:
        assert i["status"] == "modeled_not_enforced"
