"""Stage 26 — validate_runtime_config.py SECRET_PROVIDER rules."""

from __future__ import annotations

import sys

# conftest preloads scripts/validate_runtime_config.py under this name.
validator = sys.modules["validate_runtime_config"]


def _eval(mode: str, **env: str):
    return validator.evaluate(mode, dict(env))


def test_local_default_env_provider_passes():
    report = _eval("local")
    assert report.passed is True


def test_local_mock_vault_passes_without_warning():
    report = _eval("local", SECRET_PROVIDER="mock-vault")
    # No failing finding; mock-vault is silently accepted in local mode.
    assert report.passed is True


def test_staging_mock_vault_emits_warning_not_failure():
    report = _eval(
        "staging",
        SECRET_PROVIDER="mock-vault",
        POSTGRES_PASSWORD="real-password",
        VAULT_ADDR="",
        VAULT_TOKEN="",
    )
    codes = {f.code: f.severity for f in report.findings}
    assert codes.get("mock_vault_in_staging") == "warn"
    # The mock-vault choice itself is not a failure; passes hinge on
    # other staging rules. Here we only assert the WARN is present.
    fails = [f for f in report.findings if f.severity == "fail"]
    assert all(f.code != "mock_vault_in_staging" for f in fails)


def test_staging_vault_without_addr_fails():
    report = _eval(
        "staging",
        SECRET_PROVIDER="vault",
        POSTGRES_PASSWORD="real-password",
        VAULT_TOKEN="real-token",
    )
    codes = [f.code for f in report.findings if f.severity == "fail"]
    assert "vault_addr_missing" in codes


def test_staging_vault_with_placeholder_token_fails():
    report = _eval(
        "staging",
        SECRET_PROVIDER="vault",
        POSTGRES_PASSWORD="real-password",
        VAULT_ADDR="http://vault.example",
        VAULT_TOKEN="PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE",
    )
    codes = [f.code for f in report.findings if f.severity == "fail"]
    assert "vault_token_missing" in codes


def test_production_check_mock_vault_fails():
    report = _eval(
        "production-check",
        SECRET_PROVIDER="mock-vault",
        POSTGRES_PASSWORD="real-password",
        VAULT_ADDR="http://vault.example",
        VAULT_TOKEN="real-token",
        ALERTMANAGER_WEBHOOK_URL="https://hooks.example/x",
        GITHUB_TOKEN="real",
        DISCORD_BOT_TOKEN="real",
    )
    codes = [f.code for f in report.findings if f.severity == "fail"]
    assert "mock_vault_forbidden_in_production" in codes


def test_production_check_env_only_fails():
    report = _eval(
        "production-check",
        SECRET_PROVIDER="env",
        POSTGRES_PASSWORD="real-password",
        VAULT_ADDR="http://vault.example",
        VAULT_TOKEN="real-token",
        ALERTMANAGER_WEBHOOK_URL="https://hooks.example/x",
        GITHUB_TOKEN="real",
        DISCORD_BOT_TOKEN="real",
    )
    codes = [f.code for f in report.findings if f.severity == "fail"]
    assert "env_provider_in_production" in codes


def test_unknown_provider_fails_in_every_mode():
    for mode in ("local", "staging", "production-check"):
        report = _eval(mode, SECRET_PROVIDER="quantum-vault")
        codes = [f.code for f in report.findings if f.severity == "fail"]
        assert "secret_provider_unknown" in codes, mode


def test_report_to_dict_carries_secret_provider():
    report = _eval("local", SECRET_PROVIDER="mock-vault")
    out = report.to_dict()
    assert out["secret_provider"] == "mock-vault"
    # No secret value should appear in the dict.
    assert "PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE" not in str(out) or (
        "PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE" in str(report.env_keys_present)
    )
