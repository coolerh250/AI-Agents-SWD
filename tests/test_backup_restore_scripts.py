"""Stage 24 static checks for the backup/restore script trio.

Tests assert syntax + safety properties without actually running the
scripts. Bash syntax is checked via ``bash -n``. The restore script's
opt-in guards are verified by string match against the source.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKUP = _REPO_ROOT / "scripts" / "backup_postgres.sh"
_RESTORE = _REPO_ROOT / "scripts" / "restore_postgres.sh"
_VERIFY = _REPO_ROOT / "scripts" / "verify_backup_restore.sh"


def _bash() -> str | None:
    return shutil.which("bash")


@pytest.fixture(scope="module")
def bash_path():
    path = _bash()
    if path is None:
        pytest.skip("bash not available")
    return path


def test_backup_script_exists():
    assert _BACKUP.is_file()


def test_backup_script_bash_n_syntax_clean(bash_path):
    res = subprocess.run([bash_path, "-n", str(_BACKUP)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_backup_script_writes_to_backups_dir():
    text = _BACKUP.read_text(encoding="utf-8")
    assert "BACKUP_DIR=" in text
    assert 'mkdir -p "$BACKUP_DIR"' in text


def test_restore_script_bash_n_syntax_clean(bash_path):
    res = subprocess.run([bash_path, "-n", str(_RESTORE)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_restore_script_requires_allow_restore():
    text = _RESTORE.read_text(encoding="utf-8")
    assert "ALLOW_RESTORE:-false" in text or '"${ALLOW_RESTORE:-false}"' in text
    assert "RESTORE_POSTGRES: FAIL (ALLOW_RESTORE" in text


def test_restore_script_blocks_production_mode():
    text = _RESTORE.read_text(encoding="utf-8")
    assert "production-check" in text
    assert "restore is forbidden" in text or "FAIL (APP_ENV" in text


def test_restore_script_requires_backup_file_arg():
    text = _RESTORE.read_text(encoding="utf-8")
    assert "FAIL (missing backup file argument)" in text
    assert "FAIL (backup file not found" in text


def test_verify_script_bash_n_syntax_clean(bash_path):
    res = subprocess.run([bash_path, "-n", str(_VERIFY)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_verify_script_asserts_backup_then_refusal():
    text = _VERIFY.read_text(encoding="utf-8")
    assert "backup_postgres.sh" in text
    assert "restore_postgres.sh" in text
    assert "ALLOW_RESTORE!=true" in text


def test_no_real_secret_substring_in_any_script():
    """None of the three scripts may carry a token-shaped substring."""
    import re

    forbidden = re.compile(
        r"ghp_[A-Za-z0-9_]{16,}"
        r"|github_pat_[A-Za-z0-9_]{16,}"
        r"|Bearer [A-Za-z0-9._-]{30,}"
        r"|Bot [A-Za-z0-9._-]{30,}"
    )
    for script in (_BACKUP, _RESTORE, _VERIFY):
        body = script.read_text(encoding="utf-8")
        assert forbidden.search(body) is None, f"token-shaped substring in {script.name}"
