"""Stage 24 static checks for scripts/runtime_health_snapshot.sh.

End-to-end PASS is exercised by verify_staging_hardening.sh on the
cluster. Here we only check shape: syntax, output path, regeneratable.
"""

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


def test_snapshot_script_exists():
    assert _SNAPSHOT.is_file()


def test_snapshot_script_bash_n_syntax_clean(bash_path):
    res = subprocess.run([bash_path, "-n", str(_SNAPSHOT)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_snapshot_targets_source_runtime_health_log():
    text = _SNAPSHOT.read_text(encoding="utf-8")
    assert "source/runtime-health.log" in text


def test_snapshot_overwrites_log_not_appends():
    text = _SNAPSHOT.read_text(encoding="utf-8")
    # The script should truncate the file before writing so re-runs are
    # idempotent. Look for the canonical truncation pattern (``: > "$out"``).
    assert ': > "$out"' in text or ': > "$out"' in text


def test_snapshot_emits_pass_marker():
    text = _SNAPSHOT.read_text(encoding="utf-8")
    assert "RUNTIME_HEALTH_SNAPSHOT_DONE: PASS" in text


def test_snapshot_does_not_echo_token_shaped_strings():
    text = _SNAPSHOT.read_text(encoding="utf-8")
    forbidden = re.compile(
        r"ghp_[A-Za-z0-9_]{16,}"
        r"|github_pat_[A-Za-z0-9_]{16,}"
        r"|Bearer [A-Za-z0-9._-]{30,}"
        r"|Bot [A-Za-z0-9._-]{30,}"
    )
    assert forbidden.search(text) is None


def test_snapshot_includes_production_safety_query():
    text = _SNAPSHOT.read_text(encoding="utf-8")
    assert "production_executed" in text
    assert "deployment_records" in text
    assert "workflow_states" in text
