"""Step 52.4 -- identity posture collector (read-only, no network, no secrets).

Aggregates the COMMITTED Step 52.1/52.2/52.3 identity models into a redacted
posture summary. Reads only repo YAML; never connects to an IdP, fetches
discovery/JWKS, reads a secret/key file, or runs a verifier. A missing/unreadable
source yields status ``unknown`` -- never a fake "modeled" PASS.

``build_identity_posture_summary(root)`` returns the serializable summary that is
committed to ``infra/identity/identity-posture-summary.yaml`` and copied into the
orchestrator image; ``load_identity_posture_summary(path)`` reads it back.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shared.sdk.identity_posture.models import (
    REQUIRED_FALSE,
    STATUS_FAILED,
    STATUS_MODELED,
    STATUS_UNKNOWN,
)

ROOT = Path(__file__).resolve().parents[3]

# Source files whose presence is required for a non-unknown posture.
_SOURCES = (
    "authentication-inventory.yaml",
    "production-oidc-disabled-config.yaml",
    "oidc-provider-catalog.yaml",
    "oidc-discovery-contract.yaml",
    "jwks-reference-model.yaml",
    "oidc-callback-boundary.yaml",
    "session-hardening-catalog.yaml",
    "session-concurrency-policy.yaml",
    "forced-logout-model.yaml",
    "session-key-rotation-model.yaml",
    "role-mapping-policy.yaml",
    "unknown-user-policy.yaml",
    "break-glass-model.yaml",
    "identity-authorization-decision-model.yaml",
    "human-acceptance-identity-boundary.yaml",
    "verification-rerun-identity-boundary.yaml",
    "rbac-inventory.yaml",
)

LIMITATIONS = [
    "no_real_oidc_provider_configured",
    "no_oidc_discovery_or_jwks_fetch",
    "no_oidc_callback_or_token_exchange",
    "no_production_auth",
    "no_production_session_secret_store",
    "no_real_group_to_role_mapping",
    "no_production_session_key_rotation_backend",
    "break_glass_disabled_pending_production_approval",
    "no_production_approval_identity_chain",
]
NEXT_REQUIRED_STEPS = [
    "step_53_production_secret_store",
    "production_oidc_provider_configuration",
    "production_role_mapping_configuration",
    "step_60_production_approval_identity_chain",
]


def _load(idir: Path, name: str) -> dict[str, Any]:
    return yaml.safe_load((idir / name).read_text(encoding="utf-8")) or {}


def _get(d: dict, *path: str, default: Any = None) -> Any:
    cur: Any = d
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def collect_identity_posture(root: Path | None = None) -> dict[str, Any]:
    """Derive the posture dict from the committed identity models."""
    base = root or ROOT
    idir = base / "infra" / "identity"

    missing = [s for s in _SOURCES if not (idir / s).is_file()]
    if missing:
        return _unknown_posture(missing)

    try:
        auth = _load(idir, "authentication-inventory.yaml")
        disabled = _load(idir, "production-oidc-disabled-config.yaml")
        provider = _load(idir, "oidc-provider-catalog.yaml")["providers"][
            "production-oidc-placeholder"
        ]
        discovery = _load(idir, "oidc-discovery-contract.yaml")
        jwks = _load(idir, "jwks-reference-model.yaml")
        callback = _load(idir, "oidc-callback-boundary.yaml")
        hardening = _load(idir, "session-hardening-catalog.yaml")["sessionHardening"]
        concurrency = _load(idir, "session-concurrency-policy.yaml")["sessionConcurrency"]
        forced = _load(idir, "forced-logout-model.yaml")["forcedLogout"]
        keyrot = _load(idir, "session-key-rotation-model.yaml")
        rolemap = _load(idir, "role-mapping-policy.yaml")["roleMapping"]
        breakglass = _load(idir, "break-glass-model.yaml")["breakGlass"]
        rbac = _load(idir, "rbac-inventory.yaml")
        ha = _load(idir, "human-acceptance-identity-boundary.yaml")["humanAcceptance"]
        vr = _load(idir, "verification-rerun-identity-boundary.yaml")["verificationRerun"]
    except (KeyError, TypeError):
        return _unknown_posture(["malformed_source"])

    pa: dict[str, Any] = next(
        (r for r in rbac.get("roles", []) if r.get("key") == "platform_admin"), {}
    )

    posture: dict[str, Any] = {
        "productionIdentityReady": False,
        "productionAuthEnabled": bool(_get(auth, "meta", "productionAuthEnabled", default=False)),
        "testLocalEnabled": True,
        "testLocalProductionFallbackAllowed": bool(
            _get(disabled, "auth", "testLocalFallbackAllowed", default=False)
        ),
        "oidc": {
            "abstractionEnabled": True,
            "configured": bool(provider.get("configured")),
            "enabled": bool(provider.get("enabled")),
            "productionEnabled": bool(_get(disabled, "auth", "productionEnabled", default=False)),
            "discoveryFetched": bool(_get(discovery, "discovery", "fetchEnabled", default=False)),
            "jwksFetched": bool(_get(jwks, "jwks", "fetchEnabled", default=False)),
            "callbackEnabled": bool(_get(callback, "callback", "enabled", default=False)),
            "tokenExchangeEnabled": bool(
                _get(callback, "callback", "authorizationCodeExchange", default=False)
            ),
            "realProviderConfigured": bool(_get(provider, "issuer", "value", default="")),
            "secretCommitted": False,
        },
        "session": {
            "hardened": bool(_get(hardening, "cookie", "httpOnly", default=False)),
            "rawTokenPersisted": bool(
                _get(hardening, "persistence", "rawTokenPersisted", default=True)
            ),
            "cleanupAvailable": bool(_get(hardening, "cleanup", "implemented", default=False)),
            "cleanupMode": _get(hardening, "cleanup", "mode", default=STATUS_UNKNOWN),
            "concurrencyEnforced": concurrency.get("currentBehavior") == "enforced",
            "forcedLogoutSupported": bool(
                _get(forced, "sessionLevelRevoke", "supported", default=False)
            ),
            "keyRotationProductionReady": bool(
                _get(keyrot, "constraints", "currentKeyProductionReady", default=False)
            ),
            "productionSecretStoreConfigured": False,
        },
        "roleMapping": {
            "enginePresent": True,
            "configured": bool(rolemap.get("configured")),
            "unknownUserBehavior": rolemap.get("unknownUserBehavior", "deny"),
            "defaultRole": rolemap.get("defaultRole", "none"),
            # auto-grant is false when the policy forbids a default platform_admin
            "platformAdminAutoGrant": not rolemap.get("forbidden", {}).get(
                "defaultPlatformAdmin", False
            )
            and rolemap.get("defaultRole") == "platform_admin",
            "frontendRoleAuthority": bool(rolemap.get("frontendRoleAuthority")),
        },
        "breakGlass": {
            "enabled": bool(breakglass.get("enabled")),
            "routePresent": bool(breakglass.get("loginRouteExists")),
            "requiresFutureApproval": bool(
                _get(breakglass, "requirements", "separateApprovalRequired", default=False)
            ),
        },
        "authorization": {
            "humanAcceptanceIsDeployment": bool(ha.get("isProductionApproval")),
            "verificationRerunAllowlistedOnly": _get(vr, "execution", "shell", default=True)
            is False,
            "platformAdminInfrastructureAuthority": pa.get("productionAuthority", "none") != "none",
        },
        "limitations": list(LIMITATIONS),
        "nextRequiredSteps": list(NEXT_REQUIRED_STEPS),
    }
    posture["status"] = _derive_status(posture)
    return posture


def _derive_status(posture: dict[str, Any]) -> str:
    for path in REQUIRED_FALSE:
        cur: Any = posture
        for key in path.split("."):
            cur = cur.get(key) if isinstance(cur, dict) else None
        if cur:  # any safety invariant violated -> failed
            return STATUS_FAILED
    return STATUS_MODELED


def _unknown_posture(reasons: list[str]) -> dict[str, Any]:
    return {
        "status": STATUS_UNKNOWN,
        "productionIdentityReady": False,
        "productionAuthEnabled": False,
        "oidc": {"enabled": False, "configured": False},
        "session": {"rawTokenPersisted": False},
        "roleMapping": {"enginePresent": False, "configured": False},
        "breakGlass": {"enabled": False},
        "authorization": {},
        "limitations": ["identity_posture_source_missing"],
        "nextRequiredSteps": [],
        "missingSources": reasons,
    }


def build_identity_posture_summary(root: Path | None = None) -> dict[str, Any]:
    posture = collect_identity_posture(root)
    return {
        "version": "1",
        "meta": {"stage": "54D", "step": "52.4"},
        "identityPosture": posture,
    }


def load_identity_posture_summary(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


__all__ = [
    "LIMITATIONS",
    "NEXT_REQUIRED_STEPS",
    "collect_identity_posture",
    "build_identity_posture_summary",
    "load_identity_posture_summary",
]
