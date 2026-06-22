"""Step 53 -- secret store abstraction (no value access)."""

from __future__ import annotations

import pytest

from shared.sdk.secrets_foundation import (
    DisabledSecretStoreProvider,
    SecretRef,
    SecretStoreProvider,
    SecretValueAccessDisabledError,
)


def test_provider_satisfies_protocol() -> None:
    assert isinstance(DisabledSecretStoreProvider(), SecretStoreProvider)


def test_metadata_has_no_value() -> None:
    md = DisabledSecretStoreProvider().get_secret_metadata(
        SecretRef(store="disabled", name="", key="")
    )
    assert md.configured is False
    assert md.production_ready is False
    assert "value" not in md.model_dump()


def test_read_value_raises() -> None:
    with pytest.raises(SecretValueAccessDisabledError):
        DisabledSecretStoreProvider().read_secret_value(
            SecretRef(store="vault_ref", name="a", key="k")
        )
