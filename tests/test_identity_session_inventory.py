"""Step 52.1 -- session inventory."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "session-inventory.yaml"


def _s() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))["sessions"]


def test_raw_token_not_persisted() -> None:
    ss = _s()["serverSide"]
    assert ss["rawTokenPersisted"] is False
    assert ss["tokenHashPersisted"] is True


def test_cookie_flags() -> None:
    c = _s()["cookie"]
    assert c["httpOnly"] is True
    assert c["sameSite"] == "strict"
    assert c["secureConfigurable"] is True


def test_signing_secret_not_committed() -> None:
    sig = _s()["signing"]
    assert sig["secretCommitted"] is False
    assert sig["productionSecretStore"] == "not_configured"


def test_confirmation_nonce_hashed() -> None:
    assert _s()["confirmationNonce"]["hashedAtRest"] is True
    assert _s()["confirmationNonce"]["rawPersisted"] is False


def test_not_production_ready() -> None:
    assert _s()["productionReadiness"]["status"] == "not_production_ready"
