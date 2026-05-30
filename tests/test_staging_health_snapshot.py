"""Stage 25 checks for runtime_health_snapshot.sh --env staging support."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SNAPSHOT = _REPO_ROOT / "scripts" / "runtime_health_snapshot.sh"


@pytest.fixture(scope="module")
def bash_path():
    path = shutil.which("bash")
    if path is None:
        pytest.skip("bash not available")
    return path


def test_snapshot_script_bash_n_syntax_clean(bash_path):
    res = subprocess.run([bash_path, "-n", str(_SNAPSHOT)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_snapshot_supports_env_flag():
    text = _SNAPSHOT.read_text(encoding="utf-8")
    assert "--env" in text
    # Default is local; the local + staging paths must exist.
    assert 'ENV_TARGET="local"' in text
    assert "staging" in text


def test_snapshot_staging_output_path():
    text = _SNAPSHOT.read_text(encoding="utf-8")
    assert "source/runtime-health-staging.log" in text


def test_snapshot_staging_uses_staging_compose_file():
    text = _SNAPSHOT.read_text(encoding="utf-8")
    assert "infra/docker-compose/docker-compose.staging.yml" in text
    assert "aiagents-staging" in text


def test_snapshot_staging_uses_staging_ports():
    text = _SNAPSHOT.read_text(encoding="utf-8")
    # Staging orchestrator on 18000 + prometheus on 19090.
    assert "http://localhost:18000" in text
    assert "http://localhost:19090" in text


def test_snapshot_does_not_echo_token_or_password():
    text = _SNAPSHOT.read_text(encoding="utf-8")
    forbidden = re.compile(
        r"ghp_[A-Za-z0-9_]{16,}"
        r"|github_pat_[A-Za-z0-9_]{16,}"
        r"|Bearer [A-Za-z0-9._-]{30,}"
        r"|Bot [A-Za-z0-9._-]{30,}"
    )
    assert forbidden.search(text) is None
    # No `echo $POSTGRES_PASSWORD` anywhere.
    assert "echo $POSTGRES_PASSWORD" not in text
    assert 'echo "$POSTGRES_PASSWORD"' not in text


def test_snapshot_emits_pass_marker():
    text = _SNAPSHOT.read_text(encoding="utf-8")
    assert "RUNTIME_HEALTH_SNAPSHOT_DONE: PASS" in text


def test_snapshot_truncates_log_on_each_run():
    text = _SNAPSHOT.read_text(encoding="utf-8")
    assert ': > "$out"' in text


def test_snapshot_includes_production_safety_query():
    text = _SNAPSHOT.read_text(encoding="utf-8")
    assert "deployment_records" in text
    assert "workflow_states" in text
    assert "production_executed" in text


def test_gitignore_excludes_staging_health_log():
    """The staging health log carries no secret but is regeneratable —
    the broad ``*.log`` ignore already catches it. The test pins the
    contract so a future operator can audit it."""
    text = (_REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "*.log" in text
