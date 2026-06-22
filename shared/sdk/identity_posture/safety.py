"""Step 52.4 -- flat /operations/safety identity fields.

Booleans / enums / counts only. Absent summary -> SAFE, fail-closed posture with
`unknown` status; ``identity_production_ready`` is ALWAYS false.
"""

from __future__ import annotations

from typing import Any

from shared.sdk.identity_posture.models import STATUS_UNKNOWN


def identity_posture_safety_fields(summary: dict[str, Any] | None) -> dict[str, Any]:
    p = (summary or {}).get("identityPosture", {}) if summary else {}
    oidc = p.get("oidc", {}) or {}
    sess = p.get("session", {}) or {}
    rm = p.get("roleMapping", {}) or {}
    bg = p.get("breakGlass", {}) or {}
    az = p.get("authorization", {}) or {}
    status = p.get("status", STATUS_UNKNOWN)

    return {
        "identity_posture_enabled": True,
        "identity_posture_status": status,
        "identity_production_ready": False,
        "identity_production_auth_enabled": bool(p.get("productionAuthEnabled")),
        "identity_test_local_enabled": bool(p.get("testLocalEnabled")),
        "identity_test_local_production_allowed": bool(p.get("testLocalProductionFallbackAllowed")),
        # oidc
        "identity_oidc_abstraction_enabled": bool(oidc.get("abstractionEnabled")),
        "identity_oidc_configured": bool(oidc.get("configured")),
        "identity_oidc_enabled": bool(oidc.get("enabled")),
        "identity_oidc_production_enabled": bool(oidc.get("productionEnabled")),
        "identity_oidc_discovery_fetched": bool(oidc.get("discoveryFetched")),
        "identity_oidc_jwks_fetched": bool(oidc.get("jwksFetched")),
        "identity_oidc_callback_enabled": bool(oidc.get("callbackEnabled")),
        "identity_oidc_token_exchange_enabled": bool(oidc.get("tokenExchangeEnabled")),
        "identity_oidc_real_provider_configured": bool(oidc.get("realProviderConfigured")),
        "identity_oidc_secret_committed": bool(oidc.get("secretCommitted")),
        # session
        "identity_session_hardened": bool(sess.get("hardened")),
        "identity_session_raw_token_persisted": bool(sess.get("rawTokenPersisted")),
        "identity_session_cleanup_available": bool(sess.get("cleanupAvailable")),
        "identity_session_concurrency_enforced": bool(sess.get("concurrencyEnforced")),
        "identity_session_forced_logout_supported": bool(sess.get("forcedLogoutSupported")),
        "identity_session_key_rotation_ready": bool(sess.get("keyRotationProductionReady")),
        "identity_session_production_secret_store_configured": bool(
            sess.get("productionSecretStoreConfigured")
        ),
        # role mapping
        "identity_role_mapping_engine_present": bool(rm.get("enginePresent")),
        "identity_role_mapping_configured": bool(rm.get("configured")),
        "identity_unknown_user_behavior": rm.get("unknownUserBehavior", "deny"),
        "identity_default_role": rm.get("defaultRole", "none"),
        "identity_platform_admin_auto_grant": bool(rm.get("platformAdminAutoGrant")),
        "identity_frontend_role_authority": bool(rm.get("frontendRoleAuthority")),
        # break-glass
        "identity_break_glass_enabled": bool(bg.get("enabled")),
        "identity_break_glass_route_present": bool(bg.get("routePresent")),
        "identity_break_glass_requires_future_approval": bool(bg.get("requiresFutureApproval")),
        # authorization boundaries
        "identity_human_acceptance_is_deployment": bool(az.get("humanAcceptanceIsDeployment")),
        "identity_verification_rerun_allowlisted_only": bool(
            az.get("verificationRerunAllowlistedOnly")
        ),
        "identity_platform_admin_infrastructure_authority": bool(
            az.get("platformAdminInfrastructureAuthority")
        ),
    }


__all__ = ["identity_posture_safety_fields"]
