"""Stage 26 — leak scanner functional tests against a temp tree."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "scripts" / "scan_for_secret_leaks.sh"


@pytest.fixture(scope="module")
def bash_path():
    p = shutil.which("bash")
    if p is None:
        pytest.skip("bash not available")
    return p


def _run_scanner_against(tmp_root: Path, bash_path: str) -> subprocess.CompletedProcess:
    # The scanner derives REPO_ROOT from its own location; we point it
    # at a copy of the script that lives inside tmp_root so the sweep
    # only sees the fixture files.
    fake_scripts = tmp_root / "scripts"
    fake_scripts.mkdir(parents=True, exist_ok=True)
    shutil.copy(_SCRIPT, fake_scripts / "scan_for_secret_leaks.sh")
    return subprocess.run(
        [bash_path, str(fake_scripts / "scan_for_secret_leaks.sh")],
        capture_output=True,
        text=True,
    )


def test_clean_tree_passes(tmp_path: Path, bash_path: str):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "x.md").write_text(
        "Placeholder PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE here\n",
        encoding="utf-8",
    )
    (tmp_path / "infra").mkdir()
    (tmp_path / "infra" / "runtime").mkdir()
    (tmp_path / "infra" / "runtime" / "env.example").write_text(
        "GITHUB_TOKEN=${GITHUB_TOKEN:-}\nVAULT_TOKEN=PLACEHOLDER_DO_NOT_COMMIT_REAL_VALUE\n",
        encoding="utf-8",
    )
    res = _run_scanner_against(tmp_path, bash_path)
    assert "SECRET_LEAK_SCAN: PASS" in res.stdout, res.stdout + res.stderr


def test_real_token_substring_fails(tmp_path: Path, bash_path: str):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "leak.md").write_text(
        "# accidentally committed: ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAA\n",
        encoding="utf-8",
    )
    res = _run_scanner_against(tmp_path, bash_path)
    assert "SECRET_LEAK_SCAN: FAIL" in res.stdout, res.stdout
    # The matched line MUST NOT print the literal token (the scanner
    # prints the pattern name, not the matched substring).
    assert "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAA" not in res.stdout


def test_redaction_token_is_allowed(tmp_path: Path, bash_path: str):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "ok.md").write_text(
        "headers['Authorization'] = ***REDACTED***\n", encoding="utf-8"
    )
    res = _run_scanner_against(tmp_path, bash_path)
    assert "SECRET_LEAK_SCAN: PASS" in res.stdout


def test_committed_repo_passes(bash_path: str):
    """The real repo must pass — meta-test catching anything that slipped in."""
    res = subprocess.run([bash_path, str(_SCRIPT)], capture_output=True, text=True, cwd=_REPO_ROOT)
    assert "SECRET_LEAK_SCAN: PASS" in res.stdout, res.stdout
