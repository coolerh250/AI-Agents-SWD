"""devops-agent → github-automation integration unit tests.

We swap out the real httpx-backed GitHubAutomationHttpClient with a fake
that records the call args and returns a canned envelope. That lets us
assert the agent:

* calls github-automation by default (request.github omitted),
* skips the call when ``request.github.enabled = false``,
* folds the github result into the deployment_records metadata,
* surfaces the github result in the devops.deployment_simulated event,
* still completes the deployment when github-automation fails,
* never marks ``production_executed = true``.
"""

from __future__ import annotations

import asyncio
from typing import Any


class _FakeClient:
    """Drop-in replacement for GitHubAutomationHttpClient."""

    def __init__(self, *, result: dict[str, Any] | None = None) -> None:
        self.result = result or {
            "status": "success",
            "dry_run": True,
            "issue_url": "https://github.com/owner/repo/issues/1",
            "branch": "ai-agents/t1",
            "pr_url": "https://github.com/owner/repo/pull/99",
            "pr_number": 99,
            "checks_status": "success",
            "event_type": "github.pr.dry_run",
        }
        self.calls: list[dict[str, Any]] = []

    async def run_demo_pr(
        self, payload: dict[str, Any], *, task_id: str = "", workflow_id: str = ""
    ) -> dict:
        self.calls.append({"payload": payload, "task_id": task_id, "workflow_id": workflow_id})
        return dict(self.result)


def _agent(devops_agent, **kwargs):
    """Build a DevOpsAgent with the fake github client injected."""
    return devops_agent.DevOpsAgent(github_client=kwargs.pop("github_client"), **kwargs)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def test_handle_calls_github_automation_by_default(devops_agent, monkeypatch):
    # Avoid touching Postgres in the unit test — the persistence step is
    # exercised in test_devops_agent.py.
    async def _no_db(self, record):  # type: ignore[no-self-use]
        return None

    monkeypatch.setattr(devops_agent.DevOpsAgent, "_persist_deployment_record", _no_db)
    client = _FakeClient()
    agent = _agent(devops_agent, github_client=client)
    payload = {
        "task_id": "t-default",
        "workflow_id": "wf-t-default",
        "request": {"type": "dev.test"},
    }

    async def _noop_publish(self, message):  # type: ignore[no-self-use]
        self._last_message = message
        return "0-0"

    monkeypatch.setattr(devops_agent.DevOpsAgent, "publish_next", _noop_publish)
    result = _run(agent.handle(payload))
    assert len(client.calls) == 1, "github automation must be called by default"
    call = client.calls[0]
    assert call["payload"]["task_id"] == "t-default"
    assert call["payload"]["dry_run"] is True
    assert call["payload"]["repo"]  # populated from default env
    # Result envelope carries github bits.
    assert result["decision_type"] == "github_pr_integration"
    assert result["event_type"] == "github.pr.dry_run"
    assert result["artifact_refs"]["production_executed"] is False
    assert result["artifact_refs"]["pr_url"] == "https://github.com/owner/repo/pull/99"
    assert result["artifact_refs"]["dry_run"] is True
    # execution_metadata (== record) includes github result for downstream.
    assert result["execution_metadata"]["github"]["pr_url"] == (
        "https://github.com/owner/repo/pull/99"
    )
    assert result["execution_metadata"]["production_executed"] is False


def test_handle_skips_github_when_enabled_false(devops_agent, monkeypatch):
    async def _no_db(self, record):  # type: ignore[no-self-use]
        return None

    monkeypatch.setattr(devops_agent.DevOpsAgent, "_persist_deployment_record", _no_db)
    client = _FakeClient()
    agent = _agent(devops_agent, github_client=client)
    payload = {
        "task_id": "t-skip",
        "workflow_id": "wf-t-skip",
        "request": {
            "type": "dev.test",
            "github": {"enabled": False, "disabled_reason": "test opt-out"},
        },
    }

    async def _noop_publish(self, message):  # type: ignore[no-self-use]
        self._last_message = message
        return "0-0"

    monkeypatch.setattr(devops_agent.DevOpsAgent, "publish_next", _noop_publish)
    result = _run(agent.handle(payload))
    assert client.calls == [], "github automation must not be called when enabled=false"
    assert result["execution_metadata"]["github"]["status"] == "disabled"
    assert result["execution_metadata"]["github"]["disabled_reason"] == "test opt-out"
    assert result["execution_metadata"]["production_executed"] is False


def test_handle_keeps_running_on_github_failure(devops_agent, monkeypatch):
    async def _no_db(self, record):  # type: ignore[no-self-use]
        return None

    monkeypatch.setattr(devops_agent.DevOpsAgent, "_persist_deployment_record", _no_db)
    client = _FakeClient(
        result={
            "status": "failed",
            "dry_run": True,
            "error": "http error: ConnectError",
            "issue_url": "",
            "branch": "ai-agents/t-fail",
            "pr_url": "",
            "checks_status": "unknown",
            "event_type": "github.pr.failed",
        }
    )
    agent = _agent(devops_agent, github_client=client)

    async def _noop_publish(self, message):  # type: ignore[no-self-use]
        self._last_message = message
        return "0-0"

    monkeypatch.setattr(devops_agent.DevOpsAgent, "publish_next", _noop_publish)
    payload = {
        "task_id": "t-fail",
        "workflow_id": "wf-t-fail",
        "request": {"type": "dev.test"},
    }
    result = _run(agent.handle(payload))
    assert result["decision_type"] == "github_pr_integration"
    assert result["result"] == "failed"
    assert result["event_type"] == "github.pr.failed"
    assert result["execution_metadata"]["github"]["status"] == "failed"
    assert result["execution_metadata"]["production_executed"] is False


def test_published_event_carries_github_block(devops_agent, monkeypatch):
    """The devops.deployment_simulated event published to stream.devops must
    contain a top-level ``github`` field so the orchestrator workflow-event
    consumer can backfill workflow_states.execution_result.github."""

    async def _no_db(self, record):  # type: ignore[no-self-use]
        return None

    monkeypatch.setattr(devops_agent.DevOpsAgent, "_persist_deployment_record", _no_db)
    captured: dict[str, Any] = {}

    async def _capture_publish(self, message):  # type: ignore[no-self-use]
        captured["message"] = message
        return "0-0"

    monkeypatch.setattr(devops_agent.DevOpsAgent, "publish_next", _capture_publish)
    client = _FakeClient()
    agent = _agent(devops_agent, github_client=client)
    _run(
        agent.handle(
            {
                "task_id": "t-evt",
                "workflow_id": "wf-t-evt",
                "request": {"type": "dev.test"},
            }
        )
    )
    msg = captured["message"]
    assert msg["event"] == "devops.deployment_simulated"
    assert msg["github"]["status"] == "success"
    assert msg["github"]["pr_url"] == "https://github.com/owner/repo/pull/99"
    assert msg["github"]["dry_run"] is True
