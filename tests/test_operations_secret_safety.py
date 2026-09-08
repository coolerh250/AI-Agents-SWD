"""Stage 26 — /operations/safety surfaces secret_provider fields safely."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_operations_module():
    """Load apps/orchestrator/src/operations.py with shims that satisfy its
    eager imports (no DB / Redis / observability needed for the helper
    we're testing)."""
    src = _REPO_ROOT / "apps" / "orchestrator" / "src"
    sys.path.insert(0, str(src))
    try:
        # First, make sure ``progress`` (a sibling of operations.py) is
        # importable. operations does ``from progress import ...``.
        import importlib.util as iu

        prog_path = src / "progress.py"
        spec = iu.spec_from_file_location("progress", prog_path)
        if spec and spec.loader:
            mod = iu.module_from_spec(spec)
            sys.modules.setdefault("progress", mod)
            spec.loader.exec_module(mod)

        spec2 = iu.spec_from_file_location("orchestrator_operations", src / "operations.py")
        if spec2 is None or spec2.loader is None:
            pytest.skip("operations.py not loadable")
        mod2 = iu.module_from_spec(spec2)
        spec2.loader.exec_module(mod2)
        return mod2
    finally:
        sys.path.pop(0)


@pytest.fixture(scope="module")
def operations_module():
    try:
        return _load_operations_module()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"could not load operations module: {exc}")


def test_secret_provider_status_helper_default(operations_module, monkeypatch):
    """When SECRET_PROVIDER isn't set, default to env and report no Vault."""
    monkeypatch.delenv("SECRET_PROVIDER", raising=False)
    monkeypatch.delenv("VAULT_ADDR", raising=False)
    monkeypatch.delenv("VAULT_TOKEN", raising=False)
    info = operations_module._secret_provider_status()
    assert info["secret_provider"] == "env"
    assert info["vault_configured"] is False
    assert info["vault_reachable"] is False
    assert info["mock_vault_enabled"] is False
    assert "missing_required_secrets" in info


def test_secret_provider_status_mock_vault(operations_module, monkeypatch, tmp_path):
    fake = tmp_path / "mv.json"
    fake.write_text('{"POSTGRES_PASSWORD": "x"}', encoding="utf-8")
    monkeypatch.setenv("SECRET_PROVIDER", "mock-vault")
    monkeypatch.setenv("MOCK_VAULT_SECRETS_FILE", str(fake))
    # Reset SDK singleton so the new env shows up
    from shared.sdk.secrets import reset_default_provider

    reset_default_provider()
    info = operations_module._secret_provider_status()
    assert info["secret_provider"] == "mock-vault"
    assert info["mock_vault_enabled"] is True
    assert info["mock_vault_file_present"] is True


def test_secret_provider_status_never_returns_value(operations_module, monkeypatch, tmp_path):
    fake = tmp_path / "mv.json"
    fake.write_text('{"POSTGRES_PASSWORD": "NEVER-EXPOSE-IN-STATUS"}', encoding="utf-8")
    monkeypatch.setenv("SECRET_PROVIDER", "mock-vault")
    monkeypatch.setenv("MOCK_VAULT_SECRETS_FILE", str(fake))
    from shared.sdk.secrets import reset_default_provider

    reset_default_provider()
    info = operations_module._secret_provider_status()
    assert "NEVER-EXPOSE-IN-STATUS" not in repr(info)


# AT-M3.6B.2 Runtime Image Alignment Safety Surface Remediation -- a fresh
# VaultKvSecretProvider's `.status["reachable"]` reflects only whatever its own
# internal cache already holds. `_secret_provider_status()` used to read
# `.status` before anything had triggered a lookup, so a brand-new provider
# (which is what `provider_from_env()` always returns -- never the same
# instance twice) reported `vault_reachable=False` even against a fully
# reachable Vault. These tests drive `_secret_provider_status()` itself,
# end to end, against a stubbed Vault HTTP layer -- no real Vault needed --
# to prove the fix without relying on a live server.


