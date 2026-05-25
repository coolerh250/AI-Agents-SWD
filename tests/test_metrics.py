from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.sdk.observability import metrics as metrics_module

_REQUIRED_METRICS = (
    "WORKFLOW_TOTAL",
    "WORKFLOW_COMPLETED_TOTAL",
    "WORKFLOW_FAILED_TOTAL",
    "WORKFLOW_DURATION_SECONDS",
    "AGENT_EXECUTION_TOTAL",
    "AGENT_EXECUTION_FAILURES_TOTAL",
    "AGENT_LATENCY_SECONDS",
    "DEADLETTER_TOTAL",
    "RETRY_TOTAL",
    "NOTIFICATION_TOTAL",
)


def test_metrics_module_exposes_required_counters():
    for name in _REQUIRED_METRICS:
        assert hasattr(metrics_module, name), f"missing metric: {name}"


def test_workflow_total_counter_increments():
    metric = metrics_module.WORKFLOW_TOTAL.labels(status="metrics-test")
    before = metric._value.get()
    metric.inc()
    assert metric._value.get() == before + 1


def test_agent_latency_observation_accumulates():
    bucket = metrics_module.AGENT_LATENCY_SECONDS.labels(agent="metrics-test")
    before = bucket._sum.get()
    bucket.observe(0.123)
    assert bucket._sum.get() == before + 0.123


def test_metrics_response_returns_prometheus_format():
    body, content_type = metrics_module.metrics_response()
    assert b"workflow_total" in body
    assert "text/plain" in content_type


def test_install_metrics_endpoint_attaches_route():
    app = FastAPI()
    metrics_module.install_metrics_endpoint(app)
    response = TestClient(app).get("/metrics")
    assert response.status_code == 200
    assert "workflow_total" in response.text
    assert "agent_execution_total" in response.text
