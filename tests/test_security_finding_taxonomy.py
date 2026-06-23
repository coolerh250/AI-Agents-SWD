"""Step 54.1 -- security finding severity taxonomy."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "security-finding-taxonomy.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8")) or {}


def test_file_exists_and_parses() -> None:
    assert F.is_file()
    assert _d().get("severities")


def test_all_severities_defined() -> None:
    keys = {s["key"] for s in _d()["severities"]}
    assert {"critical", "high", "medium", "low", "informational"} <= keys


def test_critical_is_production_blocker() -> None:
    crit = next(s for s in _d()["severities"] if s["key"] == "critical")
    assert crit["gateBehavior"] == "fail"
    assert crit["productionBlocker"] is True


def test_special_classifications_critical() -> None:
    specials = {s["condition"]: s for s in _d()["specialClassifications"]}
    for cond in ("secret_leak", "production_credential_leak", "unauthenticated_deploy_path"):
        assert specials[cond]["severity"] == "critical"
