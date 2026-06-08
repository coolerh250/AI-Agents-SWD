"""Optional HMAC-SHA256 signer for audit row hashes.

The signer reads ``AUDIT_HMAC_KEY`` from the env (or a
``SecretProvider`` if one is wired in). When the key is missing the
signer is **not** an error -- it returns ``None`` and the integrity
record records ``signature_status=signing_key_not_configured``. This
keeps the unsigned hash-chain useful while making it easy for an
operator to enable HMAC later.

The key value is never returned, logged, or echoed by any function in
this module. The ``signing_key_id`` is opaque metadata; it is safe to
expose via the operations API so an operator can confirm which key was
in use at sign time.
"""

from __future__ import annotations

import hashlib
import hmac
import os

from .models import (
    SIGNATURE_STATUS_NOT_CONFIGURED,
    SIGNATURE_STATUS_SIGNED,
    SIGNATURE_STATUS_UNSIGNED,
)

DEFAULT_SIGNING_KEY_ID = "default-test-key-id"
UNSIGNED_KEY_ID = "unsigned"


class AuditSigner:
    """Read-only signer. Never returns the key value."""

    def __init__(
        self,
        *,
        key: bytes | None = None,
        key_id: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        src = env if env is not None else os.environ
        if key is not None:
            self._key: bytes | None = key
        else:
            raw = (src.get("AUDIT_HMAC_KEY", "") or "").strip()
            self._key = raw.encode("utf-8") if raw else None
        if key_id is not None:
            self._key_id = key_id
        else:
            env_key_id = (src.get("AUDIT_HMAC_KEY_ID", "") or "").strip()
            if self._key is None:
                self._key_id = UNSIGNED_KEY_ID
            elif env_key_id:
                self._key_id = env_key_id
            else:
                self._key_id = DEFAULT_SIGNING_KEY_ID

    @property
    def configured(self) -> bool:
        return self._key is not None

    @property
    def key_id(self) -> str:
        return self._key_id

    def sign(self, row_hash: str) -> tuple[str | None, str, str]:
        """Sign a row_hash. Returns ``(signature, signature_status, key_id)``.

        When the key is absent the signature is ``None`` and the
        status is ``signing_key_not_configured``. Callers persist that
        triple verbatim onto the integrity record.
        """
        if self._key is None:
            return None, SIGNATURE_STATUS_NOT_CONFIGURED, self._key_id
        if not row_hash:
            return None, SIGNATURE_STATUS_UNSIGNED, self._key_id
        signature = hmac.new(self._key, row_hash.encode("utf-8"), hashlib.sha256).hexdigest()
        return signature, SIGNATURE_STATUS_SIGNED, self._key_id

    def verify(self, row_hash: str, signature: str | None) -> bool:
        """Constant-time verify of a signature against ``row_hash``."""
        if self._key is None or not signature:
            return False
        expected = hmac.new(self._key, row_hash.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


__all__ = ["AuditSigner", "DEFAULT_SIGNING_KEY_ID", "UNSIGNED_KEY_ID"]
