"""Step 54.2 -- local scanner capability inventory."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "local-scanner-capability-inventory.yaml"


def _scanners() -> list:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {}).get("scanners", [])


def test_file_exists_and_categories() -> None:
    assert F.is_file()
    cats = {s["category"] for s in _scanners()}
    assert {"secret", "sast", "dependency"} <= cats


def test_bundled_are_local_and_tokenfree() -> None:
    for s in _scanners():
        if s.get("installed"):
            assert s["localOnly"] is True, s["key"]
            assert s["tokenRequired"] is False, s["key"]


def test_custom_installed_external_honest() -> None:
    for s in _scanners():
        if s["key"].startswith("custom_"):
            assert s["installed"] is True, s["key"]
        else:
            assert s["installed"] is False, s["key"]


def test_no_source_upload_or_production_ready() -> None:
    for s in _scanners():
        assert s["sourceUpload"] is False
        assert s["productionReady"] is False
