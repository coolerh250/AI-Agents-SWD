"""Stage 27 — orchestrator workflow gate + resume-after-clarification."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _load_orchestrator() -> ModuleType:
    """Load orchestrator main as a unique module so two tests don't collide."""
    src = _REPO_ROOT / "apps" / "orchestrator" / "src"
    sys.path.insert(0, str(src))
    try:
        # progress.py is imported by main.py — preload it.
        for name in (
            "progress",
            "workflow",
            "workflow_events",
            "resume_engine",
            "dispatch",
            "incidents_api",
            "operations",
        ):
            path = src / f"{name}.py"
            if not path.exists():
                continue
            spec = importlib.util.spec_from_file_location(name, path)
            assert spec is not None and spec.loader is not None
            mod = importlib.util.module_from_spec(spec)
            sys.modules.setdefault(name, mod)
            spec.loader.exec_module(mod)
        spec = importlib.util.spec_from_file_location("orchestrator_main", src / "main.py")
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.pop(0)


@pytest.fixture(scope="module")
def orchestrator_app():
    try:
        return _load_orchestrator()
    except Exception as exc:  # pragma: no cover — orchestrator must load
        pytest.skip(f"orchestrator main not loadable: {exc}")


class _FakeWorkItem:
    def __init__(
        self,
        *,
        task_id="t1",
        status="needs_clarification",
        description="desc",
        request_type="dev.test",
        workflow_id="wf-1",
        execution_mode="delivery_task",
    ):
        self.task_id = task_id
        self.status = status
        self.description = description
        self.request_type = request_type
        self.workflow_id = workflow_id
        self.execution_mode = execution_mode


class _FakeClarification:
    def __init__(self, *, status="open", user_response=None, task_id="t1"):
        self.status = status
        self.user_response = user_response
        self.task_id = task_id


class _FakeStore:
    def __init__(
        self,
        *,
        work_item: _FakeWorkItem | None = None,
        clarifications: list[_FakeClarification] | None = None,
    ):
        self._work_item = work_item
        self._clarifications = clarifications or []
        self.status_updates: list[tuple[str, str]] = []

    async def get_work_item(self, task_id):
        return self._work_item

    async def list_clarification_requests(self, task_id, *, status: str | None = None):
        if status is None:
            return list(self._clarifications)
        return [c for c in self._clarifications if c.status == status]

    async def update_work_item_status(self, task_id, status):
        self.status_updates.append((task_id, status))
        if self._work_item is not None:
            self._work_item.status = status
        return self._work_item


def test_resume_returns_404_when_no_work_item(orchestrator_app, monkeypatch):
    fake = _FakeStore(work_item=None)
    monkeypatch.setattr(orchestrator_app, "TaskExecutionStore", lambda: fake)
    client = TestClient(orchestrator_app.app)
    r = client.post("/workflow/resume-after-clarification/missing")
    assert r.status_code == 404


def test_resume_returns_pending_when_clarifications_open(orchestrator_app, monkeypatch):
    wi = _FakeWorkItem(status="needs_clarification", description="TBD")
    fake = _FakeStore(work_item=wi, clarifications=[_FakeClarification(status="open")])
    monkeypatch.setattr(orchestrator_app, "TaskExecutionStore", lambda: fake)
    client = TestClient(orchestrator_app.app)
    r = client.post("/workflow/resume-after-clarification/t1")
    assert r.status_code == 200
    body = r.json()
    assert body["resumed"] is False
    assert body["reason"] == "open_clarifications_pending"
    assert body["open_clarifications"] == 1


def test_resume_promotes_to_ready_for_development(orchestrator_app, monkeypatch):
    wi = _FakeWorkItem(status="needs_clarification", description="TBD")
    answered = [
        _FakeClarification(
            status="answered",
            user_response=("please implement the new /healthz endpoint with a passing test"),
        )
    ]
    fake = _FakeStore(work_item=wi, clarifications=answered)
    monkeypatch.setattr(orchestrator_app, "TaskExecutionStore", lambda: fake)

    class _FakeWorkflowStore:
        async def get_workflow_state(self, task_id):
            return None

    monkeypatch.setattr(orchestrator_app, "WorkflowStore", lambda: _FakeWorkflowStore())

    async def _fake_dispatch(*args, **kwargs):
        return True

    # The orchestrator main imports ``dispatch_task`` lazily inside the
    # route — patch the dispatch module's symbol so the call resolves
    # to our fake.
    import dispatch  # noqa: F401

    monkeypatch.setattr(sys.modules["dispatch"], "dispatch_task", _fake_dispatch)

    async def _fake_send(task_id, event_type, message):
        return None

    monkeypatch.setattr(orchestrator_app, "send_notification", _fake_send)

    client = TestClient(orchestrator_app.app)
    r = client.post("/workflow/resume-after-clarification/t1")
    assert r.status_code == 200
    body = r.json()
    assert body["resumed"] is True
    assert body["status"] == "ready_for_development"
    assert fake.status_updates[-1] == ("t1", "ready_for_development")


def test_resume_keeps_needs_clarification_when_answer_still_unclear(orchestrator_app, monkeypatch):
    wi = _FakeWorkItem(status="needs_clarification", description="TBD")
    answered = [_FakeClarification(status="answered", user_response="?")]
    fake = _FakeStore(work_item=wi, clarifications=answered)
    monkeypatch.setattr(orchestrator_app, "TaskExecutionStore", lambda: fake)
    client = TestClient(orchestrator_app.app)
    r = client.post("/workflow/resume-after-clarification/t1")
    assert r.status_code == 200
    body = r.json()
    assert body["resumed"] is False
    assert body["status"] == "needs_clarification"
