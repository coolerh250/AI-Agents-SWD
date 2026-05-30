"""Stage 25 static checks for the staging-runtime script trio.

Tests assert syntax + safety properties without actually running the
scripts (the cluster verify scripts cover the end-to-end PASS). Bash
syntax is checked via ``bash -n``. Key safety constants are pinned by
string match.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_START = _REPO_ROOT / "scripts" / "start_staging_runtime.sh"
_STOP = _REPO_ROOT / "scripts" / "stop_staging_runtime.sh"
_CHECK = _REPO_ROOT / "scripts" / "check_staging_runtime.sh"
_VERIFY = _REPO_ROOT / "scripts" / "verify_staging_runtime.sh"
_BACKUP_VERIFY = _REPO_ROOT / "scripts" / "verify_staging_backup_restore.sh"

_ALL = (_START, _STOP, _CHECK, _VERIFY, _BACKUP_VERIFY)


@pytest.fixture(scope="module")
def bash_path():
    path = shutil.which("bash")
    if path is None:
        pytest.skip("bash not available")
    return path


@pytest.mark.parametrize("script", _ALL)
def test_script_exists(script):
    assert script.is_file()


@pytest.mark.parametrize("script", _ALL)
def test_script_bash_n_syntax_clean(bash_path, script):
    res = subprocess.run([bash_path, "-n", str(script)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_start_script_uses_staging_compose_project():
    text = _START.read_text(encoding="utf-8")
    assert "aiagents-staging" in text
    # Must invoke compose with -p to keep the project separate.
    assert "docker compose -p" in text


def test_start_script_validates_before_up():
    text = _START.read_text(encoding="utf-8")
    # validate_runtime_config.sh must run before the compose up.
    assert text.find("validate_runtime_config.sh") != -1
    # rudimentary ordering check: validate appears earlier in the file
    assert text.find("validate_runtime_config.sh") < text.find("up -d")


def test_start_script_applies_migrations():
    text = _START.read_text(encoding="utf-8")
    assert "migrations/*.sql" in text
    assert "psql -U" in text


def test_stop_script_supports_purge_flag():
    text = _STOP.read_text(encoding="utf-8")
    assert "--volumes" in text or "--purge" in text
    assert "down" in text


def test_stop_script_does_not_force_purge_by_default():
    text = _STOP.read_text(encoding="utf-8")
    # Purge requires an explicit --volumes/--purge flag.
    assert "PURGE=0" in text
    assert "PURGE=1" in text


def test_check_script_uses_staging_ports():
    text = _CHECK.read_text(encoding="utf-8")
    # Staging port offset +10000 — orchestrator must show on 18000.
    assert "18000" in text
    assert "18007" in text  # discord-gateway
    assert "18005" in text  # github-automation


def test_verify_script_runs_e2e_workflow():
    text = _VERIFY.read_text(encoding="utf-8")
    assert "/discord/messages" in text
    assert "/workflow/progress/" in text
    assert "/operations/workflows/" in text
    assert "/operations/safety" in text


def test_verify_script_default_action_is_down():
    text = _VERIFY.read_text(encoding="utf-8")
    assert 'ACTION="down"' in text
    assert "--keep-running" in text
    # The verify script invokes stop_staging_runtime.sh in the default path.
    assert "stop_staging_runtime.sh" in text


def test_verify_backup_script_guards_local_test_dataset():
    """The staging backup verifier samples local/test table count before
    and after to assert the staging operation never touches the
    aiagents-test project's DB.
    """
    text = _BACKUP_VERIFY.read_text(encoding="utf-8")
    assert "aiagents-test" in text
    assert "local_before" in text and "local_after" in text


def test_no_real_secret_substring_in_any_script():
    forbidden = re.compile(
        r"ghp_[A-Za-z0-9_]{16,}"
        r"|github_pat_[A-Za-z0-9_]{16,}"
        r"|Bearer [A-Za-z0-9._-]{30,}"
        r"|Bot [A-Za-z0-9._-]{30,}"
    )
    for script in _ALL:
        body = script.read_text(encoding="utf-8")
        assert forbidden.search(body) is None, f"token-shaped substring in {script.name}"


def test_no_script_echoes_postgres_password():
    """The staging password must NEVER appear in a verify-script stdout
    line. The scripts only read it via env-file substitution; the
    script bodies must not echo ``$POSTGRES_PASSWORD``.
    """
    for script in _ALL:
        text = script.read_text(encoding="utf-8")
        assert "echo $POSTGRES_PASSWORD" not in text
        assert 'echo "$POSTGRES_PASSWORD"' not in text
        assert "printf %s $POSTGRES_PASSWORD" not in text
