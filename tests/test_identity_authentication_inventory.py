"""Step 52.1 -- authentication inventory."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "authentication-inventory.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_modes_present() -> None:
    keys = {m["key"] for m in _d()["authenticationModes"]}
    assert {"test_local_signed_session", "oidc", "disabled"} <= keys


def test_test_local_non_production() -> None:
    m = next(m for m in _d()["authenticationModes"] if m["key"] == "test_local_signed_session")
    assert m["productionAllowed"] is False
    assert m["environmentEligibility"]["production"] == "forbidden"
    assert m["environmentEligibility"]["staging"] == "forbidden"


def test_production_auth_and_oidc_disabled() -> None:
    d = _d()
    assert d["meta"]["productionAuthEnabled"] is False
    assert d["meta"]["oidcConfigured"] is False


def test_behaviors_safe() -> None:
    b = _d()["behaviors"]
    assert b["cookieHttpOnly"] is True
    assert b["cookieSameSite"] == "strict"
    assert b["frontendLocalStorageToken"] is False
    assert b["urlToken"] is False
    assert b["productionAuthFailClosed"] is True
    assert b["anonymousBlocked"] is True


def test_not_production_ready() -> None:
    assert _d()["productionReadiness"]["status"] == "not_production_ready"
