"""Stage 24 secrets baseline.

Public surface kept intentionally small — every consumer should treat
secrets as opaque tokens. Importable symbols:

* :class:`SecretProvider` — env-backed default, Vault placeholder ready.
* :class:`SecretRef` — type-safe handle that never serialises the value.
* :func:`redact`, :func:`redact_mapping` — render helpers that return
  ``***REDACTED***`` for anything that smells like a secret.

The Vault provider in this module is a placeholder. It does not contact
a real Vault server; Stage 24 only nails down the interface so a real
provider can swap in later without touching any caller.
"""

from shared.sdk.secrets.models import REDACTION_TOKEN, SecretRef
from shared.sdk.secrets.provider import (
    EnvSecretProvider,
    SecretProvider,
    VaultPlaceholderProvider,
    default_provider,
    redact,
    redact_mapping,
)

__all__ = [
    "REDACTION_TOKEN",
    "SecretRef",
    "EnvSecretProvider",
    "SecretProvider",
    "VaultPlaceholderProvider",
    "default_provider",
    "redact",
    "redact_mapping",
]
