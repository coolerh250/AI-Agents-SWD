"""Stage 24 static checks for scripts/production_safety_gate.sh.

We don't actually run the gate here — the cluster verify scripts cover
the end-to-end PASS. The test confirms the script's shape: read-only,
no real-write hooks, no secret echo.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_GATE = _REPO_ROOT / "scripts" / "production_safety_gate.sh"


@pytest.fixture(scope="module")
def bash_path():
    path = shutil.which("bash")
    if path is None:
        pytest.skip("bash not available")
    return path


def test_gate_script_exists():
    assert _GATE.is_file()


def test_gate_script_bash_n_syntax_clean(bash_path):
    res = subprocess.run([bash_path, "-n", str(_GATE)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr


def test_gate_inspects_deployment_records():
    text = _GATE.read_text(encoding="utf-8")
    assert "deployment_records" in text
    assert "production_executed" in text
    assert "environment='production'" in text


def test_gate_inspects_workflow_states():
    text = _GATE.read_text(encoding="utf-8")
    assert "workflow_states" in text
    assert "execution_result->>'production_executed'='true'" in text


def test_gate_inspects_operations_safety():
    text = _GATE.read_text(encoding="utf-8")
    assert "/operations/safety" in text


def test_gate_emits_pass_or_fail_marker():
    text = _GATE.read_text(encoding="utf-8")
    assert "PRODUCTION_SAFETY_GATE: PASS" in text
    assert "PRODUCTION_SAFETY_GATE: FAIL" in text


def test_gate_is_read_only():
    """The gate must NOT contain any destructive cmd that mutates DB
    rows, deploys a service, or talks to a real external API.
    """
    text = _GATE.read_text(encoding="utf-8")
    forbidden_patterns = (
        r"\bDELETE\b",
        r"\bUPDATE\b",
        r"\bINSERT\b",
        r"\bDROP\b",
        r"\bTRUNCATE\b",
        r"docker compose .* up\b",
        r"docker compose .* restart\b",
        r"kubectl",
        r"helm",
        r"curl .* -X PUT",
        r"curl .* -X POST",
        r"curl .* -X DELETE",
    )
    for pattern in forbidden_patterns:
        assert not re.search(
            pattern, text, re.IGNORECASE
        ), f"production_safety_gate.sh contains forbidden pattern {pattern!r}"


def test_gate_carries_no_real_secret():
    text = _GATE.read_text(encoding="utf-8")
    forbidden = re.compile(
        r"ghp_[A-Za-z0-9_]{16,}"
        r"|github_pat_[A-Za-z0-9_]{16,}"
        r"|Bearer [A-Za-z0-9._-]{30,}"
        r"|Bot [A-Za-z0-9._-]{30,}"
    )
    assert forbidden.search(text) is None
