"""Unit tests for scripts/validate_runtime_config.py.

The validator is exercised by importing it as a module — every test
passes a fixed env dict to ``evaluate`` so no shell / process env
matters. No real GitHub / Discord call is made.
"""

from __future__ import annotations

import sys

import pytest


@pytest.fixture(scope="module")
def validator():
    # conftest preloads scripts/validate_runtime_config.py under the
    # canonical "validate_runtime_config" module name. Reuse that single
    # instance to avoid the Python 3.14 dataclass re-registration race.
    return sys.modules["validate_runtime_config"]


def test_local_mode_clean_env_passes(validator):
    env = {
        "APP_ENV": "local",
        "POSTGRES_HOST_AUTH_METHOD": "trust",
        "VAULT_ADDR": "http://vault:8200",
        "RUN_REAL_GITHUB_TEST": "false",
        "RUN_REAL_DISCORD_TEST": "false",
    }
    report = validator.evaluate("local", env)
    assert report.passed is True
    assert all(f.severity != "fail" for f in report.findings)


def test_local_mode_real_github_inconsistent_fails(validator):
    env = {
        "APP_ENV": "local",
        "RUN_REAL_GITHUB_TEST": "true",
        "GITHUB_TEST_REPO": "",  # missing → fail
        "GITHUB_TOKEN": "x",
    }
    report = validator.evaluate("local", env)
    assert report.passed is False
    assert any(f.code == "real_github_test_missing_repo" for f in report.findings)


def test_local_mode_real_discord_inconsistent_fails(validator):
    env = {
        "APP_ENV": "local",
        "RUN_REAL_DISCORD_TEST": "true",
        "DISCORD_TEST_CHANNEL_ID": "",
        "DISCORD_BOT_TOKEN": "x",
    }
    report = validator.evaluate("local", env)
    assert report.passed is False
    assert any(f.code == "real_discord_missing_channel" for f in report.findings)


def test_staging_placeholder_secret_fails(validator):
    env = {
        "APP_ENV": "staging",
        "POSTGRES_PASSWORD": "PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE",
        "POSTGRES_HOST_AUTH_METHOD": "scram-sha-256",
        "VAULT_ADDR": "https://vault.staging.example",
    }
    report = validator.evaluate("staging", env)
    assert report.passed is False
    assert any(f.code == "placeholder_secret" for f in report.findings)


def test_staging_trust_auth_fails(validator):
    env = {
        "APP_ENV": "staging",
        "POSTGRES_PASSWORD": "real-pw",
        "POSTGRES_HOST_AUTH_METHOD": "trust",
        "VAULT_ADDR": "https://vault.staging.example",
    }
    report = validator.evaluate("staging", env)
    assert report.passed is False
    assert any(f.code == "postgres_trust_auth_forbidden" for f in report.findings)


def test_staging_vault_dev_mode_fails_without_escape(validator):
    env = {
        "APP_ENV": "staging",
        "POSTGRES_PASSWORD": "real-pw",
        "VAULT_ADDR": "http://vault:8200",  # local docker dev
    }
    report = validator.evaluate("staging", env)
    assert any(f.code == "vault_dev_mode_forbidden" for f in report.findings)
    assert report.passed is False


def test_staging_vault_dev_mode_warns_with_escape(validator):
    env = {
        "APP_ENV": "staging",
        "POSTGRES_PASSWORD": "real-pw",
        "VAULT_ADDR": "http://vault:8200",
        "ALLOW_VAULT_DEV_MODE_FOR_STAGING": "true",
    }
    report = validator.evaluate("staging", env)
    codes = {f.code: f.severity for f in report.findings}
    assert codes.get("vault_dev_mode_in_staging") == "warn"
    assert report.passed is True  # warning ≠ fail


def test_staging_real_github_test_enabled_info_not_fail(validator):
    env = {
        "APP_ENV": "staging",
        "POSTGRES_PASSWORD": "real-pw",
        "VAULT_ADDR": "https://vault.staging.example",
        "RUN_REAL_GITHUB_TEST": "true",
        "GITHUB_TEST_REPO": "owner/sandbox",
        "GITHUB_TOKEN": "ghp_real_sandbox_pat",
    }
    report = validator.evaluate("staging", env)
    codes = {f.code: f.severity for f in report.findings}
    # opt-in is logged at info level, never blocks
    assert codes.get("real_github_test_opt_in") == "info"
    assert report.passed is True


def test_production_check_vault_dev_mode_fails(validator):
    env = {
        "APP_ENV": "production-check",
        "POSTGRES_PASSWORD": "real-pw",
        "POSTGRES_HOST_AUTH_METHOD": "scram-sha-256",
        "VAULT_ADDR": "http://vault:8200",
        "ALERTMANAGER_WEBHOOK_URL": "https://hooks.example/x",
    }
    report = validator.evaluate("production-check", env)
    assert any(f.code == "vault_dev_mode_forbidden" for f in report.findings)
    assert report.passed is False


def test_production_check_trust_auth_fails(validator):
    env = {
        "APP_ENV": "production-check",
        "POSTGRES_PASSWORD": "real-pw",
        "POSTGRES_HOST_AUTH_METHOD": "trust",
        "VAULT_ADDR": "https://vault.example",
        "ALERTMANAGER_WEBHOOK_URL": "https://hooks.example/x",
    }
    report = validator.evaluate("production-check", env)
    assert any(f.code == "postgres_trust_auth_forbidden" for f in report.findings)


def test_production_check_alertmanager_missing_fails(validator):
    env = {
        "APP_ENV": "production-check",
        "POSTGRES_PASSWORD": "real-pw",
        "POSTGRES_HOST_AUTH_METHOD": "scram-sha-256",
        "VAULT_ADDR": "https://vault.example",
        "ALERTMANAGER_WEBHOOK_URL": "",
    }
    report = validator.evaluate("production-check", env)
    assert any(f.code == "alertmanager_receiver_missing" for f in report.findings)


def test_production_check_production_executed_sentinel_fails(validator):
    env = {
        "APP_ENV": "production-check",
        "POSTGRES_PASSWORD": "real-pw",
        "POSTGRES_HOST_AUTH_METHOD": "scram-sha-256",
        "VAULT_ADDR": "https://vault.example",
        "ALERTMANAGER_WEBHOOK_URL": "https://hooks.example/x",
        "PRODUCTION_EXECUTED_TRUE_COUNT": "1",
    }
    report = validator.evaluate("production-check", env)
    assert any(f.code == "production_executed_true" for f in report.findings)


def test_invalid_mode_fails(validator):
    env = {"APP_ENV": "local"}
    report = validator.evaluate("nonsense", env)
    assert report.passed is False
    assert any(f.code == "invalid_mode" for f in report.findings)


def test_findings_never_include_secret_values(validator):
    """No matter the failure, message + field carry no secret-shaped substring."""
    env = {
        "APP_ENV": "staging",
        "POSTGRES_PASSWORD": "PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE",
        "GITHUB_TOKEN": "ghp_pleaseneverleak",
        "VAULT_ADDR": "http://vault:8200",
        "POSTGRES_HOST_AUTH_METHOD": "trust",
        "DISCORD_BOT_TOKEN": "discord-secret-please-never-leak",
    }
    report = validator.evaluate("staging", env)
    for finding in report.findings:
        assert "ghp_pleaseneverleak" not in finding.message
        assert "discord-secret-please-never-leak" not in finding.message
