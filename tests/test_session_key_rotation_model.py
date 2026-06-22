"""Step 52.3 -- session key rotation model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "identity" / "session-key-rotation-model.yaml"


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_required_model_only() -> None:
    kr = _d()["sessionKeyRotation"]
    assert kr["required"] is True
    assert kr["status"] == "model_only"
    assert kr["keyIdsRequired"] is True
    assert kr["multipleActiveVerificationKeysRequired"] is True


def test_production_secret_store_required() -> None:
    kr = _d()["sessionKeyRotation"]
    assert kr["productionSecretStoreRequired"] is True
    assert _d()["dependencies"]["productionSecretStore"] == "53"


def test_current_key_not_production_ready_and_not_committed() -> None:
    c = _d()["constraints"]
    assert c["currentKeyProductionReady"] is False
    assert c["keyFileCommitted"] is False


def test_rotation_and_emergency_not_implemented() -> None:
    kr = _d()["sessionKeyRotation"]
    assert kr["rotationWithoutMassLogout"]["implemented"] is False
    assert kr["emergencyRotation"]["implemented"] is False
