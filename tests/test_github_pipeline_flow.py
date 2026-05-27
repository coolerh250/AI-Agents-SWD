"""End-to-end (live cluster) pipeline → github-automation test.

Skipped unless Redis + Postgres + github-automation are reachable.
Posts a workflow through communication-gateway with
``request.github.enabled=true, dry_run=true``, polls until completion,
and asserts the workflow row, audit log, and notification stream all
carry the github result.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid

import httpx
import pytest


def _http_up(url: str) -> bool:
    try:
        return httpx.get(url, timeout=2).status_code == 200
    except Exception:
        return False


def _all_up() -> bool:
    return (
        _http_up("http://localhost:8000/health")
        and _http_up("http://localhost:8003/health")
        and _http_up("http://localhost:8004/health")
        and _http_up("http://localhost:8005/health")
    )


requires_cluster = pytest.mark.skipif(
    not _all_up(), reason="orchestrator/audit/gateway/github-automation not reachable"
)


def _wait_for_workflow(task_id: str, timeout: float = 60.0) -> dict | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            body = httpx.get(f"http://localhost:8000/workflow/progress/{task_id}", timeout=5).json()
        except Exception:
            body = {}
        if body.get("current_stage") == "completed":
            return body
        time.sleep(2)
    return None


@requires_cluster
def test_pipeline_emits_github_dry_run_envelope_on_workflow():
    task_id = f"github-pipeline-test-{uuid.uuid4().hex[:8]}"
    res = httpx.post(
        "http://localhost:8004/intake/mock",
        json={
            "task_id": task_id,
            "request": {
                "type": "dev.test",
                "description": "pytest github pipeline",
                "github": {
                    "enabled": True,
                    "repo": "coolerh250/AI-Agents-SWD",
                    "base_branch": "main",
                    "dry_run": True,
                },
            },
        },
        timeout=30,
    )
    assert res.status_code == 200, res.text

    progress = _wait_for_workflow(task_id)
    assert progress is not None, f"workflow {task_id} did not complete"
    assert progress["current_stage"] == "completed"
    # github fields must be filled
    gh = progress.get("github")
    assert isinstance(gh, dict) and gh, "progress.github missing"
    assert gh["status"] == "success"
    assert gh["dry_run"] is True
    assert gh["pr_url"].startswith("https://github.com/")
    assert progress.get("pr_url") == gh["pr_url"]
    assert progress.get("github_dry_run") is True

    # timeline carries a github.demo_pr.dry_run entry
    timeline = httpx.get(f"http://localhost:8000/workflow/timeline/{task_id}", timeout=10).json()
    phases = [entry.get("phase") for entry in timeline.get("agent_timeline", [])]
    assert "github.demo_pr.dry_run" in phases, phases

    # audit log has github_pr_integration
    events = httpx.get(f"http://localhost:8003/audit/events/{task_id}", timeout=10).json()
    decisions = {ev.get("decision_type") for ev in events.get("events", [])}
    assert "github_pr_integration" in decisions, decisions

    # notification carries github.pr.dry_run
    notif = httpx.get("http://localhost:8004/notifications?count=200", timeout=10).json()
    found = False
    for entry in notif.get("notifications", []):
        payload = entry.get("notification") or {}
        if payload.get("task_id") == task_id and payload.get("event_type") == "github.pr.dry_run":
            found = True
            break
    assert found, "no github.pr.dry_run notification observed"

    # workflow_states.production_executed must still be false
    workflow = httpx.get(f"http://localhost:8000/workflow/{task_id}", timeout=10).json()
    exec_result = (workflow.get("state") or {}).get("execution_result") or {}
    assert exec_result.get("production_executed") is False
    assert exec_result.get("github", {}).get("dry_run") is True


@requires_cluster
def test_pipeline_skips_github_when_enabled_false():
    task_id = f"github-pipeline-skip-{uuid.uuid4().hex[:8]}"
    res = httpx.post(
        "http://localhost:8004/intake/mock",
        json={
            "task_id": task_id,
            "request": {
                "type": "dev.test",
                "github": {"enabled": False, "disabled_reason": "pytest opt-out"},
            },
        },
        timeout=30,
    )
    assert res.status_code == 200, res.text
    progress = _wait_for_workflow(task_id)
    assert progress is not None
    gh = progress.get("github") or {}
    # disabled means we still emit a github block but with status=disabled and
    # an empty pr_url. The pr_url field on the envelope is therefore empty.
    assert gh.get("status") == "disabled"
    assert gh.get("pr_url", "") == ""
    assert progress.get("pr_url", "") == ""


def _redis_ping() -> bool:
    try:
        import redis.asyncio as _redis

        async def ping() -> bool:
            c = _redis.from_url("redis://localhost:6379")
            try:
                return bool(await c.ping())
            finally:
                await c.aclose()

        return asyncio.new_event_loop().run_until_complete(ping())
    except Exception:
        return False


@pytest.mark.skipif(not _redis_ping(), reason="redis not reachable on :6379")
@requires_cluster
def test_pipeline_publishes_devops_event_with_github_block():
    """The devops.deployment_simulated event on stream.devops must carry
    a top-level ``github`` block keyed by the task_id."""
    task_id = f"github-pipeline-devops-{uuid.uuid4().hex[:8]}"
    res = httpx.post(
        "http://localhost:8004/intake/mock",
        json={
            "task_id": task_id,
            "request": {
                "type": "dev.test",
                "github": {"enabled": True, "dry_run": True},
            },
        },
        timeout=30,
    )
    assert res.status_code == 200, res.text
    _wait_for_workflow(task_id)

    import redis.asyncio as _redis

    async def find() -> dict | None:
        client = _redis.from_url("redis://localhost:6379", decode_responses=True)
        try:
            entries = await client.xrevrange("stream.devops", "+", "-", count=500)
            for _id, fields in entries:
                try:
                    payload = json.loads(fields.get("data", "{}"))
                except (ValueError, TypeError):
                    continue
                if payload.get("task_id") == task_id and payload.get("event") == (
                    "devops.deployment_simulated"
                ):
                    return payload
        finally:
            await client.aclose()
        return None

    event = asyncio.new_event_loop().run_until_complete(find())
    assert event is not None, "no devops.deployment_simulated event found"
    assert isinstance(event.get("github"), dict)
    assert event["github"]["dry_run"] is True
    assert event["github"]["status"] in ("success", "failed", "disabled")
