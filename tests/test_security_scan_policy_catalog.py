"""Step 54.1 -- security scan policy catalog."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "security-scan-policy-catalog.yaml"

EXPECTED = {
    "sast_required_before_pr",
    "dependency_scan_required_before_release",
    "secret_scan_required_before_pr",
    "sbom_required_before_deployment",
    "image_digest_required_before_cluster_smoke",
    "image_vulnerability_policy_required_before_runtime",
    "threat_model_required_before_production_gate",
    "release_risk_summary_required_before_deployment_request",
}


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8")) or {}


def test_file_exists_and_parses() -> None:
    assert F.is_file()
    assert _d().get("policies")


def test_expected_policies_present() -> None:
    keys = {p["key"] for p in _d()["policies"]}
    assert EXPECTED <= keys


def test_all_modeled_not_enforced() -> None:
    for p in _d()["policies"]:
        assert p["status"] == "modeled_not_enforced"


def test_no_production_enforcement_claim() -> None:
    d = _d()
    assert d["productionEnforced"] is False
    assert d["nonProductionVerificationBlocked"] is False
