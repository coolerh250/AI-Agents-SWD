"""Stage 52 -- idempotency-key helpers for operator actions.

Every mutating action requires an ``Idempotency-Key``. A repeated request with
the same key must return the existing action result rather than re-executing.
The store enforces uniqueness on ``idempotency_key``; these helpers normalise
and validate the key.
"""

from __future__ import annotations

import re

_KEY_RE = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def normalize_key(raw: str | None) -> str | None:
    if raw is None:
        return None
    key = raw.strip()
    return key or None


def is_valid_key(raw: str | None) -> bool:
    key = normalize_key(raw)
    return bool(key and _KEY_RE.match(key))


__all__ = ["normalize_key", "is_valid_key"]
