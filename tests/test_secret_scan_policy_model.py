"""Step 54.1 -- secret scan policy model (ties to Step 53)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "security" / "secret-scan-policy-model.yaml"


def _s() -> dict:
    return (yaml.safe_load(F.read_text(encoding="utf-8")) or {})["secretScan"]


def test_file_exists_and_parses() -> None:
    assert F.is_file()
    assert _s()


def test_required_not_configured() -> None:
    s = _s()
    assert s["required"] is True
    assert s["configured"] is False
    assert s["productionReady"] is False


def test_confirmed_secret_fails() -> None:
    assert _s()["failPolicy"]["anyConfirmedSecret"] == "fail"


def test_ties_to_step53_controls() -> None:
    s = _s()
    assert "step53NoInlineSecretVerifier" in s["existingControls"]
    assert "step53RedactionPolicy" in s["existingControls"]
