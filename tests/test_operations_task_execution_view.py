"""Stage 27 — /operations/workflows + /operations/tasks task_execution checks."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_operations() -> ModuleType:
    src = _REPO_ROOT / "apps" / "orchestrator" / "src"
    sys.path.insert(0, str(src))
    try:
        # Pre-load progress.py so operations can import it cleanly.
        prog_path = src / "progress.py"
        if prog_path.exists():
            spec = importlib.util.spec_from_file_location("progress", prog_path)
            assert spec is not None and spec.loader is not None
            mod = importlib.util.module_from_spec(spec)
            sys.modules.setdefault("progress", mod)
            spec.loader.exec_module(mod)
        spec = importlib.util.spec_from_file_location("orchestrator_ops", src / "operations.py")
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.pop(0)


@pytest.fixture(scope="module")
def ops():
    try:
        return _load_operations()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"operations module not loadable: {exc}")


class _FakeWorkItem:
    def __init__(self) -> None:
        self.work_item_id = "wi-1"
        self.task_id = "t1"
        self.workflow_id = "wf-1"
        self.title = "title"
        self.description = "desc"
        self.request_type = "dev.test"
        self.execution_mode = "delivery_task"
        self.status = "ready_for_development"
        self.development_required = True
        self.github_required = False
        self.scrum_enabled = False
        self.acceptance_criteria = None
        self.definition_of_done = None
        self.execution_plan = {"stages": ["intake"]}
        self.assumptions: list[Any] = []
        self.open_questions: list[Any] = []
        self.risks: list[Any] = []

    def to_dict(self):
        return {
            "work_item_id": self.work_item_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "execution_mode": self.execution_mode,
            "status": self.status,
            "scrum_enabled": self.scrum_enabled,
            "acceptance_criteria": self.acceptance_criteria,
            "definition_of_done": self.definition_of_done,
        }


class _FakeDiscussion:
    def __init__(self, agent: str, message_type: str) -> None:
        self.agent = agent
        self.message_type = message_type

    def to_dict(self):
        return {"agent": self.agent, "message_type": self.message_type}


class _FakeClarification:
    def __init__(self, status: str = "open"):
        self.status = status

    def to_dict(self):
        return {"status": self.status}


class _FakeStore:
    def __init__(self, work_item=None, discussions=None, clarifications=None, counts=None):
        self._work_item = work_item
        self._discussions = discussions or []
        self._clarifications = clarifications or []
        self._counts = counts or {
            "total_work_items": 2,
            "simple_task_count": 1,
            "delivery_task_count": 1,
            "scrum_project_count": 0,
            "needs_clarification_count": 0,
            "ready_for_development_count": 1,
            "blocked_count": 0,
        }

    async def get_work_item(self, task_id):
        return self._work_item

    async def list_agent_discussions(self, task_id, *, limit=200):
        return list(self._discussions)

    async def list_clarification_requests(self, task_id, *, status=None):
        return list(self._clarifications)

    async def list_work_items(self, *, status=None, execution_mode=None, limit=100):
        return [self._work_item] if self._work_item else []

    async def counts(self):
        return dict(self._counts)


def test_task_execution_summary_returns_counts(ops, monkeypatch):
    fake = _FakeStore()
    monkeypatch.setattr(ops, "TaskExecutionStore", lambda: fake)
    import asyncio

    out = asyncio.new_event_loop().run_until_complete(ops._task_execution_summary())
    assert out["total_work_items"] == 2
    assert out["delivery_task_count"] == 1
    assert out["ready_for_development_count"] == 1


def test_list_work_items_route_returns_count(ops, monkeypatch):
    fake = _FakeStore(work_item=_FakeWorkItem())
    monkeypatch.setattr(ops, "TaskExecutionStore", lambda: fake)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(ops.router)
    client = TestClient(app)
    r = client.get("/operations/tasks/work-items")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["work_items"][0]["task_id"] == "t1"


def test_work_item_view_returns_404_when_missing(ops, monkeypatch):
    fake = _FakeStore(work_item=None)
    monkeypatch.setattr(ops, "TaskExecutionStore", lambda: fake)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(ops.router)
    client = TestClient(app)
    r = client.get("/operations/tasks/work-items/missing")
    assert r.status_code == 404


def test_work_item_view_returns_section(ops, monkeypatch):
    fake = _FakeStore(
        work_item=_FakeWorkItem(),
        discussions=[
            _FakeDiscussion("intake-agent", "analysis"),
            _FakeDiscussion("requirement-agent", "analysis"),
        ],
        clarifications=[_FakeClarification(status="open")],
    )
    monkeypatch.setattr(ops, "TaskExecutionStore", lambda: fake)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(ops.router)
    client = TestClient(app)
    r = client.get("/operations/tasks/work-items/t1")
    assert r.status_code == 200
    body = r.json()
    assert body["work_item"]["task_id"] == "t1"
    assert len(body["agent_discussions"]) == 2
    assert body["open_clarification_count"] == 1
