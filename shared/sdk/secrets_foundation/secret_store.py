"""Step 53 -- secret store abstraction (interface only, NO value access).

Defines the provider surface a future production step would implement. In Step 53
there is NO concrete provider that connects to a real store, and ANY live value
read raises ``SecretValueAccessDisabledError``. Only metadata / reference
validation is permitted.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from shared.sdk.secrets_foundation.secret_ref import SecretRef
from shared.sdk.secrets_foundation.secret_store_models import (
    SecretMetadata,
    SecretValueAccessDisabledError,
)


@runtime_checkable
class SecretStoreProvider(Protocol):
    def get_secret_metadata(self, ref: SecretRef) -> SecretMetadata: ...

    def read_secret_value(self, ref: SecretRef) -> str: ...


class DisabledSecretStoreProvider:
    """The only provider in Step 53. Returns metadata; never a value."""

    provider = "disabled"

    def get_secret_metadata(self, ref: SecretRef) -> SecretMetadata:
        return SecretMetadata(
            store=ref.store,
            name=ref.name,
            key=ref.key,
            version=ref.version,
            configured=ref.configured,
            production_ready=ref.production_ready,
        )

    def read_secret_value(self, ref: SecretRef) -> str:
        raise SecretValueAccessDisabledError(
            "secret value access is disabled in Step 53 (no production secret store)"
        )


__all__ = [
    "SecretStoreProvider",
    "DisabledSecretStoreProvider",
    "SecretMetadata",
    "SecretValueAccessDisabledError",
]
