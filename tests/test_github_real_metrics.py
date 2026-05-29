"""Stage 23 metrics registration tests.

The github-automation service must expose the five new
``github_real_test_*`` series. The test asserts they are registered on
the default Prometheus registry — counters with labels emit only
HELP/TYPE lines until the first ``.labels(...).inc()`` runs.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_github_automation_metrics_endpoint_carries_real_test_series(github_automation_app):
    client = TestClient(github_automation_app)
    res = client.get("/metrics")
    assert res.status_code == 200
    body = res.text
    for series in (
        "github_real_test_attempts_total",
        "github_real_test_success_total",
        "github_real_test_blocked_total",
        "github_real_test_failures_total",
        "github_real_test_duration_seconds",
    ):
        assert series in body, f"metric {series} not registered"


def test_blocked_increments_blocked_metric(github_automation_app, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("RUN_REAL_GITHUB_TEST", raising=False)
    monkeypatch.delenv("GITHUB_TEST_REPO", raising=False)
    client = TestClient(github_automation_app)
    res = client.post(
        "/github/workflow/real-test-pr",
        json={
            "task_id": "metrics-1",
            "repo": "coolerh250/AI-Agents-SWD",
            "branch_name": "ai-agents-test/metrics-1",
            "title": "[AI-Agents-SWD Test] metrics",
            "body": (
                "## Summary\nx\n\n## Changed Files\n- x\n\n## Risk Assessment\nx\n\n"
                "## Test Result\nx\n\n## Rollback Plan\nx\n\n## Safety Notes\nx\n"
            ),
            "file_path": "docs/github-real-test/metrics-1.md",
            "file_content": (
                "task_id=metrics-1\nworkflow_id=wf\n"
                "generated_by=github-automation\nreal_github_test=true\n"
                "production_executed=false\n"
            ),
            "dry_run": False,
        },
    )
    assert res.status_code == 409
    metrics = client.get("/metrics").text
    assert "github_real_test_blocked_total" in metrics
    # one labelled increment must have appeared on the counter line
    assert "github_real_test_blocked_total{" in metrics
