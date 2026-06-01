"""Stage 27 — requirement-agent clarification flow."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeStore:
    def __init__(self) -> None:
        self.work_items: list[dict] = []
        self.discussions: list[dict] = []
        self.clarifications: list[dict] = []

    async def create_work_item(self, **kwargs):
        self.work_items.append(kwargs)

        class _WI:
            work_item_id = "wi-fake"
            task_id = kwargs["task_id"]

        return _WI()

    async def add_agent_discussion(self, **kwargs):
        self.discussions.append(kwargs)

        class _D:
            discussion_id = "d-fake"

        return _D()

    async def create_clarification_request(self, **kwargs):
        self.clarifications.append(kwargs)

        class _C:
            clarification_id = "c-fake"

        return _C()


@pytest.fixture
def req_agent(requirement_agent, monkeypatch):
    # __init__ would create real Redis client; bypass via __new__.
    cls = requirement_agent.RequirementAgent
    obj = cls.__new__(cls)
    obj.name = "requirement-agent"
    obj.output_stream = "stream.development"

    async def _noop_publish(*args, **kwargs):
        return "id-1"

    monkeypatch.setattr(obj, "publish_next", _noop_publish)
    obj._store = _FakeStore()
    return obj


def test_clarification_branch_on_tbd(req_agent):
    payload: dict[str, Any] = {
        "task_id": "t-unclear",
        "workflow_id": "wf-1",
        "source": "discord",
        "request": {
            "type": "dev.test",
            "description": "TBD",
            "discord": {"channel_id": "c1", "user_id": "u1"},
        },
    }
    result = _run(req_agent.handle(payload))
    assert result["decision_type"] == "clarification_requested"
    assert result["result"] == "needs_clarification"
    # Work item was created with needs_clarification status.
    assert req_agent._store.work_items[0]["status"] == "needs_clarification"
    # A clarification_requests row was inserted.
    assert len(req_agent._store.clarifications) == 1
    # IMPORTANT: the agent must NOT publish_next on this branch.
    # publish_next is monkey-patched to return "id-1" if called; we use
    # the fact that the result lacks the ready_for_development event_type.
    assert result["event_type"] == "task.needs_clarification"


def test_ready_for_development_branch(req_agent):
    payload: dict[str, Any] = {
        "task_id": "t-ready",
        "workflow_id": "wf-2",
        "source": "discord",
        "request": {
            "type": "dev.test",
            "description": (
                "implement a new /healthz endpoint with a passing test, "
                "wire metrics and update the README"
            ),
            "discord": {"channel_id": "c1", "user_id": "u1"},
        },
    }
    result = _run(req_agent.handle(payload))
    assert result["decision_type"] == "task_ready_for_development"
    # Historical result string preserved for backwards compatibility;
    # downstream stream_agent + tests grep for ``requirement.completed``.
    assert result["result"] == "requirement.completed"
    assert req_agent._store.work_items[0]["execution_mode"] == "delivery_task"
    assert req_agent._store.work_items[0]["status"] == "ready_for_development"
    assert len(req_agent._store.clarifications) == 0  # no clarification needed


def test_scrum_mode_only_when_explicit_keyword(req_agent):
    payload: dict[str, Any] = {
        "task_id": "t-scrum",
        "workflow_id": "wf-3",
        "source": "discord",
        "request": {
            "type": "general",
            "description": (
                "project kickoff: please populate the sprint backlog, draft "
                "the acceptance criteria, and pin the definition of done"
            ),
            "discord": {"channel_id": "c1", "user_id": "u1"},
        },
    }
    result = _run(req_agent.handle(payload))
    assert result["artifact_refs"]["execution_mode"] == "scrum_project"
    wi = req_agent._store.work_items[0]
    assert wi["execution_mode"] == "scrum_project"
    assert wi["scrum_enabled"] is True
    # Scrum bootstrapped acceptance criteria + DoD because the
    # explicit keyword triggered scrum_project mode.
    assert wi["acceptance_criteria"] is not None
    assert wi["definition_of_done"] is not None
    assert wi["scrum_metadata"]["project_kickoff"] is True


def test_simple_task_does_not_get_scrum_fields(req_agent):
    payload: dict[str, Any] = {
        "task_id": "t-simple",
        "workflow_id": "wf-4",
        "source": "discord",
        "request": {
            "type": "general",
            "description": ("please summarise the docs intro into three bullet points"),
            "discord": {"channel_id": "c1", "user_id": "u1"},
        },
    }
    _run(req_agent.handle(payload))
    wi = req_agent._store.work_items[0]
    assert wi["execution_mode"] == "simple_task"
    assert wi["scrum_enabled"] is False
    assert wi["acceptance_criteria"] is None
    assert wi["definition_of_done"] is None


def test_discussion_recorded_on_every_branch(req_agent):
    payload: dict[str, Any] = {
        "task_id": "t-d",
        "workflow_id": "wf-d",
        "source": "discord",
        "request": {
            "type": "dev.test",
            "description": "implement a new endpoint, add tests, ship it",
            "discord": {"channel_id": "c1", "user_id": "u1"},
        },
    }
    _run(req_agent.handle(payload))
    assert any(d["agent"] == "requirement-agent" for d in req_agent._store.discussions)
