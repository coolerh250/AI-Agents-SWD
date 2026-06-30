"""Step 62 -- production readiness redaction.

Drops any secret / token / kubeconfig / chain-of-thought / raw-dump shape from readiness
payloads and audit metadata. Records carry ids / statuses / markers / counts only.
"""

from __future__ import annotations

import re
from typing import Any

_SECRET_SHAPES = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|"
    r"BEGIN [A-Z ]*PRIVATE KEY|-----BEGIN|eyJ[A-Za-z0-9_-]{10,}\.)"
)
_FORBIDDEN_KEYS = re.compile(
    r"(secret|token|password|credential|kubeconfig|private_key|chain_of_thought|"
    r"raw_reasoning|raw_prompt|raw_dump|raw_db_dump|raw_redis_dump)",
    re.IGNORECASE,
)


def redact(value: Any) -> Any:
    """Recursively drop secret-shaped values and forbidden keys."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if _FORBIDDEN_KEYS.search(str(k)):
                out[k] = "[redacted]"
                continue
            out[k] = redact(v)
        return out
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str) and _SECRET_SHAPES.search(value):
        return "[redacted]"
    return value
