"""Stage 52 -- signed, server-side session tokens (no raw token persisted).

A session token is ``base64url(identity_key|issued_ts|expires_ts).hmac_sig``,
signed with HMAC-SHA256 using a secret from a runtime key file / env reference
(never committed, never logged, never returned in a response body). The DB
stores only ``session_hash = sha256(token)`` so a leaked DB row cannot
reconstruct a usable cookie. Tokens are validated for signature + expiry; the
store separately checks status (active / expired / revoked).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import time
from collections.abc import Mapping
from pathlib import Path

SESSION_KEY_FILE_ENV = "ADMIN_CONSOLE_SESSION_KEY_FILE"
DEFAULT_SESSION_KEY_PATHS = (
    ".runtime/admin-console-session-key",
    "/tmp/aiagents-admin-console-session-key",
)
DEFAULT_SESSION_TTL_SECONDS = 1800  # 30 minutes


def _resolve_secret(env: Mapping[str, str] | None = None) -> bytes:
    """Read the session signing secret from a runtime key file.

    Order: explicit env path -> default runtime paths -> generate an ephemeral
    in-memory secret (test-only; a restart invalidates sessions, which is safe).
    The raw secret never leaves this module.
    """
    source = env if env is not None else os.environ
    explicit = (source.get(SESSION_KEY_FILE_ENV) or "").strip()
    candidates = [explicit] if explicit else list(DEFAULT_SESSION_KEY_PATHS)
    for cand in candidates:
        if cand and Path(cand).expanduser().is_file():
            return Path(cand).expanduser().read_bytes()
    return _ephemeral_secret()


_EPHEMERAL: bytes | None = None


def _ephemeral_secret() -> bytes:
    global _EPHEMERAL
    if _EPHEMERAL is None:
        _EPHEMERAL = secrets.token_bytes(32)
    return _EPHEMERAL


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def session_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_session(
    identity_key: str,
    *,
    ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
    now: int | None = None,
    env: Mapping[str, str] | None = None,
) -> tuple[str, int, int]:
    """Return (token, issued_ts, expires_ts). The token is never persisted raw."""
    issued = int(now if now is not None else time.time())
    expires = issued + int(ttl_seconds)
    payload = f"{identity_key}|{issued}|{expires}".encode()
    sig = hmac.new(_resolve_secret(env), payload, hashlib.sha256).digest()
    token = f"{_b64(payload)}.{_b64(sig)}"
    return token, issued, expires


def verify_session(
    token: str,
    *,
    now: int | None = None,
    env: Mapping[str, str] | None = None,
) -> dict | None:
    """Validate signature + expiry. Returns claims dict or None (fail-closed)."""
    if not token or "." not in token:
        return None
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        payload = _unb64(payload_b64)
        sig = _unb64(sig_b64)
    except (ValueError, Exception):  # noqa: BLE001 - any decode error fails closed
        return None
    expected = hmac.new(_resolve_secret(env), payload, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        identity_key, issued_s, expires_s = payload.decode("utf-8").split("|")
        issued, expires = int(issued_s), int(expires_s)
    except (ValueError, UnicodeDecodeError):
        return None
    current = int(now if now is not None else time.time())
    if current >= expires:
        return None
    return {"identity_key": identity_key, "issued_at": issued, "expires_at": expires}


__all__ = [
    "SESSION_KEY_FILE_ENV",
    "DEFAULT_SESSION_KEY_PATHS",
    "DEFAULT_SESSION_TTL_SECONDS",
    "session_hash",
    "issue_session",
    "verify_session",
]
