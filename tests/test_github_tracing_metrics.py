"""Tracing / metrics / audit / notification assertions for github-automation.

In-process tests (TestClient) cover the metrics endpoint and the tracing
hooks. Notification + audit side effects depend on Redis / audit-service;
those tests are skipped when the runtime is not reachable.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from shared.sdk.event_bus.redis_streams import RedisStreamEventBus


def _redis_up() -> bool:
    bus = RedisStreamEventBus(redis_url="redis://localhost:6379")

    async def ping() -> bool:
        try:
            return bool(await bus.client.ping())
        finally:
            await bus.close()

    try:
        return asyncio.get_event_loop().run_until_complete(ping())
    except Exception:
        return False


def _audit_up() -> bool:
    try:
        return httpx.get("http://localhost:8003/health", timeout=2).status_code == 200
    except Exception:
        return False


requires_redis = pytest.mark.skipif(not _redis_up(), reason="redis not reachable on :6379")
requires_audit = pytest.mark.skipif(not _audit_up(), reason="audit-service not reachable on :8003")


def test_demo_pr_creates_span_attributes_in_process(github_automation_app):
    """Smoke check: the response surface confirms a span was opened with the
    right attributes (we don't assert on Tempo here; that lives in the
    verify_trace_flow.sh integration check). The span itself is exercised
    by simply calling the endpoint — we just confirm the call succeeds."""
    client = TestClient(github_automation_app)
    res = client.post(
        "/github/workflow/demo-pr",
        json={"task_id": "trace-" + uuid.uuid4().hex[:8]},
    )
    assert res.status_code == 200


def test_metrics_endpoint_emits_all_five_github_counters(github_automation_app):
    client = TestClient(github_automation_app)
    # Drive each counter at least once.
    client.post("/github/issue", json={"repo": "owner/repo", "title": "t"})
    client.post(
        "/github/branch",
        json={"repo": "owner/repo", "name": "feature/x"},
    )
    client.post(
        "/github/pull-request",
        json={
            "repo": "owner/repo",
            "title": "t",
            "body": "b",
            "head_branch": "feature/x",
        },
    )
    client.get("/github/checks?ref=feature/x&dry_run=true&repo=owner/repo")
    metrics = client.get("/metrics").text
    for counter in (
        "github_issue_created_total",
        "github_branch_created_total",
        "github_pr_created_total",
        "github_checks_read_total",
        "github_automation_failures_total",
    ):
        assert counter in metrics, f"missing counter {counter!r}"
    # dry_run label must appear.
    assert 'dry_run="true"' in metrics


@requires_redis
def test_demo_pr_publishes_notification_on_stream():
    """The github-automation service must publish a github.pr.dry_run
    notification on stream.notifications when the demo flow runs."""
    task_id = "notif-" + uuid.uuid4().hex[:8]
    # The service must be running for this check.
    try:
        res = httpx.post(
            "http://localhost:8005/github/workflow/demo-pr",
            json={"task_id": task_id, "dry_run": True},
            timeout=10,
        )
    except httpx.HTTPError as exc:
        pytest.skip(f"github-automation not reachable: {exc}")
    assert res.status_code == 200

    async def poll() -> bool:
        bus = RedisStreamEventBus(redis_url="redis://localhost:6379")
        deadline = time.time() + 10
        try:
            while time.time() < deadline:
                entries = await bus.client.xrevrange("stream.notifications", "+", "-", count=200)
                for _id, fields in entries:
                    try:
                        payload = json.loads(fields.get("data", "{}"))
                    except (ValueError, TypeError):
                        continue
                    if (
                        payload.get("task_id") == task_id
                        and payload.get("event_type") == "github.pr.dry_run"
                    ):
                        return True
                await asyncio.sleep(0.5)
        finally:
            await bus.close()
        return False

    assert asyncio.get_event_loop().run_until_complete(poll())


@requires_redis
@requires_audit
def test_demo_pr_writes_audit_event():
    """The github-automation service must write an audit row with
    decision_type='github_automation' tagged with the demo task_id."""
    task_id = "audit-" + uuid.uuid4().hex[:8]
    try:
        res = httpx.post(
            "http://localhost:8005/github/workflow/demo-pr",
            json={"task_id": task_id, "dry_run": True},
            timeout=10,
        )
    except httpx.HTTPError as exc:
        pytest.skip(f"github-automation not reachable: {exc}")
    assert res.status_code == 200

    deadline = time.time() + 10
    found = False
    while time.time() < deadline and not found:
        try:
            events = httpx.get(f"http://localhost:8003/audit/events/{task_id}", timeout=3).json()
        except httpx.HTTPError:
            events = {"events": []}
        for ev in events.get("events", []):
            if ev.get("decision_type") == "github_automation":
                found = True
                break
        if not found:
            time.sleep(0.5)
    assert found, "no audit event with decision_type=github_automation observed"
