"""Stage 47 -- workspace operator safety helpers.

Controlled-only posture: no real LLM, no GitHub write, no repo-root write, no
deploy, no production execution, no secret leak. Pure helpers -- no I/O, no env
mutation. Used by the runner, the agent, the operations API, and tests.
"""

from __future__ import annotations

import os
import re

# Patterns that must never appear in generated files, command output, or
# persisted summaries. Deliberately conservative.
_SECRET_PATTERNS = (
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),  # GitHub PAT
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),  # OpenAI-style key
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),  # Slack token
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key id
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:discord)[._-]?(?:bot)?[._-]?token\b\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bhmac[._-]?key\b\s*[:=]\s*\S+"),
)


def flag(name: str, default: bool, env: dict | None = None) -> bool:
    """Read a boolean env flag (default-aware). ``true``/``1``/``yes`` -> True."""
    source = env if env is not None else os.environ
    raw = str(source.get(name, "true" if default else "false")).strip().lower()
    return raw not in ("false", "0", "no", "")


def contains_secret(text: str | None) -> bool:
    """True if ``text`` matches any known secret/token pattern."""
    if not text:
        return False
    return any(p.search(text) for p in _SECRET_PATTERNS)


def redact(text: str | None, *, max_len: int = 4000) -> str:
    """Redact secret-like substrings and truncate. Safe to persist."""
    if not text:
        return ""
    out = str(text)
    for p in _SECRET_PATTERNS:
        out = p.sub("[REDACTED]", out)
    if len(out) > max_len:
        out = out[:max_len] + "\n...[truncated]"
    return out


def assert_no_secret(text: str | None, *, where: str = "output") -> None:
    """Raise if ``text`` carries a secret. The message never echoes the value."""
    if contains_secret(text):
        raise ValueError(f"secret-like content detected in {where}")


def workspace_safety_flags(env: dict | None = None) -> dict:
    """The controlled-only flag posture surfaced on results + /operations/safety."""
    return {
        "workspace_operator_enabled": flag("ENABLE_WORKSPACE_OPERATOR", True, env),
        "workspace_operator_controlled_only": flag("WORKSPACE_OPERATOR_CONTROLLED_ONLY", True, env),
        "workspace_operator_real_llm_enabled": flag(
            "ENABLE_WORKSPACE_OPERATOR_REAL_LLM", False, env
        ),
        "workspace_operator_github_write_enabled": flag(
            "ENABLE_WORKSPACE_OPERATOR_GITHUB_WRITE", False, env
        ),
        "workspace_operator_repo_write_enabled": flag(
            "ENABLE_WORKSPACE_OPERATOR_REPO_WRITE", False, env
        ),
        "workspace_operator_deploy_enabled": flag("ENABLE_WORKSPACE_OPERATOR_DEPLOY", False, env),
        "workspace_operator_work_item_dispatch_enabled": flag(
            "ENABLE_WORKSPACE_OPERATOR_WORK_ITEM_DISPATCH", False, env
        ),
        "workspace_operator_template_mode": flag("WORKSPACE_OPERATOR_TEMPLATE_MODE", True, env),
    }


__all__ = [
    "flag",
    "contains_secret",
    "redact",
    "assert_no_secret",
    "workspace_safety_flags",
]
