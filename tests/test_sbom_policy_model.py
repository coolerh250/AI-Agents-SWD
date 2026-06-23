"""Step 54.1 -- SBOM policy model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "sbom-policy-model.yaml"


def _s() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["sbom"]


def test_file_exists_and_parses() -> None:
    assert F.is_file()
    assert _s()


def test_required_not_configured_not_committed() -> None:
    s = _s()
    assert s["required"] is True
    assert s["configured"] is False
    assert s["productionReady"] is False
    assert s["storage"]["committedToRepo"] is False


def test_formats_and_scopes() -> None:
    s = _s()
    assert {"cyclonedx", "spdx"} <= set(s["formats"])
    assert {"python", "node", "container"} <= set(s["scopes"])


def test_no_sbom_generated_placeholder_only() -> None:
    s = _s()
    assert s["placeholderSchema"]["components"] == []
