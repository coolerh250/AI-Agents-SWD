"""Step 52.4 -- redaction guard for the identity posture surface.

Reuses the Step 52.2 token/secret detector and adds raw-email / GUID checks so
no posture response or summary can carry a secret, raw email, or real group ID.
"""

from __future__ import annotations

import re
from typing import Any

from shared.sdk.identity import find_secret_like

# 8-4-4-4-12 hex GUID (Entra tenant / group object ID shape).
_GUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


def find_sensitive(obj: Any) -> list[str]:
    """Return reasons the serialized object carries sensitive data (deduped)."""
    text = _flatten(obj)
    reasons = list(find_secret_like(text))
    if _GUID.search(text):
        reasons.append("guid: real tenant/group object ID shape present")
    seen: set[str] = set()
    out: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def is_redacted(obj: Any) -> bool:
    return not find_sensitive(obj)


def _flatten(obj: Any) -> str:
    if isinstance(obj, dict):
        return "\n".join(f"{k}: {_flatten(v)}" for k, v in obj.items())
    if isinstance(obj, (list, tuple)):
        return "\n".join(_flatten(v) for v in obj)
    return str(obj)


__all__ = ["find_sensitive", "is_redacted"]
