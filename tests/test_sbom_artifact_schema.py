"""Step 54.3 -- SBOM artifact schema."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "sbom-artifact-schema.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8")) or {}


def test_schema_present() -> None:
    d = _d()
    assert "sbomArtifact" in d
    assert d["sbomArtifact"]["productionReady"] is False


def test_supported_formats() -> None:
    assert "internal-manifest-baseline" in _d()["supportedFormats"]


def test_invariants() -> None:
    inv = _d()["invariants"]
    assert "runtime_sbom_not_committed" in inv
    assert "no_secret_value" in inv
    assert "production_ready_always_false" in inv
