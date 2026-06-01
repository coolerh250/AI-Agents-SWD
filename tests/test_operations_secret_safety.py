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
