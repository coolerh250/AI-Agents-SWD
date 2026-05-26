"""Static checks for scripts/verify_platform_observability.sh.

We do NOT execute the script (it touches Docker + the running stack);
we only assert it is syntactically valid, executable in the git index,
emits the required markers, and covers every check the Step 15.5 spec
calls for. The runtime sweep happens on 10.0.1.31, not in pytest.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "scripts" / "verify_platform_observability.sh"


def test_script_exists():
    assert _SCRIPT.exists(), f"missing {_SCRIPT}"


def test_script_is_executable_in_git_index():
    res = subprocess.run(
        ["git", "ls-files", "--stage", "scripts/verify_platform_observability.sh"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0 or not res.stdout:
        pytest.skip("git ls-files unavailable; cannot check index mode")
    mode = res.stdout.split()[0]
    assert mode.startswith(
        "1007"
    ), f"verify_platform_observability.sh is not +x in git index (mode={mode})"


def test_script_is_syntactically_valid():
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash not available on PATH")
    res = subprocess.run(
        [bash, "-n", str(_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0, f"syntax error: {res.stderr}"


def test_script_emits_required_aggregate_markers():
    body = _SCRIPT.read_text(encoding="utf-8")
    for marker in (
        "PLATFORM_OBSERVABILITY_VERIFY: PASS",
        "PLATFORM_OBSERVABILITY_VERIFY: FAIL",
        "VERIFY_PLATFORM_OBSERVABILITY_DONE",
        "CHECK_RUNTIME_STATE: PASS",
        "VERIFY_TRACING_BACKEND: PASS",
        "VERIFY_TRACE_FLOW: PASS",
        "VERIFY_ALERTING: PASS",
        "VERIFY_INCIDENT_FLOW: PASS",
    ):
        assert marker in body, f"missing marker {marker!r}"


def test_script_invokes_existing_subscripts():
    body = _SCRIPT.read_text(encoding="utf-8")
    for sub in (
        "scripts/check_runtime_state.sh",
        "scripts/verify_tracing_backend.sh",
        "scripts/verify_trace_flow.sh",
        "scripts/verify_alerting.sh",
        "scripts/verify_incident_flow.sh",
    ):
        assert sub in body, f"script does not reference {sub}"


def test_script_covers_required_areas():
    body = _SCRIPT.read_text(encoding="utf-8")
    for token in (
        # Docker / runtime
        "docker compose",
        "postgres",
        "redis",
        "vault",
        "prometheus",
        "grafana",
        "tempo",
        "alertmanager",
        # Health endpoints
        "/health",
        "communication-gateway",
        "orchestrator",
        "policy-engine",
        "approval-engine",
        "audit-service",
        "retry-scheduler",
        "intake-agent",
        "requirement-agent",
        "development-agent",
        "qa-agent",
        "devops-agent",
        # Metrics
        "/metrics",
        "workflow_total",
        "agent_execution_total",
        # Prometheus / Alertmanager
        "/-/healthy",
        "/api/v1/targets",
        "/api/v1/rules",
        "/api/v1/alerts",
        "/api/v2/status",
        "/api/v2/receivers",
        # Grafana
        "/api/health",
        "/api/datasources",
        # Tempo
        "/ready",
        "/status/version",
        "/api/traces/",
        # Workflow + trace
        "/workflow/progress/",
        "/workflow/timeline/",
        # Incident lifecycle
        "/incidents",
        "/ack",
        "/resolve",
        # SLO
        "aiagents-slo.yml",
        # Safety
        "production_executed",
        "deployment_records",
    ):
        assert token in body, f"script missing coverage for {token!r}"


def test_script_does_not_contact_external_services():
    """The verification path must never reach out to a real cloud
    backend, alert SaaS, or production endpoint."""
    body = _SCRIPT.read_text(encoding="utf-8")
    banned = (
        "grafana.net",
        "slack.com",
        "discord.com",
        "telegram.org",
        "pagerduty.com",
        "opsgenie.com",
        "kubernetes.io",
        "googleapis.com",
        "amazonaws.com",
        "azure.com",
    )
    for needle in banned:
        assert needle not in body, f"script contains banned external host {needle!r}"


def test_script_does_not_embed_secrets():
    body = _SCRIPT.read_text(encoding="utf-8").lower()
    for needle in ("api_key=", "token=", "password=", "bearer ", "secret_key"):
        assert needle not in body, f"script contains forbidden secret token {needle!r}"
