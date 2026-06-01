"""Stage 26 — static checks for the staging-secrets script trio."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BOOTSTRAP = _REPO_ROOT / "scripts" / "bootstrap_mock_vault_secrets.sh"
_ROTATION = _REPO_ROOT / "scripts" / "verify_secret_rotation_smoke.sh"
_LEAK_SCAN = _REPO_ROOT / "scripts" / "scan_for_secret_leaks.sh"
_VERIFY = _REPO_ROOT / "scripts" / "verify_staging_secrets.sh"
_LIST = _REPO_ROOT / "scripts" / "list_required_secrets.py"

_ALL = (_BOOTSTRAP, _ROTATION, _LEAK_SCAN, _VERIFY)


@pytest.fixture(scope="module")
def bash_path():
    path = shutil.which("bash")
    if path is None:
        pytest.skip("bash not available")
    return path


@pytest.mark.parametrize("script", _ALL + (_LIST,))
def test_script_exists(script):
    assert script.is_file()


@pytest.mark.parametrize("script", _ALL)
def test_bash_n_clean(bash_path, script):
    res = subprocess.run([bash_path, "-n", str(script)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_bootstrap_writes_to_local_gitignored_path():
    text = _BOOTSTRAP.read_text(encoding="utf-8")
    assert ".mock-vault-secrets.local.json" in text
    # Must chmod the file 600 (script uses chmod 600 or similar).
    assert "chmod 600" in text
    # Refuses to overwrite without ALLOW_OVERWRITE=true.
    assert "ALLOW_OVERWRITE" in text


def test_bootstrap_template_path_is_placeholder_only():
    template = _REPO_ROOT / "infra" / "runtime" / "mock-vault-secrets.example.json"
    text = template.read_text(encoding="utf-8")
    assert "PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE" in text
    # No real-token shapes.
    forbidden = (
        r"ghp_[A-Za-z0-9_]{16,}",
        r"github_pat_[A-Za-z0-9_]{16,}",
        r"xoxb-[A-Za-z0-9-]{8,}",
        r"sk-[A-Za-z0-9]{20,}",
    )
    for pat in forbidden:
        assert not re.search(pat, text), pat


def test_rotation_smoke_does_not_echo_password():
    text = _ROTATION.read_text(encoding="utf-8")
    assert "echo $POSTGRES_PASSWORD" not in text
    assert 'echo "$POSTGRES_PASSWORD"' not in text


def test_leak_scan_carries_forbidden_patterns():
    text = _LEAK_SCAN.read_text(encoding="utf-8")
    assert "ghp_" in text
    assert "github_pat_" in text
    assert "xoxb-" in text
    # Allow-list MUST mention PLACEHOLDER and ${...} placeholders.
    assert "PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE" in text


def test_verify_staging_secrets_runs_the_pipeline():
    text = _VERIFY.read_text(encoding="utf-8")
    assert "list_required_secrets.py" in text
    assert "bootstrap_mock_vault_secrets.sh" in text
    assert "validate_runtime_config.sh" in text
    assert "verify_secret_rotation_smoke.sh" in text
    assert "scan_for_secret_leaks.sh" in text
    assert "/operations/safety" in text


def test_no_real_secret_substring_in_any_script():
    forbidden = re.compile(
        r"ghp_[A-Za-z0-9_]{16,}"
        r"|github_pat_[A-Za-z0-9_]{16,}"
        r"|xoxb-[A-Za-z0-9-]{8,}"
        r"|sk-[A-Za-z0-9]{20,}"
    )
    # The leak scanner itself ships the documented mnemonic fixtures
    # in its allowlist; skip its own file from this meta-check.
    for script in _ALL:
        if script.name == "scan_for_secret_leaks.sh":
            continue
        text = script.read_text(encoding="utf-8")
        assert forbidden.search(text) is None, script.name
