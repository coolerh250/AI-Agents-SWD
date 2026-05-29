"""Stage 24 unit tests for shared.sdk.secrets.

Every test runs against an :class:`EnvSecretProvider` driven by a dict
so no live env / network is touched. The Vault placeholder is exercised
through its public interface — by construction it cannot return a value.
"""

from __future__ import annotations

from shared.sdk.secrets import (
    REDACTION_TOKEN,
    EnvSecretProvider,
    SecretRef,
    VaultPlaceholderProvider,
    redact,
    redact_mapping,
)
from shared.sdk.secrets.provider import looks_like_placeholder


def test_env_provider_returns_present_ref_for_real_value():
    p = EnvSecretProvider({"GITHUB_TOKEN": "ghp_real_value"})
    ref = p.get_secret("GITHUB_TOKEN")
    assert isinstance(ref, SecretRef)
    assert ref.present is True
    assert ref.reveal() == "ghp_real_value"
    assert bool(ref) is True


def test_env_provider_missing_var_is_absent():
    p = EnvSecretProvider({})
    ref = p.get_secret("GITHUB_TOKEN")
    assert ref.present is False
    assert ref.reveal() == ""
    assert bool(ref) is False


def test_env_provider_placeholder_is_absent():
    """The literal placeholder marker MUST be treated as 'not set' so a
    half-configured staging env doesn't fool the platform into thinking
    a token is present."""
    p = EnvSecretProvider({"GITHUB_TOKEN": "PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE"})
    ref = p.get_secret("GITHUB_TOKEN")
    assert ref.present is False
    assert ref.reveal() == ""


def test_env_provider_strips_whitespace():
    p = EnvSecretProvider({"GITHUB_TOKEN": "  ghp_value  "})
    ref = p.get_secret("GITHUB_TOKEN")
    assert ref.reveal() == "ghp_value"


def test_secret_ref_repr_and_str_redact():
    p = EnvSecretProvider({"GITHUB_TOKEN": "ghp_NEVER_LEAK"})
    ref = p.get_secret("GITHUB_TOKEN")
    assert "ghp_NEVER_LEAK" not in repr(ref)
    assert REDACTION_TOKEN in repr(ref)
    assert str(ref) == REDACTION_TOKEN


def test_secret_ref_model_dump_redacts():
    p = EnvSecretProvider({"GITHUB_TOKEN": "ghp_NEVER_LEAK"})
    ref = p.get_secret("GITHUB_TOKEN")
    dumped = ref.model_dump()
    assert dumped["value"] == REDACTION_TOKEN
    assert "ghp_NEVER_LEAK" not in str(dumped)
    assert dumped["name"] == "GITHUB_TOKEN"
    assert dumped["present"] is True


def test_redact_returns_token_for_truthy_value():
    assert redact("anything") == REDACTION_TOKEN
    assert redact(123) == REDACTION_TOKEN


def test_redact_returns_empty_for_falsy_value():
    assert redact("") == ""
    assert redact(None) == ""


def test_redact_mapping_secret_shaped_keys():
    out = redact_mapping(
        {
            "GITHUB_TOKEN": "ghp_X",
            "DISCORD_BOT_TOKEN": "discord-X",
            "VAULT_TOKEN": "vault-X",
            "POSTGRES_PASSWORD": "pw",
            "API_KEY": "k",
            "PUBLIC_URL": "https://example",
            "REDIS_URL": "redis://r",
        }
    )
    assert out["GITHUB_TOKEN"] == REDACTION_TOKEN
    assert out["DISCORD_BOT_TOKEN"] == REDACTION_TOKEN
    assert out["VAULT_TOKEN"] == REDACTION_TOKEN
    assert out["POSTGRES_PASSWORD"] == REDACTION_TOKEN
    assert out["API_KEY"] == REDACTION_TOKEN
    assert out["PUBLIC_URL"] == "https://example"
    assert out["REDIS_URL"] == "redis://r"


def test_redact_mapping_extra_keys():
    out = redact_mapping({"my_alias": "secret"}, extra_keys=["my_alias"])
    assert out["my_alias"] == REDACTION_TOKEN


def test_redact_mapping_preserves_empty_values():
    out = redact_mapping({"GITHUB_TOKEN": ""})
    # empty string isn't redacted — it carries no secret to leak
    assert out["GITHUB_TOKEN"] == ""


def test_vault_placeholder_provider_returns_absent():
    p = VaultPlaceholderProvider(vault_addr="http://vault:8200")
    ref = p.get_secret("GITHUB_TOKEN")
    assert ref.present is False
    assert ref.reveal() == ""
    assert p.has_secret("GITHUB_TOKEN") is False


def test_looks_like_placeholder_helper():
    assert looks_like_placeholder("PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE") is True
    assert looks_like_placeholder("ghp_real") is False
    assert looks_like_placeholder(None) is False
    assert looks_like_placeholder("") is False
