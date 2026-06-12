"""Stage 40 -- redact sensitive fields from raw alert payloads.

The raw payload must never be stored verbatim. This module removes any key
whose name matches the secret-field list before writing to the database.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

_SECRET_KEYS = frozenset(
    {
        "token",
        "secret",
        "password",
        "authorization",
        "api_key",
        "apikey",
        "webhook_secret",
        "access_token",
        "refresh_token",
        "private_key",
        "client_secret",
        "bearer",
        "credential",
        "credentials",
        "passwd",
        "pass",
    }
)


def _redact_dict(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: "[REDACTED]" if k.lower() in _SECRET_KEYS else _redact_dict(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact_dict(item) for item in obj]
    return obj


def redact_payload(payload: Any) -> dict[str, Any]:
    """Return a redacted copy of *payload* safe to store in the database."""
    redacted = _redact_dict(payload)
    return redacted if isinstance(redacted, dict) else {"_raw": redacted}


def payload_hash(payload: Any) -> str:
    """Deterministic SHA-256 hex digest of the canonical JSON payload."""
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


__all__ = ["redact_payload", "payload_hash"]
