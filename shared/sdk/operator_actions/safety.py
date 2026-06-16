"""Stage 52 -- Admin Console v1 operator-action safety flags.

Booleans-only snapshot for /operations/safety. All high-risk capabilities are
hard-coded false; only the controlled-action set is enabled (and only in a test
auth configuration). Never carries a raw token / secret.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from shared.sdk.operator_actions.auth import resolve_auth_config


def operator_action_safety_flags(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = env if env is not None else os.environ
    cfg = resolve_auth_config(source)
    actions_enabled = cfg.operator_actions_enabled
    return {
        "admin_console_v1_enabled": str(source.get("ENABLE_ADMIN_CONSOLE_V1", "true"))
        .strip()
        .lower()
        != "false",
        "admin_console_auth_enabled": cfg.auth_mode != "disabled",
        "admin_console_auth_mode": cfg.auth_mode,
        "admin_console_test_auth_enabled": cfg.test_auth_enabled,
        "admin_console_production_auth_enabled": cfg.production_auth_enabled,
        "admin_console_oidc_enabled": cfg.oidc_enabled,
        "admin_console_rbac_enabled": True,
        "admin_console_csrf_enabled": True,
        "admin_console_operator_actions_enabled": actions_enabled,
        "admin_console_operator_actions_controlled_only": True,
        # Hard-disabled high-risk capabilities (never executable this stage).
        "admin_console_arbitrary_action_enabled": False,
        "admin_console_arbitrary_shell_enabled": False,
        "admin_console_workflow_pause_resume_enabled": False,
        "admin_console_work_item_mutation_enabled": False,
        "admin_console_github_actions_enabled": False,
        "admin_console_deployment_actions_enabled": False,
        "admin_console_production_actions_enabled": False,
    }


__all__ = ["operator_action_safety_flags"]
