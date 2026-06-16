"""Stage 52 -- CSRF protection (HMAC-bound to the session).

A CSRF token is ``base64url(session_hash_prefix|issued).hmac_sig`` signed with
the session secret. The client echoes it in an ``X-CSRF-Token`` header on every
mutating request; the server recomputes and compares. Because the token is bound
to the session hash, a token minted for one session cannot be replayed on
another. The token carries no secret value.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Mapping

from shared.sdk.operator_actions.session import _b64, _resolve_secret, _unb64

CSRF_TTL_SECONDS = 1800
CSRF_HEADER = "X-CSRF-Token"


def issue_csrf(
    session_token_hash: str, *, now: int | None = None, env: Mapping[str, str] | None = None
) -> str:
    issued = int(now if now is not None else time.time())
    payload = f"{session_token_hash[:16]}|{issued}".encode()
    sig = hmac.new(_resolve_secret(env), b"csrf:" + payload, hashlib.sha256).digest()
    return f"{_b64(payload)}.{_b64(sig)}"


def verify_csrf(
    token: str,
    session_token_hash: str,
    *,
    now: int | None = None,
    ttl: int = CSRF_TTL_SECONDS,
    env: Mapping[str, str] | None = None,
) -> bool:
    if not token or "." not in token or not session_token_hash:
        return False
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        payload = _unb64(payload_b64)
        sig = _unb64(sig_b64)
    except Exception:  # noqa: BLE001 - decode error fails closed
        return False
    expected = hmac.new(_resolve_secret(env), b"csrf:" + payload, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        return False
    try:
        bound_prefix, issued_s = payload.decode("utf-8").split("|")
        issued = int(issued_s)
    except (ValueError, UnicodeDecodeError):
        return False
    if bound_prefix != session_token_hash[:16]:
        return False
    current = int(now if now is not None else time.time())
    return current < issued + int(ttl)


__all__ = ["CSRF_TTL_SECONDS", "CSRF_HEADER", "issue_csrf", "verify_csrf"]
