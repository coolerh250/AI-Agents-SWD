"""Step 53 -- secret rotation model."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "secrets" / "secret-rotation-model.yaml"
REQUIRED = {
    "session_signing_key",
    "audit_hmac_keyring",
    "oidc_client_secret",
    "database_credential",
    "redis_credential",
    "backup_encryption_key",
    "github_credential",
    "argocd_repo_credential",
    "registry_credential",
    "llm_api_key",
    "notification_webhook",
}


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_model_only_store_required() -> None:
    r = _d()["rotation"]
    assert r["required"] is True
    assert r["productionStoreRequired"] is True
    assert r["status"] == "model_only"


def test_emergency_rotation_approval_required() -> None:
    er = _d()["rotation"]["emergencyRotation"]
    assert er["required"] is True
    assert er["approvalRequired"] is True


def test_all_critical_secrets_covered() -> None:
    covered = {p["secretKey"] for p in _d()["secretRotationPlans"]}
    assert REQUIRED <= covered


def test_each_plan_records_store_dependency() -> None:
    for p in _d()["secretRotationPlans"]:
        assert p["productionStoreRequired"] is True
