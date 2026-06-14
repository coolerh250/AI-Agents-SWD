"""Stage 46 -- agent discussion safety guards.

Pure helpers that assert discussion output stays planning-only and never
carries secrets or chain-of-thought. Used by tests and the agent.
"""

from __future__ import annotations

import os

# Substrings that must never appear in a persisted contribution/finding.
_SECRET_MARKERS = (
    "DISCORD_BOT_TOKEN",
    "GITHUB_TOKEN",
    "GITHUB_PAT",
    "LLM_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AUDIT_HMAC_KEY",
    "BACKUP_KEY",
    "BEGIN RSA PRIVATE KEY",
    "ghp_",
    "xoxb-",
)

# Keys that would indicate chain-of-thought / raw prompt persistence.
_FORBIDDEN_KEYS = ("chain_of_thought", "raw_prompt", "transcript", "reasoning_trace")


def flag(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, "true" if default else "false")).strip().lower()
    return raw not in ("false", "0", "no", "")


def design_review_enabled(env: dict | None = None) -> bool:
    src = env if env is not None else os.environ
    return str(src.get("ENABLE_DESIGN_REVIEW", "true")).strip().lower() not in ("false", "0", "no")


def design_review_planning_only(env: dict | None = None) -> bool:
    src = env if env is not None else os.environ
    return str(src.get("DESIGN_REVIEW_PLANNING_ONLY", "true")).strip().lower() not in (
        "false",
        "0",
        "no",
    )


def design_review_real_llm_enabled(env: dict | None = None) -> bool:
    src = env if env is not None else os.environ
    return str(src.get("ENABLE_DESIGN_REVIEW_REAL_LLM", "false")).strip().lower() in (
        "true",
        "1",
        "yes",
    )


def design_review_work_item_dispatch_enabled(env: dict | None = None) -> bool:
    src = env if env is not None else os.environ
    return str(src.get("ENABLE_DESIGN_REVIEW_WORK_ITEM_DISPATCH", "false")).strip().lower() in (
        "true",
        "1",
        "yes",
    )


def contains_secret(text: str) -> bool:
    upper = (text or "").upper()
    return any(m.upper() in upper for m in _SECRET_MARKERS)


def assert_no_secret(text: str) -> None:
    if contains_secret(text):
        raise ValueError("secret marker detected in discussion/review output")


def assert_no_chain_of_thought(payload: dict) -> None:
    for key in payload:
        if str(key).lower() in _FORBIDDEN_KEYS:
            raise ValueError(f"forbidden chain-of-thought key: {key}")


__all__ = [
    "flag",
    "design_review_enabled",
    "design_review_planning_only",
    "design_review_real_llm_enabled",
    "design_review_work_item_dispatch_enabled",
    "contains_secret",
    "assert_no_secret",
    "assert_no_chain_of_thought",
]