def _install_fake_vault_provider(monkeypatch, *, reachable: bool) -> None:
    """Make `shared.sdk.secrets.provider_from_env` return a `VaultKvSecretProvider`
    talking to a stubbed Vault that either answers every read or refuses all of them --
    a fresh instance, exactly like production's `provider_from_env()` call."""
    import shared.sdk.secrets as secrets_pkg
    from shared.sdk.secrets.provider import VaultKvSecretProvider
    from shared.sdk.secrets.models import SecretRef

    def _getter(url: str, headers: dict, timeout: float) -> tuple[int, dict]:
        if reachable:
            return 200, {"data": {"data": {"ANTHROPIC_API_KEY": "PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE"}}}
        return 503, {}

    def _fake_provider_from_env(env=None):
        return VaultKvSecretProvider(
            addr="http://vault:8200",
            token_ref=SecretRef(name="VAULT_TOKEN", _value="scoped-token", present=True),
            mount="secret",
            path="aiagents/test-runtime",
            http_getter=_getter,
        )

    monkeypatch.setattr(secrets_pkg, "provider_from_env", _fake_provider_from_env)


def test_secret_provider_status_reachable_vault_reports_true(operations_module, monkeypatch):
    """A fresh provider against a Vault that actually answers must report reachable=True --
    not just after some earlier, unrelated call has happened to warm its cache."""
    monkeypatch.setenv("SECRET_PROVIDER", "vault")
    monkeypatch.setenv("VAULT_TOKEN", "scoped-token")
    _install_fake_vault_provider(monkeypatch, reachable=True)
    info = operations_module._secret_provider_status()
    assert info["vault_reachable"] is True


def test_secret_provider_status_unreachable_vault_reports_false(operations_module, monkeypatch):
    """An actually-unreachable Vault must still report reachable=False -- the fix must not
    flip the field to an unconditional True."""
    monkeypatch.setenv("SECRET_PROVIDER", "vault")
    monkeypatch.setenv("VAULT_TOKEN", "scoped-token")
    _install_fake_vault_provider(monkeypatch, reachable=False)
    info = operations_module._secret_provider_status()
    assert info["vault_reachable"] is False


def test_secret_provider_status_does_not_depend_on_a_prior_unrelated_lookup(
    operations_module, monkeypatch
):
    """A single, cold call to `_secret_provider_status()` must be truthful on its own -- the
    result must not depend on some earlier caller having already exercised the provider."""
    monkeypatch.setenv("SECRET_PROVIDER", "vault")
    monkeypatch.setenv("VAULT_TOKEN", "scoped-token")
    _install_fake_vault_provider(monkeypatch, reachable=True)
    # No warm-up call of any kind before this -- the helper must reach the same
    # truthful answer entirely within its own single invocation.
    info = operations_module._secret_provider_status()
    assert info["vault_reachable"] is True


def test_vault_token_missing_required_secrets_checks_environment_not_kv_document(
    operations_module, monkeypatch
):
    """VAULT_TOKEN is the credential Vault is reached WITH, never a field Vault stores about
    itself. A Vault-backed provider whose KV document holds only ANTHROPIC_API_KEY must not
    report VAULT_TOKEN missing merely because it isn't a KV field."""
    monkeypatch.setenv("SECRET_PROVIDER", "vault")
    monkeypatch.setenv("VAULT_TOKEN", "scoped-token")
    _install_fake_vault_provider(monkeypatch, reachable=True)
    info = operations_module._secret_provider_status()
    assert "VAULT_TOKEN" not in info["missing_required_secrets"]


def test_vault_token_absent_from_environment_is_still_reported_missing(
    operations_module, monkeypatch
):
    """The environment-based check must still fail closed: no VAULT_TOKEN in the environment
    is still a genuinely missing required secret."""
    monkeypatch.setenv("SECRET_PROVIDER", "vault")
    monkeypatch.delenv("VAULT_TOKEN", raising=False)
    _install_fake_vault_provider(monkeypatch, reachable=True)
    info = operations_module._secret_provider_status()
    assert "VAULT_TOKEN" in info["missing_required_secrets"]
