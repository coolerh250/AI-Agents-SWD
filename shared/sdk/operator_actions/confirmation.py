"""Stage 52 -- one-time confirmation nonces (hashed at rest).

A confirmation flow issues a short-lived nonce bound to (action_request,
identity). Only the SHA-256 hash is persisted; the raw nonce is returned once to
the client and must be echoed on execute. The store enforces one-time use,
expiry, and same-identity. These helpers are pure.
"""

from __future__ import annotations

import hashlib
import secrets
import time

CONFIRMATION_TTL_SECONDS = 300  # 5 minutes


def generate_nonce() -> str:
    """A fresh, URL-safe confirmation nonce (raw value, returned once)."""
    return secrets.token_urlsafe(24)


def nonce_hash(nonce: str) -> str:
    return hashlib.sha256(nonce.encode("utf-8")).hexdigest()


def expiry_ts(now: int | None = None, ttl: int = CONFIRMATION_TTL_SECONDS) -> int:
    return int(now if now is not None else time.time()) + int(ttl)


def confirmation_valid(
    *,
    provided_nonce: str,
    stored_hash: str,
    used: bool,
    expires_ts: int,
    same_identity: bool,
    now: int | None = None,
) -> tuple[bool, str]:
    """Validate a confirmation. Returns (ok, reason)."""
    if used:
        return False, "confirmation_already_used"
    if not same_identity:
        return False, "confirmation_identity_mismatch"
    current = int(now if now is not None else time.time())
    if current >= int(expires_ts):
        return False, "confirmation_expired"
    if (
        not provided_nonce
        or not hashlib.sha256(provided_nonce.encode("utf-8")).hexdigest() == stored_hash
    ):
        return False, "confirmation_invalid"
    return True, "ok"


__all__ = [
    "CONFIRMATION_TTL_SECONDS",
    "generate_nonce",
    "nonce_hash",
    "expiry_ts",
    "confirmation_valid",
]
