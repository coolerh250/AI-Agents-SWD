"""Step 54.1 -- threat model input catalog."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "threat-model-input-catalog.yaml"


def _t() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["threatModel"]


def test_file_exists_and_parses() -> None:
    assert F.is_file()
    assert _t()


def test_required_not_configured() -> None:
    t = _t()
    assert t["required"] is True
    assert t["configured"] is False
    assert t["requiredBeforeProductionGate"] is True


def test_core_assets_covered() -> None:
    assets = set(_t()["assets"])
    for a in (
        "admin_console",
        "identity_oidc",
        "secret_management",
        "runtime_operations",
        "gitops",
        "backup_restore",
        "llm_integration",
    ):
        assert a in assets


def test_trust_boundaries_and_entrypoints() -> None:
    t = _t()
    assert t["trustBoundaries"]
    assert t["entrypoints"]
