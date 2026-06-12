"""Stage 39 -- HMAC keyring loader for tamper-evident audit chain.

The keyring is the central, in-process source of HMAC signing keys
used by ``AuditSigner`` and ``AuditChainVerifier``. It supports three
configuration shapes (priority order, highest first):

1. ``AUDIT_HMAC_KEYRING_JSON`` -- a JSON document::

       {
         "active_key_id": "audit-key-2026-06",
         "keys": {
           "audit-key-2026-05": "<base64-or-plain-secret>",
           "audit-key-2026-06": "<base64-or-plain-secret>"
         }
       }

   ``AUDIT_HMAC_ACTIVE_KEY_ID`` may override ``active_key_id``.

2. ``AUDIT_HMAC_KEY`` (legacy single-key fallback). ``AUDIT_HMAC_KEY_ID``
   names it; if absent the key is named ``"legacy-single-key"``.

3. Nothing configured -- keyring mode is ``none``. The signer remains
   not-configured, the chain stays unsigned, and the verifier still
   passes hash-chain rows without requiring a signature.

Hard rules:

* The key VALUE is never returned by any public accessor. The loader
  exposes only ``key_id``s, ``active_key_id``, ``mode``, and an
  ``invalid_reason`` string when the configuration is malformed.
* When the configuration is malformed (mode ``invalid``), no key is
  surfaced; signing is disabled to prevent signing with a wrong key.
* A failed JSON parse, an empty ``keys`` mapping, an ``active_key_id``
  not present in ``keys``, or a non-string key value all yield mode
  ``invalid`` with a human-readable reason.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

KEYRING_MODE_NONE = "none"
KEYRING_MODE_LEGACY_SINGLE_KEY = "legacy_single_key"
KEYRING_MODE_MULTI_KEYRING = "multi_keyring"
KEYRING_MODE_INVALID = "invalid"

KEY_SOURCE_LEGACY_ENV = "legacy_env"
KEY_SOURCE_KEYRING_ENV = "keyring_env"
KEY_SOURCE_SECRET_PROVIDER = "secret_provider"
KEY_SOURCE_UNKNOWN = "unknown"

DEFAULT_LEGACY_KEY_ID = "legacy-single-key"


@dataclass(frozen=True)
class _KeyEntry:
    key_id: str
    key_bytes: bytes
    source: str


@dataclass
class KeyringSnapshot:
    """A read-only view safe to expose via operations endpoints."""

    mode: str
    active_key_id: str | None
    known_key_ids: list[str] = field(default_factory=list)
    invalid_reason: str | None = None
    source: str = KEY_SOURCE_UNKNOWN

    @property
    def configured(self) -> bool:
        return self.mode in (
            KEYRING_MODE_LEGACY_SINGLE_KEY,
            KEYRING_MODE_MULTI_KEYRING,
        ) and bool(self.active_key_id)

    @property
    def valid(self) -> bool:
        return self.mode != KEYRING_MODE_INVALID

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "configured": self.configured,
            "valid": self.valid,
            "active_key_id": self.active_key_id,
            "known_key_ids": list(self.known_key_ids),
            "invalid_reason": self.invalid_reason,
            "source": self.source,
        }


class AuditHmacKeyring:
    """In-process HMAC keyring built from environment variables.

    Construct once at service startup. The keyring never reads from
    disk and does not expose the key value through any public method.
    """

    def __init__(
        self,
        *,
        env: Mapping[str, str] | None = None,
    ) -> None:
        src = dict(env if env is not None else os.environ)
        self._keys: dict[str, _KeyEntry] = {}
        self._active_key_id: str | None = None
        self._invalid_reason: str | None = None
        self._source: str = KEY_SOURCE_UNKNOWN
        self._mode: str = KEYRING_MODE_NONE

        keyring_json = (src.get("AUDIT_HMAC_KEYRING_JSON", "") or "").strip()
        if keyring_json:
            self._load_keyring_json(keyring_json, src.get("AUDIT_HMAC_ACTIVE_KEY_ID"))
            return

        legacy = (src.get("AUDIT_HMAC_KEY", "") or "").strip()
        if legacy:
            self._load_legacy_single_key(legacy, src.get("AUDIT_HMAC_KEY_ID"))
            return

        # No keyring configured. Signer will remain unsigned-mode.
        self._mode = KEYRING_MODE_NONE

    # ------------------------------------------------------------------
    # Loaders
    # ------------------------------------------------------------------
    def _load_keyring_json(self, raw: str, override_active: str | None) -> None:
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            self._mode = KEYRING_MODE_INVALID
            self._invalid_reason = "AUDIT_HMAC_KEYRING_JSON is not valid JSON"
            self._source = KEY_SOURCE_KEYRING_ENV
            return
        if not isinstance(payload, dict):
            self._mode = KEYRING_MODE_INVALID
            self._invalid_reason = "AUDIT_HMAC_KEYRING_JSON must be a JSON object"
            self._source = KEY_SOURCE_KEYRING_ENV
            return
        keys = payload.get("keys")
        if not isinstance(keys, dict) or not keys:
            self._mode = KEYRING_MODE_INVALID
            self._invalid_reason = "AUDIT_HMAC_KEYRING_JSON.keys missing or empty"
            self._source = KEY_SOURCE_KEYRING_ENV
            return
        loaded: dict[str, _KeyEntry] = {}
        for key_id, key_value in keys.items():
            if not isinstance(key_id, str) or not key_id.strip():
                self._mode = KEYRING_MODE_INVALID
                self._invalid_reason = "AUDIT_HMAC_KEYRING_JSON contains an empty key_id"
                self._source = KEY_SOURCE_KEYRING_ENV
                return
            if not isinstance(key_value, str) or not key_value.strip():
                self._mode = KEYRING_MODE_INVALID
                self._invalid_reason = (
                    f"AUDIT_HMAC_KEYRING_JSON key '{key_id}' has empty or non-string value"
                )
                self._source = KEY_SOURCE_KEYRING_ENV
                return
            loaded[key_id] = _KeyEntry(
                key_id=key_id,
                key_bytes=key_value.encode("utf-8"),
                source=KEY_SOURCE_KEYRING_ENV,
            )
        declared_active = (
            (override_active or "").strip() or str(payload.get("active_key_id") or "").strip() or ""
        )
        if not declared_active:
            self._mode = KEYRING_MODE_INVALID
            self._invalid_reason = (
                "AUDIT_HMAC_KEYRING_JSON.active_key_id or " "AUDIT_HMAC_ACTIVE_KEY_ID is required"
            )
            self._source = KEY_SOURCE_KEYRING_ENV
            return
        if declared_active not in loaded:
            self._mode = KEYRING_MODE_INVALID
            self._invalid_reason = (
                f"active_key_id '{declared_active}' is not in AUDIT_HMAC_KEYRING_JSON.keys"
            )
            self._source = KEY_SOURCE_KEYRING_ENV
            return
        self._keys = loaded
        self._active_key_id = declared_active
        self._mode = KEYRING_MODE_MULTI_KEYRING
        self._source = KEY_SOURCE_KEYRING_ENV

    def _load_legacy_single_key(self, raw_key: str, key_id: str | None) -> None:
        name = (key_id or "").strip() or DEFAULT_LEGACY_KEY_ID
        self._keys = {
            name: _KeyEntry(
                key_id=name,
                key_bytes=raw_key.encode("utf-8"),
                source=KEY_SOURCE_LEGACY_ENV,
            )
        }
        self._active_key_id = name
        self._mode = KEYRING_MODE_LEGACY_SINGLE_KEY
        self._source = KEY_SOURCE_LEGACY_ENV

    # ------------------------------------------------------------------
    # Public read API -- never returns key bytes
    # ------------------------------------------------------------------
    @property
    def mode(self) -> str:
        return self._mode

    @property
    def active_key_id(self) -> str | None:
        return self._active_key_id

    @property
    def known_key_ids(self) -> list[str]:
        return sorted(self._keys.keys())

    @property
    def invalid_reason(self) -> str | None:
        return self._invalid_reason

    @property
    def source(self) -> str:
        return self._source

    @property
    def configured(self) -> bool:
        return (
            self._mode
            in (
                KEYRING_MODE_LEGACY_SINGLE_KEY,
                KEYRING_MODE_MULTI_KEYRING,
            )
            and self._active_key_id is not None
        )

    @property
    def valid(self) -> bool:
        return self._mode != KEYRING_MODE_INVALID

    def has_key(self, key_id: str) -> bool:
        return key_id in self._keys

    def snapshot(self) -> KeyringSnapshot:
        return KeyringSnapshot(
            mode=self._mode,
            active_key_id=self._active_key_id,
            known_key_ids=self.known_key_ids,
            invalid_reason=self._invalid_reason,
            source=self._source,
        )

    def key_source(self, key_id: str) -> str:
        entry = self._keys.get(key_id)
        return entry.source if entry else KEY_SOURCE_UNKNOWN

    # ------------------------------------------------------------------
    # Internal -- only signer / verifier call these; never logged.
    # ------------------------------------------------------------------
    def _active_key_bytes(self) -> tuple[str, bytes] | None:
        if not self.configured:
            return None
        kid = self._active_key_id
        if kid is None:
            return None
        entry = self._keys.get(kid)
        if entry is None:
            return None
        return entry.key_id, entry.key_bytes

    def _key_bytes_for(self, key_id: str) -> bytes | None:
        entry = self._keys.get(key_id)
        return entry.key_bytes if entry else None


def keyring_metadata_rows(snapshot: KeyringSnapshot) -> list[dict[str, Any]]:
    """Return the per-key metadata rows we want to upsert.

    Each dict is safe to surface via operations endpoints. The key
    value is not present.
    """
    rows: list[dict[str, Any]] = []
    for kid in snapshot.known_key_ids:
        status = "active" if kid == snapshot.active_key_id else "inactive"
        rows.append(
            {
                "key_id": kid,
                "key_status": status,
                "source": snapshot.source,
            }
        )
    return rows


def iter_safe_key_ids(snapshot: KeyringSnapshot) -> Iterable[str]:
    return iter(snapshot.known_key_ids)


__all__ = [
    "KEYRING_MODE_NONE",
    "KEYRING_MODE_LEGACY_SINGLE_KEY",
    "KEYRING_MODE_MULTI_KEYRING",
    "KEYRING_MODE_INVALID",
    "KEY_SOURCE_LEGACY_ENV",
    "KEY_SOURCE_KEYRING_ENV",
    "KEY_SOURCE_SECRET_PROVIDER",
    "KEY_SOURCE_UNKNOWN",
    "DEFAULT_LEGACY_KEY_ID",
    "AuditHmacKeyring",
    "KeyringSnapshot",
    "iter_safe_key_ids",
    "keyring_metadata_rows",
]
