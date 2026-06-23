"""Step 54.2 -- scan target catalog."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "scan-target-catalog.yaml"


def _t() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["targets"]


def test_includes_defined() -> None:
    t = _t()
    assert t["secretScan"]["include"]
    assert t["sast"]["include"]


def test_excludes_noise_dirs() -> None:
    exc = set(_t()["secretScan"]["exclude"])
    assert {".git", ".venv", "node_modules"} <= exc


def test_production_code_not_excluded() -> None:
    exc = set(_t()["secretScan"]["exclude"])
    assert not ({"apps", "agents", "shared", "infra"} & exc)


def test_package_files_present() -> None:
    pkg = set(_t()["dependencyScan"]["packageFiles"])
    assert {"requirements.txt", "package.json", "package-lock.json"} <= pkg
