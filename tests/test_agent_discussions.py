"""Stage 27 — verify each pipeline agent appends an agent_discussion row.

The tests load each agent module + drive ``handle`` against a fake
TaskExecutionStore so we can assert which message_types the platform
emits for each agent. No real Postgres / Redis is touched.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeStore:
    def __init__(self) -> None:
        self.discussions: list[dict] = []
        self.work_item_status_updates: list[tuple[str, str]] = []

    async def add_agent_discussion(self, **kwargs):
        self.discussions.append(kwargs)

        class _R:
            discussion_id = "d-fake"
            agent = kwargs.get("agent", "")
            message_type = kwargs.get("message_type", "")

        return _R()

    async def create_work_item(self, **kwargs):
        class _WI:
            work_item_id = "wi-fake"
            task_id = kwargs.get("task_id", "")

        return _WI()

    async def get_work_item(self, task_id):
        return None

    async def create_clarification_request(self, **kwargs):
        class _C:
            clarification_id = "c-fake"

        return _C()

    async def update_work_item_status(self, task_id, status):
        self.work_item_status_updates.append((task_id, status))
        return None


class _FakeCodeStore:
    """Stand-in for CodeWorkspaceStore — records calls; no Postgres."""

    def __init__(self) -> None:
        self.workspaces: list[dict] = []
        self.artifacts: list[dict] = []
        self.pr_drafts: list[dict] = []
        self.workspace_status_updates: list[tuple[str, str]] = []

    async def get_workspace(self, task_id):
        if not self.workspaces:
            return None
        last = self.workspaces[-1]

        class _WS:
            workspace_id = "ws-fake"
            status = last.get("status", "created")
            execution_mode = last.get("execution_mode", "delivery_task")
            generator_mode = last.get("generator_mode", "deterministic_template")
            blocked_reason = last.get("blocked_reason", "")

            def to_dict(self):
                return {"workspace_id": "ws-fake", "status": _WS.status}

        return _WS()

    async def create_workspace(self, **kwargs):
        self.workspaces.append(kwargs)

        class _WS:
            workspace_id = "ws-fake"
            status = kwargs.get("status", "created")
            execution_mode = kwargs.get("execution_mode", "delivery_task")
            generator_mode = kwargs.get("generator_mode", "deterministic_template")
            blocked_reason = kwargs.get("blocked_reason", "")

        return _WS()

    async def update_workspace_status(self, task_id, status, **kwargs):
        self.workspace_status_updates.append((task_id, status))
        return None

    async def add_code_change_artifact(self, **kwargs):
        self.artifacts.append(kwargs)

        class _A:
            artifact_id = "art-fake"

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

    async def list_code_change_artifacts(self, task_id):
        return []


@pytest.fixture
def agent_payload():
    return {
        "task_id": "t-disc",
        "workflow_id": "wf-disc",
        "source": "discord",
        "request": {"type": "dev.test", "description": "implement a new endpoint"},
    }


def _patch_publish(monkeypatch, agent_obj):
    async def _noop(*args, **kwargs):
        return "stream-id-1"

    monkeypatch.setattr(agent_obj, "publish_next", _noop)


def test_intake_agent_records_discussion(intake_agent, agent_payload, monkeypatch):
    agent = intake_agent.IntakeAgent.__new__(intake_agent.IntakeAgent)
    # IntakeAgent.__init__ does I/O; sidestep by attribute injection.
    agent.name = "intake-agent"
    agent.output_stream = "stream.requirements"
    fake_store = _FakeStore()
    agent._task_store = fake_store
    _patch_publish(monkeypatch, agent)

    result = _run(agent.handle(agent_payload))
    assert result["decision_type"] == "intake"
    assert len(fake_store.discussions) == 1
    assert fake_store.discussions[0]["agent"] == "intake-agent"
    assert fake_store.discussions[0]["message_type"] == "analysis"


def test_development_agent_records_execution_plan_discussion(
    development_agent, agent_payload, monkeypatch, tmp_path
):
    agent = development_agent.DevelopmentAgent.__new__(development_agent.DevelopmentAgent)
    agent.name = "development-agent"
    agent.output_stream = "stream.qa"
    fake_store = _FakeStore()
    agent._task_store = fake_store
    agent._code_store = _FakeCodeStore()
    _patch_publish(monkeypatch, agent)
    monkeypatch.setenv("DEVELOPMENT_AGENT_WORKSPACE_ROOT", str(tmp_path))

    result = _run(agent.handle(agent_payload))
    # Stage 28: development-agent now classifies + generates code; the
    # decision_type reflects the controlled-generation outcome rather
    # than the legacy "development" string. "implement a new endpoint"
    # hits the demo_api template so files are written.
    assert result["decision_type"] in ("code_generated", "code_generation_blocked")
    assert any(
        d["agent"] == "development-agent" and d["message_type"] == "execution_plan"
        for d in fake_store.discussions
    )


def test_qa_agent_records_validation_note(qa_agent, agent_payload, monkeypatch):
    agent = qa_agent.QAAgent.__new__(qa_agent.QAAgent)
    agent.name = "qa-agent"
    agent.output_stream = "stream.deployments"
    fake_store = _FakeStore()
    agent._task_store = fake_store
    _patch_publish(monkeypatch, agent)

    result = _run(agent.handle(agent_payload))
    assert result["decision_type"] == "qa"
    assert any(
        d["agent"] == "qa-agent" and d["message_type"] == "validation_note"
        for d in fake_store.discussions
    )


def test_discussion_records_carry_task_id(intake_agent, agent_payload, monkeypatch):
    agent = intake_agent.IntakeAgent.__new__(intake_agent.IntakeAgent)
    agent.name = "intake-agent"
    agent.output_stream = "stream.requirements"
    fake_store = _FakeStore()
    agent._task_store = fake_store
    _patch_publish(monkeypatch, agent)

    _run(agent.handle(agent_payload))
    assert fake_store.discussions[0]["task_id"] == "t-disc"
    assert fake_store.discussions[0]["workflow_id"] == "wf-disc"


# Conftest fixtures used:
_ = Path(__file__)  # silence unused-import-check on local lints
