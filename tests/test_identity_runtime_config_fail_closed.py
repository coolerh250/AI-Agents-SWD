"""Step 52.3 -- identity runtime config fail-closed validator."""

from __future__ import annotations

import pytest

from shared.sdk.identity import UNSAFE_CONDITIONS, validate_identity_runtime_config


def test_safe_baseline_valid() -> None:
    assert validate_identity_runtime_config().valid is True


@pytest.mark.parametrize("condition", UNSAFE_CONDITIONS)
def test_each_unsafe_condition_invalidates(condition: str) -> None:
    res = validate_identity_runtime_config(**{condition: True})
    assert res.valid is False
    assert res.errors


def test_unknown_condition_raises() -> None:
    with pytest.raises(ValueError):
        validate_identity_runtime_config(not_a_real_condition=True)


def test_covers_required_conditions() -> None:
    for c in (
        "production_auth_enabled_without_oidc_ready",
        "oidc_enabled_without_role_mapping",
        "oidc_enabled_with_unknown_user_allow",
        "oidc_enabled_with_nonnone_default_role",
        "platform_admin_mapping_without_explicit_rule",
        "wildcard_group_mapping",
        "frontend_role_authority",
        "test_local_fallback_in_production",
        "session_key_ephemeral_in_production",
        "session_key_rotation_missing_in_production",
        "missing_production_secret_store",
    ):
        assert c in UNSAFE_CONDITIONS
