"""Step 52.2 -- OIDC fail-closed validator fixtures.

Each unsafe config shape must validate as ``invalid``. The "secret literal"
fixture is assembled at runtime so no secret-shaped token is committed.
"""

from __future__ import annotations

from shared.sdk.identity import validate_oidc_inputs

_BASE = dict(
    enabled=False,
    production_enabled=False,
    test_local_fallback_allowed=False,
    required_satisfied=False,
    any_required_configured=False,
    unknown_user_behavior="deny",
    default_role="none",
    discovery_fetch_enabled=False,
    jwks_fetch_enabled=False,
    callback_enabled=False,
    raw_text="",
)


def _invalid(**overrides: object) -> bool:
    return validate_oidc_inputs(**{**_BASE, **overrides}).status == "invalid"  # type: ignore[arg-type]


def test_safe_baseline_not_invalid() -> None:
    assert validate_oidc_inputs(**_BASE).status == "disabled_unconfigured"  # type: ignore[arg-type]


def test_production_enabled_invalid() -> None:
    assert _invalid(production_enabled=True)


def test_test_local_fallback_invalid() -> None:
    assert _invalid(test_local_fallback_allowed=True)


def test_enabled_without_required_invalid() -> None:
    assert _invalid(enabled=True, required_satisfied=False)


def test_unknown_user_allow_invalid() -> None:
    assert _invalid(unknown_user_behavior="allow")


def test_privileged_default_role_invalid() -> None:
    assert _invalid(default_role="operator")
    assert _invalid(default_role="platform_admin")


def test_discovery_and_jwks_fetch_invalid() -> None:
    assert _invalid(discovery_fetch_enabled=True)
    assert _invalid(jwks_fetch_enabled=True)


def test_callback_enabled_invalid() -> None:
    assert _invalid(callback_enabled=True)


def test_secret_literal_invalid() -> None:
    # Assembled at runtime; never committed as a single secret-shaped token.
    secret_line = "client_secret: " + ("A" * 24)
    assert _invalid(raw_text=secret_line)
