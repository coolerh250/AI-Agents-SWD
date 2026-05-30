"""Stage 25 static checks for scripts/verify_staging_runtime.sh.

End-to-end cluster PASS is exercised on 10.0.1.31. Here we pin the
contract: the verify script must run the validator, bring staging up,
hit the e2e workflow flow, assert safety, and (by default) tear staging
down without leaving the local/test stack disturbed.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_VERIFY = _REPO_ROOT / "scripts" / "verify_staging_runtime.sh"


@pytest.fixture(scope="module")
def bash_path():
    path = shutil.which("bash")
    if path is None:
        pytest.skip("bash not available")
    return path


def test_verify_script_exists():
    assert _VERIFY.is_file()


def test_verify_script_bash_n_syntax_clean(bash_path):
    res = subprocess.run([bash_path, "-n", str(_VERIFY)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_verify_script_uses_staging_compose_project():
    text = _VERIFY.read_text(encoding="utf-8")
    assert "aiagents-staging" in text
    assert "docker compose -p" in text


def test_verify_script_runs_validator_staging():
    text = _VERIFY.read_text(encoding="utf-8")
    assert "validate_runtime_config.sh --mode staging" in text


def test_verify_script_runs_check_runtime_and_e2e():
    text = _VERIFY.read_text(encoding="utf-8")
    assert "check_staging_runtime.sh" in text
    assert "discord/messages" in text
    assert "operations/workflows/" in text
    assert "operations/safety" in text


def test_verify_script_pins_production_safety_sql():
    text = _VERIFY.read_text(encoding="utf-8")
    assert "production_executed" in text
    assert "environment='production'" in text


def test_verify_script_default_tears_staging_down():
    text = _VERIFY.read_text(encoding="utf-8")
    # Default ACTION is "down" and the down path invokes stop_staging_runtime.sh.
    assert 'ACTION="down"' in text
    assert "stop_staging_runtime.sh" in text
    assert "--keep-running" in text


def test_verify_script_emits_pass_marker():
    text = _VERIFY.read_text(encoding="utf-8")
    assert "STAGING_RUNTIME_VERIFY: PASS" in text


def test_verify_script_carries_no_token():
    text = _VERIFY.read_text(encoding="utf-8")
    forbidden = re.compile(
        r"ghp_[A-Za-z0-9_]{16,}"
        r"|github_pat_[A-Za-z0-9_]{16,}"
        r"|Bearer [A-Za-z0-9._-]{30,}"
        r"|Bot [A-Za-z0-9._-]{30,}"
    )
    assert forbidden.search(text) is None


def test_verify_script_confirms_local_test_unaffected():
    """The verify script must check that the local/test orchestrator
    (port 8000) is still reachable after staging is brought up. If the
    staging bring-up clobbers the local cluster we want to catch it.
    """
    text = _VERIFY.read_text(encoding="utf-8")
    # local/test orchestrator on port 8000 — must be hit in the
    # "local/test stack unaffected" section.
    assert "localhost:8000/health" in text
    assert "LOCAL_TEST_UNAFFECTED" in text
