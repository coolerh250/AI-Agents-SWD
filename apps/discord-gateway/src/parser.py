"""Discord-message parser for the sandbox gateway.

Supports three flavours of inbound text (all sandbox; no real Discord API
is contacted by this module):

A. Slash-like command:
       ``/ai task type=dev.test description="create user management module"``

B. Natural-language command:
       ``ai task: create user management module``

C. Production command (still goes through the platform's approval flow):
       ``/ai task type=production.deploy description="deploy to production"``

Plus per-task GitHub options:
       ``... github.enabled=true github.dry_run=true``
       ``... github.enabled=false``

Output shape — matches the existing ``communication-gateway /intake/mock``
contract so the downstream pipeline is unchanged:

```
{
    "task_id": "...",
    "source": "discord-sandbox",
    "request": {
        "type": "dev.test",
        "description": "...",
        "github": {
            "enabled": True,
            "dry_run": True,
            "repo": "coolerh250/AI-Agents-SWD",
            "base_branch": "main",
        },
        "discord": {
            "channel_id": "...",
            "user_id": "...",
            "message_id": "...",
        },
    },
}
```
"""

from __future__ import annotations

import os
import re
import time
import uuid
from typing import Any

# kv= regex tolerates double-quoted, single-quoted, and bare values.
_KV_RE = re.compile(r'([a-z][\w.]*)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|(\S+))', re.IGNORECASE)
_SLASH_PREFIX = "/ai"
_NATURAL_PREFIX = "ai task"

DEFAULT_TYPE = "dev.test"
DEFAULT_REPO = os.environ.get("GITHUB_DEFAULT_REPO", "coolerh250/AI-Agents-SWD")
DEFAULT_BASE_BRANCH = os.environ.get("GITHUB_DEFAULT_BASE_BRANCH", "main")


class ParseError(ValueError):
    """Raised when an inbound message cannot be turned into a task request."""


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in ("true", "1", "yes", "on"):
        return True
    if text in ("false", "0", "no", "off"):
        return False
    return default


def _make_task_id(prefix: str = "discord") -> str:
    timestamp = int(time.time())
    short = uuid.uuid4().hex[:8]
    return f"{prefix}-{timestamp}-{short}"


def _classify(content: str) -> str:
    lowered = content.strip().lower()
    if lowered.startswith(_SLASH_PREFIX):
        return "slash"
    if lowered.startswith(_NATURAL_PREFIX):
        return "natural"
    return "unknown"


def _extract_natural_description(content: str) -> tuple[str, str]:
    """Pull a single description from an ``ai task: ...`` style message.

    Returns ``(description, remainder)`` where ``remainder`` carries the
    trailing ``key=value`` pairs (if any). We split on the first colon so
    extra colons inside the description don't break the parser.
    """
    body = content.strip()
    if not body.lower().startswith(_NATURAL_PREFIX):
        return "", body
    body = body[len(_NATURAL_PREFIX) :].strip()
    if body.startswith(":"):
        body = body[1:].strip()
    # ``description text key=value key=value`` — separate the trailing kv pairs.
    parts = body.split()
    kv_start = None
    for idx, token in enumerate(parts):
        if "=" in token and re.match(r"[a-z][\w.]*=", token, re.IGNORECASE):
            kv_start = idx
            break
    if kv_start is None:
        return body, ""
    return " ".join(parts[:kv_start]).strip(), " ".join(parts[kv_start:]).strip()


def _kv_pairs(text: str) -> dict[str, str]:
    pairs: dict[str, str] = {}
    for match in _KV_RE.finditer(text):
        key = match.group(1).lower()
        value = match.group(2) or match.group(3) or match.group(4) or ""
        pairs[key] = value
    return pairs


def _build_github_block(pairs: dict[str, str]) -> dict[str, Any]:
    enabled = _coerce_bool(pairs.get("github.enabled"), default=True)
    dry_run = _coerce_bool(pairs.get("github.dry_run"), default=True)
    return {
        "enabled": enabled,
        "dry_run": dry_run,
        "repo": pairs.get("github.repo", DEFAULT_REPO),
        "base_branch": pairs.get("github.base_branch", DEFAULT_BASE_BRANCH),
    }


def parse_discord_message(
    content: str,
    *,
    channel_id: str = "",
    user_id: str = "",
    message_id: str = "",
    task_id: str | None = None,
) -> dict[str, Any]:
    """Turn a sandbox Discord message into an intake-ready payload.

    Raises ``ParseError`` on empty messages or messages we cannot classify.
    The caller (the FastAPI route) maps the error to a 400.
    """
    if content is None or not str(content).strip():
        raise ParseError("empty message")
    raw = str(content).strip()
    flavour = _classify(raw)
    if flavour == "unknown":
        raise ParseError(
            "unsupported message — use '/ai task type=… description=…' " "or 'ai task: …'"
        )

    description = ""
    payload_body = raw
    if flavour == "slash":
        # Drop the ``/ai task`` prefix; everything after is kv pairs.
        tail = raw[len(_SLASH_PREFIX) :].strip()
        if tail.lower().startswith("task"):
            tail = tail[len("task") :].strip()
        payload_body = tail
        pairs = _kv_pairs(payload_body)
        description = _strip_quotes(pairs.get("description", ""))
    else:
        description, kv_tail = _extract_natural_description(raw)
        pairs = _kv_pairs(kv_tail)

    if not description:
        raise ParseError("description is required")

    request_type = pairs.get("type", DEFAULT_TYPE).strip() or DEFAULT_TYPE

    request: dict[str, Any] = {
        "type": request_type,
        "description": description,
        "github": _build_github_block(pairs),
        "discord": {
            "channel_id": str(channel_id or pairs.get("channel_id", "")),
            "user_id": str(user_id or pairs.get("user_id", "")),
            "message_id": str(message_id or pairs.get("message_id", "")),
        },
    }
    return {
        "task_id": (task_id or pairs.get("task_id") or _make_task_id()).strip(),
        "source": "discord-sandbox",
        "request": request,
        "command_type": flavour,
    }
