"""Step 58 -- operational metrics redaction.

Strips any secret / token / kubeconfig / chain-of-thought shape from metric values.
Metrics carry counts / statuses / names / freshness only.
"""

from __future__ import annotations

import re
from typing import Any

_SECRET_SHAPES = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY|"
    r"-----BEGIN|eyJ[A-Za-z0-9_-]{10,}\.)"
)
_FORBIDDEN_KEYS = re.compile(
    r"(secret|token|password|kubeconfig|private_key|chain_of_thought|raw_reasoning|prompt)",
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
