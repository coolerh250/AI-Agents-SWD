import shutil
import subprocess
from pathlib import Path

import httpx
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "scripts" / "verify_alerting.sh"
_CHECK_SCRIPT = _REPO_ROOT / "scripts" / "check_runtime_state.sh"


def test_verify_alerting_script_exists():
    assert _SCRIPT.exists(), f"missing {_SCRIPT}"


def test_verify_alerting_script_is_executable_in_index():
    res = subprocess.run(
        ["git", "ls-files", "--stage", "scripts/verify_alerting.sh"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0 or not res.stdout:
        pytest.skip("git ls-files unavailable; cannot check index mode")
    mode = res.stdout.split()[0]
    assert mode.startswith("1007"), f"verify_alerting.sh is not +x in git index (mode={mode})"


def test_verify_alerting_script_is_syntactically_valid():
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash not available on PATH")
    res = subprocess.run([bash, "-n", str(_SCRIPT)], capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"verify_alerting.sh syntax error: {res.stderr}"


def test_verify_alerting_script_checks_required_endpoints():
    body = _SCRIPT.read_text(encoding="utf-8")
    # Must hit Alertmanager health + status API and Prometheus rules / alerts.
    for marker in (
        "/-/healthy",
        "/api/v2/status",
        "/api/v1/rules",
        "/api/v1/alerts",
        "/api/v1/targets",
    ):
        assert marker in body, f"verify_alerting.sh does not exercise {marker}"
    # Must emit pass / fail markers the smoke aggregator can grep.
    for marker in (
        "ALERTMANAGER_HEALTHY",
        "PROMETHEUS_RULES_LOADED",
        "PROMETHEUS_ALERTS_API",
        "VERIFY_ALERTING_DONE",
    ):
        assert marker in body, f"verify_alerting.sh missing marker {marker}"


def test_check_runtime_state_includes_alerting_smokes():
    body = _CHECK_SCRIPT.read_text(encoding="utf-8")
    for marker in (
        "ALERTMANAGER_HEALTH",
        "PROMETHEUS_RULES_SMOKE",
        "PROMETHEUS_ALERTS_API_SMOKE",
    ):
        assert marker in body, f"check_runtime_state.sh missing alerting smoke {marker}"


def _alerting_up() -> bool:
    for url in (
        "http://localhost:9093/-/healthy",
        "http://localhost:9090/-/ready",
    ):
        try:
            if httpx.get(url, timeout=3).status_code >= 400:
                return False
        except Exception:
            return False
    return True


requires_stack = pytest.mark.skipif(
    not _alerting_up(),
    reason="alertmanager (9093) + prometheus (9090) not reachable on localhost",
)


@requires_stack
def test_alertmanager_healthy_endpoint():
    response = httpx.get("http://localhost:9093/-/healthy", timeout=5)
    assert response.status_code == 200


@requires_stack
def test_alertmanager_status_api_returns_version_info():
    response = httpx.get("http://localhost:9093/api/v2/status", timeout=5)
    assert response.status_code == 200
    body = response.json()
    assert "versionInfo" in body
    assert "cluster" in body


@requires_stack
def test_prometheus_loads_aiagents_rule_groups():
    response = httpx.get("http://localhost:9090/api/v1/rules", timeout=5)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    group_names = {g["name"] for g in body["data"]["groups"]}
    # Expect at least the four aiagents.* groups defined in aiagents.rules.yml.
    aiagents_groups = {n for n in group_names if n.startswith("aiagents.")}
    assert len(aiagents_groups) >= 4, group_names


@requires_stack
def test_prometheus_alerts_api_lists_required_alert_names():
    response = httpx.get("http://localhost:9090/api/v1/rules", timeout=5)
    assert response.status_code == 200
    body = response.json()
    alert_names: set[str] = set()
    for group in body["data"]["groups"]:
        for rule in group.get("rules", []):
            if rule.get("type") == "alerting":
                alert_names.add(rule["name"])
    for required in (
        "AIWorkflowFailuresHigh",
        "AIWorkflowLatencyP95High",
        "AIAgentExecutionFailuresHigh",
        "AIDeadletterIncreasing",
        "AIRetrySpike",
        "AIServiceDown",
        "AIPrometheusTargetDown",
        "AIApprovalPendingTooLong",
    ):
        assert required in alert_names, (required, alert_names)


@requires_stack
def test_prometheus_alerts_endpoint_returns_success():
    response = httpx.get("http://localhost:9090/api/v1/alerts", timeout=5)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert "data" in body
