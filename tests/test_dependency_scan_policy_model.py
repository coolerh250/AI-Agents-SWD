"""Step 54.1 -- dependency scan policy model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "dependency-scan-policy-model.yaml"


def _d() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["dependencyScan"]


def test_file_exists_and_parses() -> None:
    assert F.is_file()
    assert _d()


def test_required_not_configured_not_production_ready() -> None:
    d = _d()
    assert d["required"] is True
    assert d["configured"] is False
    assert d["productionReady"] is False


def test_lockfile_status_recorded() -> None:
    d = _d()
    assert d["lockfileRequired"] is True
    assert d["lockfileStatus"]["python"]["present"] is False
    assert d["lockfileStatus"]["node"]["present"] is True


def test_python_lockfile_blocker_listed() -> None:
    assert "python_lockfile_missing" in _d()["blockers"]
