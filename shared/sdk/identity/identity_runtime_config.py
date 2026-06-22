"""Step 52.3 -- identity runtime config fail-closed validator (no network).

Each keyword is an *unsafe condition*: when present (True) it forces the config
to ``invalid``. The all-false baseline is valid. Fixture-friendly so the verifier
can flip one condition at a time. This validates that an unsafe production
identity config would be rejected; it does NOT enable any production config.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# condition keyword -> human reason
_CONDITIONS: dict[str, str] = {
    "production_auth_enabled_without_oidc_ready": "production auth enabled while OIDC not ready",
    "oidc_enabled_without_role_mapping": "OIDC enabled without a configured role mapping",
    "oidc_enabled_with_unknown_user_allow": "OIDC enabled with unknown-user allow",
    "oidc_enabled_with_nonnone_default_role": "OIDC enabled with a non-none default role",
    "platform_admin_mapping_without_explicit_rule": "platform_admin mapped without an explicit rule",
    "wildcard_group_mapping": "wildcard group mapping present",
    "frontend_role_authority": "frontend role authority enabled",
    "test_local_fallback_in_production": "test-local fallback allowed in production",
    "session_key_ephemeral_in_production": "ephemeral session key in production",
    "session_key_rotation_missing_in_production": "session key rotation missing in production",
    "missing_production_secret_store": "production secret store missing",
}


@dataclass
class IdentityConfigResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


def validate_identity_runtime_config(**conditions: bool) -> IdentityConfigResult:
    unknown = set(conditions) - set(_CONDITIONS)
    if unknown:
        raise ValueError(f"unknown identity config condition(s): {sorted(unknown)}")
    errors = [_CONDITIONS[k] for k, present in conditions.items() if present]
    return IdentityConfigResult(valid=not errors, errors=errors)


# The full set of unsafe conditions this validator enforces (for the verifier).
UNSAFE_CONDITIONS = tuple(_CONDITIONS)


__all__ = ["IdentityConfigResult", "validate_identity_runtime_config", "UNSAFE_CONDITIONS"]
