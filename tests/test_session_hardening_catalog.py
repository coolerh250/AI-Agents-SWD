"""Step 52.3 -- session hardening catalog."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "session-hardening-catalog.yaml"


def _h() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))["sessionHardening"]


def test_cookie_hardened() -> None:
    c = _h()["cookie"]
    assert c["httpOnly"] is True
    assert c["sameSite"] == "Strict"
    assert c["secureRequiredInProduction"] is True


def test_raw_token_not_persisted() -> None:
    p = _h()["persistence"]
    assert p["rawTokenPersisted"] is False
    assert p["tokenHashAlgorithm"] == "sha256"
    assert p["serverSideSession"] is True


def test_cleanup_required() -> None:
    assert _h()["cleanup"]["required"] is True
    assert _h()["cleanup"]["expiredSessionPurgeRequired"] is True


def test_key_rotation_model_only_requires_secret_store() -> None:
    kr = _h()["keyRotation"]
    assert kr["required"] is True
    assert kr["implemented"] == "model_only"
    assert kr["productionSecretStoreRequired"] is True


def test_not_production_ready() -> None:
    s = yaml.safe_load(F.read_text(encoding="utf-8"))["status"]
    assert s["productionReady"] is False
