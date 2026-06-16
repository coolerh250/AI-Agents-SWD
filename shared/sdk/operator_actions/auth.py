"""Stage 52 -- authentication mode resolution (fail-closed).

Validation environment uses ``test_local_signed_session``. Production auth
(OIDC) is required-but-unconfigured and stays disabled. Unknown auth modes fail
closed (operator actions disabled). There is no anonymous operator action and no
production fallback credential.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

AUTH_MODE_TEST_LOCAL = "test_local_signed_session"
AUTH_MODE_OIDC = "oidc"
AUTH_MODE_DISABLED = "disabled"
KNOWN_AUTH_MODES = (AUTH_MODE_TEST_LOCAL, AUTH_MODE_OIDC, AUTH_MODE_DISABLED)

# Fixed, non-sensitive test identity. No password is ever used.
TEST_OPERATOR_IDENTITY = "operator-test"


@dataclass
class AuthConfig:
    auth_mode: str
    test_auth_enabled: bool
    production_auth_enabled: bool
    oidc_enabled: bool
    operator_actions_enabled: bool

    def to_safe_dict(self) -> dict:
        return {
            "admin_console_auth_enabled": self.auth_mode != AUTH_MODE_DISABLED,
            "admin_console_auth_mode": self.auth_mode,
            "admin_console_test_auth_enabled": self.test_auth_enabled,
            "admin_console_production_auth_enabled": self.production_auth_enabled,
            "admin_console_oidc_enabled": self.oidc_enabled,
            "admin_console_operator_actions_enabled": self.operator_actions_enabled,
        }


def _flag(source: Mapping[str, str], name: str, default: bool) -> bool:
    raw = str(source.get(name, "true" if default else "false")).strip().lower()
    return raw not in ("false", "0", "no", "")


def resolve_auth_config(env: Mapping[str, str] | None = None) -> AuthConfig:
    """Resolve auth config, failing closed for unknown modes / production."""
    source = env if env is not None else os.environ
    mode = (source.get("ADMIN_CONSOLE_AUTH_MODE") or AUTH_MODE_DISABLED).strip()
    if mode not in KNOWN_AUTH_MODES:
        # Unknown mode -> fail closed.
        return AuthConfig(AUTH_MODE_DISABLED, False, False, False, False)

    production_auth = _flag(source, "ADMIN_CONSOLE_PRODUCTION_AUTH_ENABLED", False)
    oidc = _flag(source, "ADMIN_CONSOLE_OIDC_ENABLED", False)
    test_auth = _flag(source, "ADMIN_CONSOLE_TEST_AUTH_ENABLED", False)

    # Test auth may activate ONLY under the test_local mode and ONLY when
    # production auth is disabled. Otherwise it is forced off (fail closed).
    if mode != AUTH_MODE_TEST_LOCAL or production_auth:
        test_auth = False

    # Operator actions require: a known non-disabled mode + an active auth path.
    # In production mode without OIDC configured, no auth path exists -> off.
    operator_actions = False
    if mode == AUTH_MODE_TEST_LOCAL and test_auth and not production_auth:
        operator_actions = _flag(source, "ENABLE_ADMIN_CONSOLE_OPERATOR_ACTIONS", False)

    return AuthConfig(
        auth_mode=mode,
        test_auth_enabled=test_auth,
        production_auth_enabled=production_auth,
        oidc_enabled=oidc,
        operator_actions_enabled=operator_actions,
    )


def test_login_allowed(env: Mapping[str, str] | None = None) -> bool:
    """A test login endpoint is usable only in the test_local mode with test auth
    enabled and production auth disabled."""
    cfg = resolve_auth_config(env)
    return (
        cfg.auth_mode == AUTH_MODE_TEST_LOCAL
        and cfg.test_auth_enabled
        and not cfg.production_auth_enabled
    )


__all__ = [
    "AUTH_MODE_TEST_LOCAL",
    "AUTH_MODE_OIDC",
    "AUTH_MODE_DISABLED",
    "KNOWN_AUTH_MODES",
    "TEST_OPERATOR_IDENTITY",
    "AuthConfig",
    "resolve_auth_config",
    "test_login_allowed",
]
