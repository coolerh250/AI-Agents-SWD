"""Step 52.4 -- identity safety fields (SDK-level, no live server)."""

from __future__ import annotations

from pathlib import Path

from shared.sdk.identity_posture import (
    build_identity_posture_summary,
    identity_posture_safety_fields,
)

SUMMARY = (
    Path(__file__).resolve().parents[1] / "infra" / "identity" / "identity-posture-summary.yaml"
)


def _fields() -> dict:
    return identity_posture_safety_fields(build_identity_posture_summary())


def test_production_and_oidc_false() -> None:
    f = _fields()
    for key in (
        "identity_production_ready",
        "identity_production_auth_enabled",
        "identity_oidc_enabled",
        "identity_oidc_discovery_fetched",
        "identity_oidc_jwks_fetched",
        "identity_oidc_callback_enabled",
        "identity_oidc_token_exchange_enabled",
        "identity_oidc_secret_committed",
        "identity_session_raw_token_persisted",
        "identity_platform_admin_auto_grant",
        "identity_frontend_role_authority",
        "identity_break_glass_enabled",
        "identity_human_acceptance_is_deployment",
        "identity_platform_admin_infrastructure_authority",
    ):
        assert f[key] is False, key


def test_enabled_true_fields() -> None:
    f = _fields()
    assert f["identity_posture_enabled"] is True
    assert f["identity_oidc_abstraction_enabled"] is True
    assert f["identity_session_hardened"] is True
    assert f["identity_role_mapping_engine_present"] is True
    assert f["identity_verification_rerun_allowlisted_only"] is True


def test_enum_fields() -> None:
    f = _fields()
    assert f["identity_posture_status"] == "modeled_fail_closed_not_enabled"
    assert f["identity_unknown_user_behavior"] == "deny"
    assert f["identity_default_role"] == "none"


def test_absent_summary_is_safe() -> None:
    f = identity_posture_safety_fields(None)
    assert f["identity_production_ready"] is False
    assert f["identity_posture_status"] == "unknown"
