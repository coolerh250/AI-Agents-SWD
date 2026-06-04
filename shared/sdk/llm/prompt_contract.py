"""Stage 30 — prompt contract + redaction helpers.

The prompt contract is the deterministic envelope every LLM provider
receives. It carries:

* the task summary + execution mode,
* the allowed / denied workspace paths,
* the safety rails (``production_executed=false``, no secrets, no
  delete, no production deploy),
* the requested output schema,
* a clarification clause (LLM MUST ask instead of guess),
* a mandatory ``requires_human_review=true`` flag.

The producer always hashes the prompt before persisting it; the
response is hashed too. Previews are short and redacted so a
``/operations/llm/interactions`` reader never sees a raw secret even if
one accidentally slipped in.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

PROMPT_CONTRACT_VERSION = "1.0"
_DEFAULT_PREVIEW_LIMIT = 240

# Patterns scrubbed from previews. Mirrors the code-workspace secret
# patterns but operates on FREE-FORM text (prompt / response) — so we
# replace the match with ``[REDACTED:<name>]``.
_REDACT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("github_token", re.compile(r"\bghp_[A-Za-z0-9]{20,}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{12,}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("bearer_token", re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.=]{20,}")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    ("hashicorp_token", re.compile(r"\bhvs\.[A-Za-z0-9_\-]{20,}\b")),
    (
        "password_assignment",
        re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*['\"]?[^\s'\"]{4,}['\"]?"),
    ),
)

# Env var name patterns we explicitly mask so a wrapper that includes
# ``OPENAI_API_KEY=<value>`` never leaks the value into the preview.
_API_KEY_ENV_PATTERN = re.compile(
    r"(?i)\b(OPENAI_API_KEY|ANTHROPIC_API_KEY|LLM_API_KEY|DISCORD_BOT_TOKEN|"
    r"GITHUB_TOKEN|HF_TOKEN|VAULT_TOKEN)\s*[:=]\s*\S+"
)


def hash_text(text: str) -> str:
    """Return a stable SHA-256 hex digest for any text input."""
    if text is None:
        text = ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def redact_text(text: str, limit: int = _DEFAULT_PREVIEW_LIMIT) -> str:
    """Return a redacted, length-bounded preview of ``text``.

    1. Every known secret-shaped match is rewritten to
       ``[REDACTED:<name>]`` BEFORE truncation, so truncation can never
       leave half of a token in the preview.
    2. Env-var-style ``KEY=value`` for known API key names is
       rewritten to ``KEY=[REDACTED]``.
    3. The result is truncated to ``limit`` chars with a trailing
       ``…[truncated]`` marker.
    """
    if not text:
        return ""
    redacted = text
    for name, pattern in _REDACT_PATTERNS:
        redacted = pattern.sub(f"[REDACTED:{name}]", redacted)
    redacted = _API_KEY_ENV_PATTERN.sub(lambda m: f"{m.group(1)}=[REDACTED]", redacted)
    if len(redacted) > limit:
        return redacted[:limit] + "…[truncated]"
    return redacted


def _normalise_paths(values: Any) -> list[str]:
    if not values:
        return []
    return [str(v) for v in values if v]


def build_prompt_contract(
    *,
    task_id: str,
    execution_mode: str,
    interaction_type: str,
    description: str,
    allowed_paths: list[str],
    denied_paths: list[str],
    output_schema_name: str,
    request_type: str = "",
    acceptance_criteria: list[str] | None = None,
) -> dict[str, Any]:
    """Build the deterministic prompt envelope for one LLM call.

    The return value is JSON-serialisable. Providers MUST treat it as
    read-only — they pass it to the wire (or, for the mock provider,
    derive a response from it deterministically).
    """
    summary = (description or "").strip()
    return {
        "contract_version": PROMPT_CONTRACT_VERSION,
        "task_id": task_id,
        "execution_mode": execution_mode,
        "request_type": request_type,
        "interaction_type": interaction_type,
        "task_summary": summary[:2000],
        "acceptance_criteria": list(acceptance_criteria or []),
        "allowed_paths": _normalise_paths(allowed_paths),
        "denied_paths": _normalise_paths(denied_paths),
        "safety_rails": {
            "production_executed": False,
            "no_secrets": True,
            "no_delete": True,
            "no_production_deploy": True,
            "no_branch_protection_modification": True,
            "no_destructive_commands": True,
            "no_real_github_write": True,
            "must_ask_clarification_if_uncertain": True,
            "must_mark_requires_human_review_true": True,
        },
        "output_schema": output_schema_name,
        "instructions": (
            "Return JSON that matches the requested schema. Refuse to "
            "modify denied_paths. Refuse to emit delete operations. "
            "Refuse to embed secrets. Always set requires_human_review=true."
        ),
    }
