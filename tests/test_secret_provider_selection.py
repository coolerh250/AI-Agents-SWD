"""Stage 26 — SECRET_PROVIDER factory selection."""

from __future__ import annotations

from shared.sdk.secrets import (
    EnvSecretProvider,
    MockVaultSecretProvider,
    VaultKvSecretProvider,
    provider_from_env,
)


def test_default_selects_env_provider():
    assert isinstance(provider_from_env({}), EnvSecretProvider)


def test_env_choice_returns_env_provider():
    assert isinstance(provider_from_env({"SECRET_PROVIDER": "env"}), EnvSecretProvider)


def test_vault_choice_returns_vault_provider():
    assert isinstance(
        provider_from_env({"SECRET_PROVIDER": "vault", "VAULT_ADDR": "http://v:8200"}),
        VaultKvSecretProvider,
    )


def test_mock_vault_choice_returns_mock_provider():
    assert isinstance(provider_from_env({"SECRET_PROVIDER": "mock-vault"}), MockVaultSecretProvider)


def test_unknown_choice_falls_back_to_env_provider():
    # Factory never raises — unknown values degrade safely to env.
    assert isinstance(provider_from_env({"SECRET_PROVIDER": "nope"}), EnvSecretProvider)


def test_factory_is_case_insensitive():
    assert isinstance(provider_from_env({"SECRET_PROVIDER": "MOCK-VAULT"}), MockVaultSecretProvider)
    assert isinstance(
        provider_from_env({"SECRET_PROVIDER": "Vault", "VAULT_ADDR": "x"}),
        VaultKvSecretProvider,
    )
