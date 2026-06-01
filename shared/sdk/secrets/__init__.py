"""Secrets baseline — env / Vault KV v2 / file-backed mock-vault.

Public surface kept intentionally small — every consumer should treat
secrets as opaque tokens. Importable symbols:

* :class:`SecretProvider` — abstract base.
* :class:`EnvSecretProvider` — reads ``os.environ``.
* :class:`VaultKvSecretProvider` — reads Vault KV v2 over HTTP.
* :class:`MockVaultSecretProvider` — reads a local JSON file used by
  staging validation. Refuses values matching known real-token shapes
  unless the operator opts in.
* :class:`VaultPlaceholderProvider` — Stage 24 placeholder, kept so old
  imports still work.
* :class:`SecretRef` — type-safe handle that never serialises the value.
* :func:`provider_from_env`, :func:`default_provider`,
  :func:`reset_default_provider` — factory + singleton helpers.
* :func:`redact`, :func:`redact_mapping` — render helpers that return
  ``***REDACTED***`` for anything that smells like a secret.
"""

from shared.sdk.secrets.models import REDACTION_TOKEN, SecretRef
from shared.sdk.secrets.provider import (
    SUPPORTED_PROVIDERS,
    EnvSecretProvider,
    MockVaultSecretProvider,
    SecretProvider,
    VaultKvSecretProvider,
    VaultPlaceholderProvider,
    default_provider,
    looks_like_placeholder,
    provider_from_env,
    redact,
    redact_mapping,
    reset_default_provider,
)

__all__ = [
    "REDACTION_TOKEN",
    "SUPPORTED_PROVIDERS",
    "SecretRef",
    "EnvSecretProvider",
    "MockVaultSecretProvider",
    "SecretProvider",
    "VaultKvSecretProvider",
    "VaultPlaceholderProvider",
    "default_provider",
    "looks_like_placeholder",
    "provider_from_env",
    "redact",
    "redact_mapping",
    "reset_default_provider",
]
