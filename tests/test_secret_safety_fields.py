"""Step 53 -- secret safety fields (SDK-level, no live server)."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.secrets_foundation import build_secret_foundation_summary, secret_safety_fields

ROOT = Path(__file__).resolve().parents[1]


def _f() -> dict:
    return secret_safety_fields(build_secret_foundation_summary(), ROOT)


def test_production_and_store_false() -> None:
    f = _f()
    for key in (
        "secrets_production_ready",
        "secrets_production_store_configured",
        "secrets_production_store_enabled",
        "secrets_read_value_enabled",
        "secrets_write_value_enabled",
        "secrets_rotation_enabled",
        "secrets_inline_values_detected",
    ):
        assert f[key] is False, key


def test_committed_flags_all_false() -> None:
    f = _f()
    for key in (
        "secrets_client_secret_committed",
        "secrets_jwt_committed",
        "secrets_private_key_committed",
        "secrets_kubeconfig_committed",
        "secrets_github_token_committed",
        "secrets_argocd_token_committed",
        "secrets_registry_credential_committed",
        "secrets_backup_key_committed",
        "secrets_session_key_committed",
        "secrets_audit_key_committed",
    ):
        assert f[key] is False, key


def test_enabled_true_fields_and_status() -> None:
    f = _f()
    assert f["secrets_foundation_enabled"] is True
    assert f["secrets_redaction_policy_enabled"] is True
    assert f["secrets_secret_refs_valid"] is True
    assert f["secrets_foundation_status"] == "modeled_fail_closed_not_configured"


def test_absent_summary_is_safe() -> None:
    f = secret_safety_fields(None, ROOT)
    assert f["secrets_production_ready"] is False
    assert f["secrets_foundation_status"] == "unknown"
