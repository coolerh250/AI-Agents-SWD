"""Step 52.2 -- OIDC config loader / fail-closed validator (NO network).

Reads only the committed ``infra/identity`` OIDC YAML files. Never reads a real
secret from ``.env``, never connects to an IdP, never parses a real token, never
creates a session. ``validate_oidc_inputs`` is the fail-closed core: any of
production-enabled, test-local fallback, unknown-user != deny, a privileged
default role, discovery/JWKS fetch, an enabled callback, an enabled-but-
incomplete config, or a secret-shaped literal forces status ``invalid``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from shared.sdk.identity.oidc_models import OidcConfigStatus
from shared.sdk.identity.oidc_redaction import contains_secret_like

ROOT = Path(__file__).resolve().parents[3]
IDENTITY_DIR = ROOT / "infra" / "identity"

PROVIDER_KEY = "production-oidc-placeholder"
_PRIVILEGED_DEFAULT_ROLES = {"operator", "platform_admin"}


@dataclass
class OidcValidationResult:
    status: OidcConfigStatus
    errors: list[str] = field(default_factory=list)
    enabled: bool = False
    production_enabled: bool = False

    @property
    def ready(self) -> bool:
        return self.status == "ready_for_future_enablement"

    @property
    def is_valid(self) -> bool:
        return self.status != "invalid"


def validate_oidc_inputs(
    *,
    enabled: bool,
    production_enabled: bool,
    test_local_fallback_allowed: bool,
    required_satisfied: bool,
    any_required_configured: bool,
    unknown_user_behavior: str,
    default_role: str,
    discovery_fetch_enabled: bool,
    jwks_fetch_enabled: bool,
    callback_enabled: bool,
    raw_text: str = "",
) -> OidcValidationResult:
    """Fail-closed validation over primitive config inputs (fixture-friendly)."""
    errors: list[str] = []
    if production_enabled:
        errors.append("production OIDC must not be enabled in this step")
    if test_local_fallback_allowed:
        errors.append("test-local fallback must not be allowed for production auth")
    if str(unknown_user_behavior).lower() not in ("deny", "deny_unknown"):
        errors.append(f"unknown_user_behavior must be deny, got {unknown_user_behavior!r}")
    if str(default_role).lower() in _PRIVILEGED_DEFAULT_ROLES:
        errors.append(f"default role must not be privileged: {default_role!r}")
    if discovery_fetch_enabled:
        errors.append("discovery fetch must be disabled")
    if jwks_fetch_enabled:
        errors.append("JWKS fetch must be disabled")
    if callback_enabled:
        errors.append("OIDC callback must be disabled")
    if enabled and not required_satisfied:
        errors.append("config enabled without all required fields configured")
    if raw_text and contains_secret_like(raw_text):
        errors.append("secret-shaped literal present in config")

    if errors:
        return OidcValidationResult("invalid", errors, enabled, production_enabled)

    if required_satisfied:
        status: OidcConfigStatus = "ready_for_future_enablement"
    elif any_required_configured:
        status = "disabled_missing_required_fields"
    else:
        status = "disabled_unconfigured"
    return OidcValidationResult(status, [], enabled, production_enabled)


def _load(name: str, root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / "infra" / "identity" / name).read_text(encoding="utf-8"))


def _provider_field_values(provider: dict[str, Any]) -> list[bool]:
    """Per-required-field configured flags for the provider entry."""
    client = provider.get("client", {})
    secret = client.get("clientSecret", {}).get("secretRef", {})
    return [
        bool(provider.get("issuer", {}).get("value")),
        bool(provider.get("jwks", {}).get("uri")),
        bool(client.get("clientId", {}).get("valueRef")),
        bool(secret.get("name") and secret.get("key")),
        bool(provider.get("redirectUris", {}).get("values")),
        bool(provider.get("scopes", {}).get("values")),
        bool(provider.get("roleMapping", {}).get("configured")),
    ]


def load_oidc_config(root: Path | None = None) -> OidcValidationResult:
    """Load the committed OIDC config files and validate them, fail-closed."""
    base = root or ROOT
    disabled = _load("production-oidc-disabled-config.yaml", base)
    catalog = _load("oidc-provider-catalog.yaml", base)
    role_map = _load("oidc-role-mapping-contract.yaml", base)
    callback = _load("oidc-callback-boundary.yaml", base)
    discovery = _load("oidc-discovery-contract.yaml", base)
    jwks = _load("jwks-reference-model.yaml", base)

    provider = catalog["providers"][PROVIDER_KEY]
    auth = disabled["auth"]
    rm = role_map["roleMapping"]

    field_flags = _provider_field_values(provider)
    raw_text = "\n".join(
        (base / "infra" / "identity" / n).read_text(encoding="utf-8")
        for n in ("production-oidc-disabled-config.yaml", "oidc-provider-catalog.yaml")
    )

    return validate_oidc_inputs(
        enabled=bool(auth.get("enabled") or provider.get("enabled")),
        production_enabled=bool(auth.get("productionEnabled") or provider.get("productionAllowed")),
        test_local_fallback_allowed=bool(auth.get("testLocalFallbackAllowed")),
        required_satisfied=all(field_flags),
        any_required_configured=any(field_flags),
        unknown_user_behavior=str(rm.get("unknownUserBehavior", "deny")),
        default_role=str(rm.get("defaultRole", "none")),
        discovery_fetch_enabled=bool(
            discovery["discovery"].get("fetchEnabled")
            or provider.get("discovery", {}).get("fetchEnabled")
        ),
        jwks_fetch_enabled=bool(
            jwks["jwks"].get("fetchEnabled") or provider.get("jwks", {}).get("fetchEnabled")
        ),
        callback_enabled=bool(callback["callback"].get("enabled")),
        raw_text=raw_text,
    )


__all__ = [
    "IDENTITY_DIR",
    "PROVIDER_KEY",
    "OidcValidationResult",
    "validate_oidc_inputs",
    "load_oidc_config",
]
