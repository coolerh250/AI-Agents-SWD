"""Stage 52 -- auth config resolution (fail-closed) + models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.sdk.operator_actions.auth import resolve_auth_config
from shared.sdk.operator_actions.auth import test_login_allowed as login_allowed
from shared.sdk.operator_actions.models import OperatorActionRequest


def test_default_fail_closed() -> None:
    cfg = resolve_auth_config({})
    assert cfg.auth_mode == "disabled"
    assert cfg.operator_actions_enabled is False
    assert login_allowed({}) is False


def test_test_local_enables_actions() -> None:
    env = {
        "ADMIN_CONSOLE_AUTH_MODE": "test_local_signed_session",
        "ADMIN_CONSOLE_TEST_AUTH_ENABLED": "true",
        "ENABLE_ADMIN_CONSOLE_OPERATOR_ACTIONS": "true",
    }
    cfg = resolve_auth_config(env)
    assert cfg.operator_actions_enabled is True
    assert login_allowed(env) is True


def test_production_auth_blocks_test_auth() -> None:
    env = {
        "ADMIN_CONSOLE_AUTH_MODE": "test_local_signed_session",
        "ADMIN_CONSOLE_TEST_AUTH_ENABLED": "true",
        "ADMIN_CONSOLE_PRODUCTION_AUTH_ENABLED": "true",
        "ENABLE_ADMIN_CONSOLE_OPERATOR_ACTIONS": "true",
    }
    cfg = resolve_auth_config(env)
    assert cfg.test_auth_enabled is False
    assert cfg.operator_actions_enabled is False


def test_unknown_mode_fails_closed() -> None:
    cfg = resolve_auth_config({"ADMIN_CONSOLE_AUTH_MODE": "weird"})
    assert cfg.auth_mode == "disabled"
    assert cfg.operator_actions_enabled is False


def test_oidc_mode_no_test_actions() -> None:
    cfg = resolve_auth_config(
        {"ADMIN_CONSOLE_AUTH_MODE": "oidc", "ADMIN_CONSOLE_OIDC_ENABLED": "true"}
    )
    assert cfg.operator_actions_enabled is False


def test_reason_required_in_model() -> None:
    with pytest.raises(ValidationError):
        OperatorActionRequest(
            action_key="k",
            identity_key="i",
            action_type="t",
            reason="",
            idempotency_key="x" * 10,
        )
