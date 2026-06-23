"""Step 54.1 -- SAST policy model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "sast-policy-model.yaml"


def _s() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["sast"]


def test_file_exists_and_parses() -> None:
    assert F.is_file()
    assert _s()


def test_required_but_not_configured() -> None:
    s = _s()
    assert s["required"] is True
    assert s["configured"] is False
    assert s["productionReady"] is False


def test_ruff_black_mypy_not_sast() -> None:
    s = _s()
    for tool in ("ruff", "black", "mypy"):
        assert tool in s["notSast"]
        assert tool not in s["toolchain"]["allowedTools"]


def test_scan_scope_covers_code() -> None:
    assert {"apps", "agents", "shared", "scripts"} <= set(_s()["scanScope"])
