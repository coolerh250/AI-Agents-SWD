import json
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[1]
_OBS_ROOT = _REPO_ROOT / "infra" / "observability"


def test_prometheus_config_targets_every_service():
    path = _OBS_ROOT / "prometheus.yml"
    assert path.exists(), f"missing {path}"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    jobs = {job["job_name"] for job in config["scrape_configs"]}
    for required in (
        "orchestrator",
        "policy-engine",
        "approval-engine",
        "audit-service",
        "communication-gateway",
        "intake-agent",
        "requirement-agent",
        "development-agent",
        "qa-agent",
        "devops-agent",
        "retry-scheduler",
    ):
        assert required in jobs, f"prometheus.yml missing scrape job for {required}"


def test_grafana_datasource_provisioning_present():
    path = _OBS_ROOT / "grafana" / "provisioning" / "datasources" / "prometheus.yml"
    assert path.exists(), f"missing {path}"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    datasources = config["datasources"]
    assert any(ds["type"] == "prometheus" and "prometheus:9090" in ds["url"] for ds in datasources)


def test_grafana_dashboard_provisioning_present():
    path = _OBS_ROOT / "grafana" / "provisioning" / "dashboards" / "dashboards.yml"
    assert path.exists(), f"missing {path}"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    providers = config["providers"]
    assert any(p["type"] == "file" for p in providers)
    assert providers[0]["options"]["path"] == "/var/lib/grafana/dashboards"


def test_grafana_dashboard_json_references_platform_metrics():
    path = _OBS_ROOT / "grafana" / "dashboards" / "aiagents.json"
    assert path.exists(), f"missing {path}"
    dashboard = json.loads(path.read_text(encoding="utf-8"))
    assert dashboard["title"] == "AI Agents SWD Platform"
    panels_text = json.dumps(dashboard["panels"])
    for metric in (
        "workflow_total",
        "workflow_completed_total",
        "workflow_failed_total",
        "workflow_duration_seconds",
        "agent_execution_total",
        "agent_latency_seconds",
        "deadletter_total",
        "retry_total",
    ):
        assert metric in panels_text, f"dashboard does not reference {metric}"


def test_docker_compose_includes_prometheus_and_grafana_bound_to_localhost():
    path = _REPO_ROOT / "infra" / "docker-compose" / "docker-compose.yml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    services = config["services"]
    assert "prometheus" in services
    assert "grafana" in services
    prom_ports = [str(p) for p in services["prometheus"]["ports"]]
    graf_ports = [str(p) for p in services["grafana"]["ports"]]
    assert any("127.0.0.1:9090:9090" in p for p in prom_ports)
    assert any("127.0.0.1:3000:3000" in p for p in graf_ports)


def test_grafana_anonymous_role_is_admin_for_local_test():
    path = _REPO_ROOT / "infra" / "docker-compose" / "docker-compose.yml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    grafana_env = config["services"]["grafana"]["environment"]
    # local/test runtime allows anonymous access; this would NOT be acceptable
    # in production but is fine for the 10.0.1.31 test environment.
    assert grafana_env["GF_AUTH_ANONYMOUS_ENABLED"] == "true"
    assert grafana_env["GF_USERS_ALLOW_SIGN_UP"] == "false"


def _stack_up() -> bool:
    import httpx

    for url in ("http://localhost:9090/-/ready", "http://localhost:3000/api/health"):
        try:
            if httpx.get(url, timeout=3).status_code >= 400:
                return False
        except Exception:
            return False
    return True


requires_stack = pytest.mark.skipif(
    not _stack_up(),
    reason="prometheus (9090) + grafana (3000) not reachable on localhost",
)


@requires_stack
def test_prometheus_ready_endpoint():
    import httpx

    response = httpx.get("http://localhost:9090/-/ready", timeout=5)
    assert response.status_code == 200


@requires_stack
def test_grafana_health_endpoint():
    import httpx

    response = httpx.get("http://localhost:3000/api/health", timeout=5)
    assert response.status_code == 200
    body = response.json()
    assert body.get("database") == "ok"


@requires_stack
def test_prometheus_lists_service_targets():
    import httpx

    response = httpx.get("http://localhost:9090/api/v1/targets", timeout=5)
    assert response.status_code == 200
    targets = response.json()["data"]["activeTargets"]
    jobs = {t["labels"]["job"] for t in targets}
    assert "orchestrator" in jobs
    assert "retry-scheduler" in jobs
