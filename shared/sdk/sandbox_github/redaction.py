"""Step 59 -- sandbox GitHub redaction.

Drops any secret / token / chain-of-thought shape from sandbox draft-PR payloads
and audit metadata before they leave the SDK. Records carry keys / counts / statuses
/ URLs only -- never a credential.
"""

from __future__ import annotations

import re
from typing import Any

_SECRET_SHAPES = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|gho_[A-Za-z0-9]{20,}|"
    r"BEGIN [A-Z ]*PRIVATE KEY|-----BEGIN|eyJ[A-Za-z0-9_-]{10,}\.)"
)
_FORBIDDEN_KEYS = re.compile(
    r"(secret|token|password|credential|private_key|chain_of_thought|raw_reasoning|raw_prompt)",
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
