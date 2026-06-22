"""Step 52.2 -- OIDC state / nonce / PKCE contract: required, not implemented."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "oidc-state-nonce-pkce-contract.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_state_required_no_raw_persist() -> None:
    s = _d()["state"]
    assert s["required"] is True
    assert s["singleUse"] is True
    assert s["boundToSession"] is True
    assert s["rawPersistenceAllowed"] is False


def test_nonce_required_no_raw_persist() -> None:
    n = _d()["nonce"]
    assert n["required"] is True
    assert n["singleUse"] is True
    assert n["rawPersistenceAllowed"] is False


def test_pkce_s256_only() -> None:
    p = _d()["pkce"]
    assert p["required"] is True
    assert p["method"] == "S256"
    assert p["plainAllowed"] is False


def test_not_implemented() -> None:
    st = _d()["status"]
    assert st["implemented"] is False
    assert st["requiredBeforeOidcEnablement"] is True
