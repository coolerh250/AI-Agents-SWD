"""Step 53 -- SecretRef rejects inline secret values (assembled at runtime)."""

from __future__ import annotations

import pytest

from shared.sdk.secrets_foundation import SecretRef, validate_ref_dict


def test_inline_jwt_rejected() -> None:
    jwt = "eyJ" + "a" * 20 + "." + "b" * 20 + "." + "c" * 20
    with pytest.raises(Exception):
        SecretRef(store="vault_ref", name="x", key=jwt)


def test_inline_private_key_rejected() -> None:
    pk = "-----BEGIN RSA " + "PRIVATE KEY-----"
    with pytest.raises(Exception):
        SecretRef(store="vault_ref", name=pk, key="k")


def test_inline_github_token_rejected() -> None:
    tok = "ghp_" + "A" * 30
    with pytest.raises(Exception):
        SecretRef(store="vault_ref", name="x", key=tok)


def test_validate_ref_dict_rejects_value_field() -> None:
    assert validate_ref_dict({"name": "ok", "value": "X" * 12})
    assert validate_ref_dict({"name": "ok", "client_secret": "Y" * 12})


def test_clean_ref_dict_passes() -> None:
    assert validate_ref_dict({"store": "disabled", "name": "", "key": ""}) == []
