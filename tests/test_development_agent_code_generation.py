"""Stage 28 — development-agent controlled code generation flow tests.

These drive ``DevelopmentAgent.handle`` against fake stores; no Postgres
/ Redis is touched. The fixtures inject ``_task_store`` + ``_code_store``
via ``__new__`` + attribute assignment so the StreamAgent base init is
bypassed.
"""

from __future__ import annotations

import asyncio
from typing import Any


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeTaskStore:
    def __init__(self) -> None:
        self.discussions: list[dict] = []

    async def get_work_item(self, task_id):
        class _WI:
            work_item_id = "wi-fake"
            execution_mode = "delivery_task"
            status = "ready_for_development"

        return _WI()

    async def add_agent_discussion(self, **kwargs):
        self.discussions.append(kwargs)

        class _R:
            discussion_id = "d-fake"

        return _R()


class _FakeCodeStore:
    def __init__(self) -> None:
        self.workspaces: list[dict] = []
        self.workspace_status_updates: list[tuple[str, str]] = []
        self.artifacts: list[dict] = []
        self.pr_drafts: list[dict] = []
        self._current_status = "created"
        self._current_gen_mode = "deterministic_template"
        self._blocked_reason = ""

    async def get_workspace(self, task_id):
        if not self.workspaces:
            return None

        class _WS:
            workspace_id = "ws-fake"
            status = self._current_status
            execution_mode = "delivery_task"
            generator_mode = self._current_gen_mode
            blocked_reason = self._blocked_reason

            def to_dict(_self):
                return {"workspace_id": "ws-fake", "status": _self.status}

        return _WS()

    async def create_workspace(self, **kwargs):
        self.workspaces.append(kwargs)
        self._current_status = kwargs.get("status", "created")
        self._current_gen_mode = kwargs.get("generator_mode", "deterministic_template")
        self._blocked_reason = kwargs.get("blocked_reason", "")

        class _WS:
            workspace_id = "ws-fake"
            status = self._current_status
            execution_mode = "delivery_task"
            generator_mode = self._current_gen_mode
            blocked_reason = self._blocked_reason

        return _WS()

    async def update_workspace_status(self, task_id, status, **kwargs):
        self._current_status = status
        if kwargs.get("blocked_reason") is not None:
            self._blocked_reason = kwargs["blocked_reason"]
        self.workspace_status_updates.append((task_id, status))
        return None

    async def add_code_change_artifact(self, **kwargs):
        self.artifacts.append(kwargs)

        class _A:
            artifact_id = f"art-{len(self.artifacts)}"

        return _A()

    async def create_pr_draft_artifact(self, **kwargs):
        self.pr_drafts.append(kwargs)

        class _D:
            pr_draft_id = "pr-fake"
            title = kwargs.get("title", "")
            status = kwargs.get("status", "draft")

        return _D()

    async def get_pr_draft_artifact(self, task_id):
        return None


def _wire_agent(development_agent, monkeypatch, tmp_path):
    agent = development_agent.DevelopmentAgent.__new__(development_agent.DevelopmentAgent)
    agent.name = "development-agent"
    agent.output_stream = "stream.qa"
    agent._task_store = _FakeTaskStore()
    agent._code_store = _FakeCodeStore()

    async def _publish(_msg):
        return "stream-1"

    monkeypatch.setattr(agent, "publish_next", _publish)
    monkeypatch.setenv("DEVELOPMENT_AGENT_WORKSPACE_ROOT", str(tmp_path))
    return agent


def test_docs_task_creates_workspace_artifact_and_pr_draft(
    development_agent, monkeypatch, tmp_path
):
    agent = _wire_agent(development_agent, monkeypatch, tmp_path)
    payload = {
        "task_id": "doc-task-1",
        "workflow_id": "wf-1",
        "request": {"type": "dev.doc", "description": "please write the documentation"},
    }
    result = _run(agent.handle(payload))
    assert result["decision_type"] == "code_generated"
    assert any(p.endswith(".md") for p in result["artifact_refs"]["changed_files"])
    assert agent._code_store.workspaces, "workspace created"
    assert agent._code_store.artifacts, "artifact recorded"
    assert agent._code_store.pr_drafts, "pr draft created"
    assert result["artifact_refs"]["production_executed"] is False


def test_api_task_writes_app_and_test_files(development_agent, monkeypatch, tmp_path):
    agent = _wire_agent(development_agent, monkeypatch, tmp_path)
    payload = {
        "task_id": "api-task-1",
        "workflow_id": "wf-2",
        "request": {"type": "dev.api", "description": "build a /healthz endpoint API"},
    }
    result = _run(agent.handle(payload))
    files = result["artifact_refs"]["changed_files"]
    assert any(f.startswith("apps/demo-generated/") and f.endswith(".py") for f in files)
    assert any(f.startswith("tests/generated/") and f.endswith(".py") for f in files)


def test_blocked_when_description_does_not_match(development_agent, monkeypatch, tmp_path):
    agent = _wire_agent(development_agent, monkeypatch, tmp_path)
    payload = {
        "task_id": "blocked-task-1",
        "workflow_id": "wf-3",
        "request": {"type": "dev.test", "description": "qwertyuiop"},
    }
    result = _run(agent.handle(payload))
    assert result["decision_type"] == "code_generation_blocked"
    assert result["artifact_refs"]["changed_files"] == []
    # No PR draft produced when blocked.
    assert agent._code_store.pr_drafts == []


def test_blocked_when_work_item_not_ready(development_agent, monkeypatch, tmp_path):
    agent = _wire_agent(development_agent, monkeypatch, tmp_path)

    class _NotReadyTaskStore(_FakeTaskStore):
        async def get_work_item(_self, task_id):
            class _WI:
                work_item_id = "wi-fake"
                execution_mode = "delivery_task"
                status = "needs_clarification"

            return _WI()

    agent._task_store = _NotReadyTaskStore()
    payload = {
        "task_id": "blocked-task-2",
        "workflow_id": "wf-4",
        "request": {"type": "dev.doc", "description": "write documentation"},
    }
    result = _run(agent.handle(payload))
    assert result["decision_type"] == "code_generation_blocked"


def test_simulated_failure_short_circuits_before_generation(
    development_agent, monkeypatch, tmp_path
):
    import sys

    import pytest

    agent_module = sys.modules["agent"]
    agent = _wire_agent(development_agent, monkeypatch, tmp_path)

    with pytest.raises(agent_module.SimulatedFailure):
        _run(
            agent.handle(
                {
                    "task_id": "fail-1",
                    "workflow_id": "wf-5",
                    "request": {"simulate_failure": True},
                }
            )
        )
    # No workspace should have been created.
    assert agent._code_store.workspaces == []


def test_publishes_development_completed_event(development_agent, monkeypatch, tmp_path):
    """The downstream qa-agent contract is unchanged — event is the same."""
    agent = _wire_agent(development_agent, monkeypatch, tmp_path)

    published: list[dict[str, Any]] = []

    async def _publish(msg):
        published.append(msg)
        return "stream-1"

    monkeypatch.setattr(agent, "publish_next", _publish)
    payload = {
        "task_id": "evt-task-1",
        "workflow_id": "wf-6",
        "request": {"type": "dev.doc", "description": "write the documentation"},
    }
    _run(agent.handle(payload))
    assert published and published[0]["event"] == "development.completed"
    assert "code_generation" in published[0]
