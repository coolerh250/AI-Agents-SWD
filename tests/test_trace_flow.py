import os
import shutil
import stat
import subprocess
from pathlib import Path

import httpx
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "scripts" / "verify_trace_flow.sh"


def test_verify_trace_flow_script_exists():
    assert _SCRIPT.exists(), f"missing {_SCRIPT}"


def test_verify_trace_flow_script_is_executable_in_index():
    # Windows can't mark a working-copy file executable, but git's index entry must.
    # If the file is missing the +x flag, the test server will skip it silently.
    res = subprocess.run(
        ["git", "ls-files", "--stage", "scripts/verify_trace_flow.sh"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0 or not res.stdout:
        pytest.skip("git ls-files unavailable; cannot check index mode")
    mode = res.stdout.split()[0]
    assert mode.startswith("1007"), f"verify_trace_flow.sh is not +x in git index (mode={mode})"


def test_verify_trace_flow_script_is_syntactically_valid():
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash not available on PATH")
    res = subprocess.run([bash, "-n", str(_SCRIPT)], capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"verify_trace_flow.sh syntax error: {res.stderr}"


def test_verify_trace_flow_script_targets_required_services():
    body = _SCRIPT.read_text(encoding="utf-8")
    for svc in (
        "communication-gateway",
        "orchestrator",
        "intake-agent",
        "requirement-agent",
        "development-agent",
        "qa-agent",
        "devops-agent",
    ):
        assert svc in body, f"verify_trace_flow.sh does not check for {svc}"


def test_verify_trace_flow_emits_pass_fail_marker():
    body = _SCRIPT.read_text(encoding="utf-8")
    assert "TRACE_FLOW_SMOKE: PASS" in body
    assert "TRACE_FLOW_SMOKE: FAIL" in body


def test_runtime_state_script_includes_trace_flow_smoke():
    body = (_REPO_ROOT / "scripts" / "check_runtime_state.sh").read_text(encoding="utf-8")
    assert "TRACE_FLOW_SMOKE" in body
    # the existing Tempo + Grafana smokes from Step 15.1 must still be there
    assert "TEMPO_HEALTH" in body
    assert "GRAFANA_TEMPO_DATASOURCE_SMOKE" in body


def _pipeline_up() -> bool:
    for url in (
        "http://localhost:8004/health",
        "http://localhost:8000/health",
        "http://localhost:3200/ready",
    ):
        try:
            if httpx.get(url, timeout=3).status_code >= 400:
                return False
        except Exception:
            return False
    return True


@pytest.mark.skipif(
    not _pipeline_up(),
    reason="pipeline (gateway + orchestrator + tempo) not reachable on localhost",
)
def test_verify_trace_flow_script_runs_end_to_end_when_stack_is_up():
    """Smoke: actually invoke verify_trace_flow.sh; it must reach DONE without error."""
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash not available on PATH")
    # Make sure the file is executable on disk (Windows checkouts may not be).
    try:
        os.chmod(_SCRIPT, os.stat(_SCRIPT).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except Exception:
        pass
    res = subprocess.run(
        [bash, str(_SCRIPT)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert "VERIFY_TRACE_FLOW_DONE" in res.stdout, res.stdout + res.stderr
