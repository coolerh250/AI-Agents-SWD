"""Stage 48 -- mini delivery pilot safety helpers.

Controlled-only posture: no production execution, no GitHub write, no PR, no
branch push, no deploy, no real LLM, no secret leak, no chain-of-thought, no
repo-root write. Pure helpers -- no I/O, no env mutation.
"""

from __future__ import annotations

import os

from shared.sdk.workspace_operator.safety import contains_secret, redact


def flag(name: str, default: bool, env: dict | None = None) -> bool:
    source = env if env is not None else os.environ
    raw = str(source.get(name, "true" if default else "false")).strip().lower()
    return raw not in ("false", "0", "no", "")


def mini_delivery_safety_flags(env: dict | None = None) -> dict:
    """The controlled-only flag posture surfaced on results + /operations/safety."""
    return {
        "mini_delivery_pilot_enabled": flag("ENABLE_MINI_DELIVERY_PILOT", True, env),
        "mini_delivery_pilot_controlled_only": flag(
            "MINI_DELIVERY_PILOT_CONTROLLED_ONLY", True, env
        ),
        "mini_delivery_real_llm_enabled": flag("ENABLE_MINI_DELIVERY_REAL_LLM", False, env),
        "mini_delivery_github_write_enabled": flag("ENABLE_MINI_DELIVERY_GITHUB_WRITE", False, env),
        "mini_delivery_pr_creation_enabled": flag("ENABLE_MINI_DELIVERY_PR_CREATION", False, env),
        "mini_delivery_deploy_enabled": flag("ENABLE_MINI_DELIVERY_DEPLOY", False, env),
        "mini_delivery_external_delivery_enabled": flag(
            "ENABLE_MINI_DELIVERY_EXTERNAL_DELIVERY", False, env
        ),
        "mini_delivery_pilot_template_mode": flag("MINI_DELIVERY_PILOT_TEMPLATE_MODE", True, env),
    }


__all__ = ["flag", "contains_secret", "redact", "mini_delivery_safety_flags"]
