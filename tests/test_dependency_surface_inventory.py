"""Step 54.1 -- dependency surface inventory."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "dependency-surface-inventory.yaml"


def _d() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["dependencySurface"]


def test_file_exists_and_parses() -> None:
    assert F.is_file()
    assert _d()


def test_python_and_node_surfaces() -> None:
    d = _d()
    assert d["python"]["runtimeDependencies"]
    assert d["python"]["lockfileMissing"] is True
    assert d["node"]["lockfileMissing"] is False


def test_base_images_and_system_packages() -> None:
    d = _d()
    assert d["dockerBaseImages"]
    assert any("psql" in p.get("providesTools", []) for p in d["systemPackages"])


def test_unknowns_not_assumed_safe() -> None:
    d = _d()
    assert d["unknowns"]
    assert d["lockfileGaps"]
