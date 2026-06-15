"""Stage 49 -- delivery package safety helpers.

Controlled-only posture: no production execution, no GitHub write, no PR, no
branch push, no deploy, no real LLM, no external delivery, no secret leak, no
chain-of-thought, no repo-root write, no auto human acceptance. Pure helpers --
no I/O, no env mutation.
"""

from __future__ import annotations

import os

from shared.sdk.workspace_operator.safety import contains_secret, redact


def flag(name: str, default: bool, env: dict | None = None) -> bool:
    source = env if env is not None else os.environ
    raw = str(source.get(name, "true" if default else "false")).strip().lower()
    return raw not in ("false", "0", "no", "")


def delivery_package_safety_flags(env: dict | None = None) -> dict:
    """The controlled-only flag posture surfaced on results + /operations/safety."""
    return {
        "delivery_package_enabled": flag("ENABLE_DELIVERY_PACKAGE", True, env),
        "delivery_package_controlled_only": flag("DELIVERY_PACKAGE_CONTROLLED_ONLY", True, env),
        "delivery_package_template_mode": flag("DELIVERY_PACKAGE_TEMPLATE_MODE", True, env),
        "delivery_package_real_llm_enabled": flag("ENABLE_DELIVERY_PACKAGE_REAL_LLM", False, env),
        "delivery_package_github_write_enabled": flag(
            "ENABLE_DELIVERY_PACKAGE_GITHUB_WRITE", False, env
        ),
        "delivery_package_pr_creation_enabled": flag(
            "ENABLE_DELIVERY_PACKAGE_PR_CREATION", False, env
        ),
        "delivery_package_deploy_enabled": flag("ENABLE_DELIVERY_PACKAGE_DEPLOY", False, env),
        "delivery_package_external_delivery_enabled": flag(
            "ENABLE_DELIVERY_PACKAGE_EXTERNAL_DELIVERY", False, env
        ),
        "delivery_package_auto_accept_enabled": flag(
            "ENABLE_DELIVERY_PACKAGE_AUTO_ACCEPT", False, env
        ),
        "delivery_package_operator_actions_enabled": flag(
            "ENABLE_DELIVERY_PACKAGE_OPERATOR_ACTIONS", False, env
        ),
    }


__all__ = ["flag", "contains_secret", "redact", "delivery_package_safety_flags"]
