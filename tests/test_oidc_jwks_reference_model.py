"""Step 52.2 -- JWKS reference model: no fetch, alg=none forbidden."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "jwks-reference-model.yaml"


def _j() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))["jwks"]


def test_no_fetch_no_cache() -> None:
    j = _j()
    assert j["fetchEnabled"] is False
    assert j["cacheEnabled"] is False
    assert j["uriConfigured"] is False
    assert j["status"] == "disabled_unconfigured"


def test_algorithms() -> None:
    j = _j()
    assert "RS256" in j["allowedAlgorithms"]
    assert "none" in j["disallowedAlgorithms"]
    assert "HS256" in j["disallowedAlgorithms"]


def test_key_rotation_required_not_configured() -> None:
    j = _j()
    assert j["keyRotation"]["required"] is True
    assert j["keyRotation"]["configured"] is False
