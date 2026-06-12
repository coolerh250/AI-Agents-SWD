"""HMAC-SHA256 signer for audit row hashes -- backed by an HMAC keyring.

Stage 39 widens the original single-key signer into a keyring-aware
signer. The keyring is the authoritative source of which key signs new
rows and which keys can verify historical rows. The signer itself is a
thin wrapper that:

* takes a :class:`AuditHmacKeyring` (or builds one from env on demand),
* signs new rows with the keyring's currently-active key,
* verifies historical rows by ``signing_key_id`` so a row signed with
  an older key can still be verified after a rotation.

Hard rules:

* The key VALUE is never returned, logged, echoed, or surfaced through
  any public method. Only opaque ``signing_key_id`` strings cross the
  boundary.
* If the keyring is ``invalid`` (malformed config), signing is
  refused outright -- the signer reports ``signing_key_not_configured``
  for new rows so a wrong key never enters the chain.
* If the keyring is ``none`` (no env), the signer is unconfigured and
  the chain stays unsigned. The hash chain itself remains usable.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Mapping

from .keyring import (
    KEYRING_MODE_INVALID,
    KEYRING_MODE_NONE,
    AuditHmacKeyring,
)
from .models import (
    SIGNATURE_STATUS_NOT_CONFIGURED,
    SIGNATURE_STATUS_SIGNED,
    SIGNATURE_STATUS_UNSIGNED,
)

DEFAULT_SIGNING_KEY_ID = "default-test-key-id"
UNSIGNED_KEY_ID = "unsigned"

VERIFY_OUTCOME_OK = "ok"
VERIFY_OUTCOME_KEY_MISSING = "key_missing"
VERIFY_OUTCOME_SIGNATURE_FAILED = "signature_failed"
VERIFY_OUTCOME_NO_KEYRING = "no_keyring"


class AuditSigner:
    """Read-only signer backed by an HMAC keyring.

    For backwards compatibility, ``AuditSigner()`` still accepts a raw
    ``key=`` parameter (used by some hermetic tests). When ``key=`` is
    given, an ephemeral one-key keyring is built around it.
    """

    def __init__(
        self,
        *,
        keyring: AuditHmacKeyring | None = None,
        key: bytes | None = None,
        key_id: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> None:
        if keyring is not None:
            self._keyring = keyring
        elif key is not None:
            # Build a one-shot keyring from the explicit key for
            # hermetic tests; never touches the real environment.
            override_id = (key_id or "").strip() or DEFAULT_SIGNING_KEY_ID
            self._keyring = AuditHmacKeyring(
                env={
                    "AUDIT_HMAC_KEY": key.decode("utf-8"),
                    "AUDIT_HMAC_KEY_ID": override_id,
                }
            )
        else:
            self._keyring = AuditHmacKeyring(env=env)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def keyring(self) -> AuditHmacKeyring:
        return self._keyring

    @property
    def configured(self) -> bool:
        return self._keyring.configured

    @property
    def keyring_mode(self) -> str:
        return self._keyring.mode

    @property
    def keyring_valid(self) -> bool:
        return self._keyring.valid

    @property
    def keyring_invalid_reason(self) -> str | None:
        return self._keyring.invalid_reason

    @property
    def key_id(self) -> str:
        """The ID of the key that would sign the next row.

        Returns the keyring's active key when one is configured.
        Returns ``"unsigned"`` when no key is configured -- this is
        the opaque marker we persist on integrity rows that were
        written while the keyring was empty.
        """
        active = self._keyring.active_key_id
        return active if active else UNSIGNED_KEY_ID

    # ------------------------------------------------------------------
    # Sign / verify
    # ------------------------------------------------------------------
    def sign(self, row_hash: str) -> tuple[str | None, str, str]:
        """Sign a row_hash with the keyring's active key.

        Returns ``(signature_hex_or_none, signature_status, key_id)``.

        * ``mode=none`` -> ``(None, signing_key_not_configured, "unsigned")``
        * ``mode=invalid`` -> ``(None, signing_key_not_configured, "unsigned")``
          We refuse to sign with a possibly-wrong key. ``audit_integrity_degraded``
          is raised by the writer.
        * configured + row_hash truthy -> ``(hex, signed, active_key_id)``
        * configured + empty row_hash -> ``(None, unsigned, active_key_id)``
        """
        if not self._keyring.configured:
            return None, SIGNATURE_STATUS_NOT_CONFIGURED, UNSIGNED_KEY_ID
        active = self._keyring._active_key_bytes()
        if active is None:
            return None, SIGNATURE_STATUS_NOT_CONFIGURED, UNSIGNED_KEY_ID
        if not row_hash:
            return None, SIGNATURE_STATUS_UNSIGNED, active[0]
        signature = hmac.new(active[1], row_hash.encode("utf-8"), hashlib.sha256).hexdigest()
        return signature, SIGNATURE_STATUS_SIGNED, active[0]

    def verify(self, row_hash: str, signature: str | None) -> bool:
        """Constant-time verify of ``signature`` against the *active* key.

        Kept for backwards compatibility with callers that don't know
        which key signed which row. Prefer :meth:`verify_with` for
        rotation-aware verification.
        """
        if not signature:
            return False
        active = self._keyring._active_key_bytes()
        if active is None:
            return False
        expected = hmac.new(active[1], row_hash.encode("utf-8"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def verify_with(
        self,
        *,
        row_hash: str,
        signature: str | None,
        signing_key_id: str | None,
    ) -> tuple[bool, str]:
        """Rotation-aware verify.

        Returns ``(ok, outcome)`` where ``outcome`` is one of
        ``ok``, ``key_missing``, ``signature_failed``, ``no_keyring``.
        """
        if not signature:
            return False, VERIFY_OUTCOME_SIGNATURE_FAILED
        if self._keyring.mode == KEYRING_MODE_NONE:
            return False, VERIFY_OUTCOME_NO_KEYRING
        if self._keyring.mode == KEYRING_MODE_INVALID:
            return False, VERIFY_OUTCOME_NO_KEYRING
        target_id = signing_key_id or self._keyring.active_key_id or ""
        key_bytes = self._keyring._key_bytes_for(target_id) if target_id else None
        if key_bytes is None:
            return False, VERIFY_OUTCOME_KEY_MISSING
        expected = hmac.new(key_bytes, row_hash.encode("utf-8"), hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, signature):
            return True, VERIFY_OUTCOME_OK
        return False, VERIFY_OUTCOME_SIGNATURE_FAILED


__all__ = [
    "AuditSigner",
    "DEFAULT_SIGNING_KEY_ID",
    "UNSIGNED_KEY_ID",
    "VERIFY_OUTCOME_OK",
    "VERIFY_OUTCOME_KEY_MISSING",
    "VERIFY_OUTCOME_SIGNATURE_FAILED",
    "VERIFY_OUTCOME_NO_KEYRING",
]
