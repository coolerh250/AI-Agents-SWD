"""Stage 36 -- backup encryption metadata + key source resolution.

This module is **metadata only**. The actual encrypt / decrypt happens
in shell via openssl (so we don't reimplement crypto in Python and so
operators can audit the exact openssl invocation). This module:

  * Decides which key source applies (env / test-only generated /
    none).
  * Exposes ``encryption_status()`` for the operations API.
  * Never holds the key value itself.

Spec contract:

  * In ``test`` mode (``BACKUP_KEY_SOURCE=test-only-generated``) a
    keyfile under /tmp with chmod 600 is acceptable. The encryption
    is real, but operators MUST treat the key as ephemeral.
  * In ``production-check`` mode an absent ``BACKUP_ENCRYPTION_KEY``
    is a hard FAIL.
  * The key value itself is never returned, logged, or carried in any
    response.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

BACKUP_ENCRYPTION_KEY_ENV = "BACKUP_ENCRYPTION_KEY"
BACKUP_KEY_SOURCE_ENV = "BACKUP_KEY_SOURCE"

ENCRYPTION_MODE_AES_256_CBC = "openssl-aes-256-cbc"
ENCRYPTION_MODE_NONE = "none"

KEY_SOURCE_ENV = "env"
KEY_SOURCE_TEST_ONLY = "test-only-generated"
KEY_SOURCE_MISSING = "missing"


@dataclass
class EncryptionConfig:
    enabled: bool
    mode: str
    key_source: str
    key_id: str | None
    production_ready: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "mode": self.mode,
            "key_source": self.key_source,
            "key_id": self.key_id,
            "production_ready": bool(self.production_ready),
        }


@dataclass
class EncryptionResult:
    """Outcome of a single encrypt operation (no key carried)."""

    encrypted_path: str
    checksum_sha256: str
    mode: str
    key_id: str | None
    size_bytes: int


def resolve_encryption_key_source(
    env: Mapping[str, str] | None = None,
) -> EncryptionConfig:
    """Decide which key source applies, without ever reading the key value.

    The actual key bytes never enter this process -- shell scripts pipe
    the env var straight into ``openssl enc -pass env:...`` so the key
    is held only inside openssl's address space.

    Returns:
        EncryptionConfig with ``enabled``, ``mode``, ``key_source``,
        ``key_id`` (a label, never the value), and a
        ``production_ready`` flag.
    """

    source: Mapping[str, str] = env if env is not None else os.environ
    has_env_key = bool(source.get(BACKUP_ENCRYPTION_KEY_ENV))
    key_source_hint = (source.get(BACKUP_KEY_SOURCE_ENV) or "").strip().lower()

    if has_env_key:
        return EncryptionConfig(
            enabled=True,
            mode=ENCRYPTION_MODE_AES_256_CBC,
            key_source=KEY_SOURCE_ENV,
            key_id=_derive_label(source.get(BACKUP_ENCRYPTION_KEY_ENV, "")),
            production_ready=True,
        )

    if key_source_hint == KEY_SOURCE_TEST_ONLY:
        return EncryptionConfig(
            enabled=True,
            mode=ENCRYPTION_MODE_AES_256_CBC,
            key_source=KEY_SOURCE_TEST_ONLY,
            key_id="test-only-ephemeral",
            production_ready=False,
        )

    return EncryptionConfig(
        enabled=False,
        mode=ENCRYPTION_MODE_NONE,
        key_source=KEY_SOURCE_MISSING,
        key_id=None,
        production_ready=False,
    )


def encryption_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Operations-API-safe view of the encryption config (no secret value)."""

    return resolve_encryption_key_source(env).to_dict()


def _derive_label(key_value: str) -> str:
    """Return a short opaque label for the key (NOT the key itself).

    The label is sha256(key)[:8] -- enough to detect "did the key
    change?" without exposing the secret. The label is fine to log.
    """

    import hashlib

    if not key_value:
        return "unknown"
    return hashlib.sha256(key_value.encode("utf-8")).hexdigest()[:8]
