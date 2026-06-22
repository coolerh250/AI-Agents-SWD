"""Step 53 -- reference-only SecretRef schema."""

from __future__ import annotations

from shared.sdk.secrets_foundation import SecretRef


def test_no_inline_value_field() -> None:
    fields = set(SecretRef.model_fields)
    assert not ({"value", "secret", "token", "password"} & fields)
    assert fields == {"store", "name", "key", "version", "required", "production_allowed"}


def test_disabled_store_not_production_ready() -> None:
    r = SecretRef(store="disabled", name="", key="", required=True)
    assert r.configured is False
    assert r.production_ready is False


def test_configured_requires_name_and_key() -> None:
    assert SecretRef(store="vault_ref", name="a", key="").configured is False
    assert SecretRef(store="vault_ref", name="a", key="k").configured is True


def test_production_ready_requires_allowed_and_configured() -> None:
    assert (
        SecretRef(store="vault_ref", name="a", key="k", production_allowed=False).production_ready
        is False
    )
    assert (
        SecretRef(store="vault_ref", name="a", key="k", production_allowed=True).production_ready
        is True
    )
    # disabled store is never production-ready even if allowed
    assert (
        SecretRef(store="disabled", name="a", key="k", production_allowed=True).production_ready
        is False
    )
