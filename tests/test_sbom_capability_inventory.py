"""Step 54.3 -- SBOM capability inventory."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "sbom-capability-inventory.yaml"


def _tools() -> list:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {}).get("sbomTools", [])


def test_file_and_bundled_baseline() -> None:
    assert F.is_file()
    tools = _tools()
    assert any(t["installed"] and t["localOnly"] for t in tools)


def test_custom_installed_external_honest() -> None:
    for t in _tools():
        if t["key"].startswith("custom_"):
            assert t["installed"] is True
        else:
            assert t["installed"] is False


def test_no_upload_or_production_ready() -> None:
    data = yaml.safe_load(F.read_text(encoding="utf-8")) or {}
    assert data["externalUploadEnabled"] is False
    for t in _tools():
        assert t["sourceUpload"] is False
        assert t["productionReady"] is False
