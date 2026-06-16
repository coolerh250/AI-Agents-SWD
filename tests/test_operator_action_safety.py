"""Stage 52 -- operator-action safety flags (high-risk hard-disabled)."""

from __future__ import annotations

from shared.sdk.operator_actions.safety import operator_action_safety_flags

ENABLED_ENV = {
    "ADMIN_CONSOLE_AUTH_MODE": "test_local_signed_session",
    "ADMIN_CONSOLE_TEST_AUTH_ENABLED": "true",
    "ENABLE_ADMIN_CONSOLE_OPERATOR_ACTIONS": "true",
}


def test_controlled_test_flags() -> None:
    f = operator_action_safety_flags(ENABLED_ENV)
    assert f["admin_console_v1_enabled"] is True
    assert f["admin_console_auth_mode"] == "test_local_signed_session"
    assert f["admin_console_test_auth_enabled"] is True
    assert f["admin_console_production_auth_enabled"] is False
    assert f["admin_console_rbac_enabled"] is True
    assert f["admin_console_csrf_enabled"] is True
    assert f["admin_console_operator_actions_enabled"] is True
    assert f["admin_console_operator_actions_controlled_only"] is True


def test_high_risk_all_disabled() -> None:
    f = operator_action_safety_flags(ENABLED_ENV)
    for k in (
        "admin_console_arbitrary_action_enabled",
        "admin_console_arbitrary_shell_enabled",
        "admin_console_workflow_pause_resume_enabled",
        "admin_console_work_item_mutation_enabled",
        "admin_console_github_actions_enabled",
        "admin_console_deployment_actions_enabled",
        "admin_console_production_actions_enabled",
    ):
        assert f[k] is False


def test_default_disabled_env() -> None:
    f = operator_action_safety_flags({})
    assert f["admin_console_operator_actions_enabled"] is False
    assert f["admin_console_auth_mode"] == "disabled"
