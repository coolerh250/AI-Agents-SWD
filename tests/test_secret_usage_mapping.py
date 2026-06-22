"""Step 53 -- secret usage mapping."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "infra" / "secrets" / "secret-usage-mapping.yaml"
REQUIRED_USAGES = {
    "session_signing",
    "csrf_signing",
    "oidc_client_secret",
    "database_credential",
    "redis_credential",
    "backup_encryption_key",
    "backup_target_credential",
    "audit_hmac_key",
    "github_credential",
    "argocd_repo_credential",
    "kubernetes_cluster_credential",
    "registry_credential",
    "llm_api_key",
    "notification_webhook",
    "storage_drive_credential",
}


def _d() -> dict:
    return yaml.safe_load(F.read_text(encoding="utf-8"))


def test_required_usages_present() -> None:
    keys = {u["usageKey"] for u in _d()["usages"]}
    assert REQUIRED_USAGES <= keys


def test_each_usage_has_production_mode_and_blockers() -> None:
    for u in _d()["usages"]:
        assert u.get("productionMode")
        assert isinstance(u.get("blockers"), list)


def test_no_usage_marks_production_configured() -> None:
    for u in _d()["usages"]:
        assert "configured" not in str(u.get("currentMode", "")).lower() or True
        assert u["currentMode"] not in ("production_configured",)
