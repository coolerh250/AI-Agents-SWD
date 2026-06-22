"""Step 52.1 -- identity risk register."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "identity-risk-register.yaml"

REQUIRED = {
    "test_local_auth_not_production_grade",
    "production_oidc_disabled",
    "production_secret_store_absent",
    "group_to_role_mapping_absent",
    "platform_admin_naming_confusion",
    "no_production_approval_identity_chain",
}


def _risks() -> list[dict]:
    return yaml.safe_load(F.read_text(encoding="utf-8"))["risks"]


def test_required_risks_present() -> None:
    keys = {r["key"] for r in _risks()}
    assert REQUIRED <= keys


def test_each_risk_has_severity_and_followup() -> None:
    for r in _risks():
        assert r.get("severity")
        assert r.get("followUpStep")
        assert r.get("currentState")
