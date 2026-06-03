"""Stage 29 — workflow event consumer routes QA decisions to the right stages."""

from __future__ import annotations

import asyncio


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeStore:
    """In-memory workflow store stub that records update_workflow_state calls."""

    def __init__(self, initial_state=None):
        self.workflow = {
            "task_id": "t1",
            "state": initial_state or {"stage": "in_progress"},
            "execution_result": initial_state or {},
            "stage": "in_progress",
            "approval_required": False,
            "approval_status": "none",
            "risk_level": "low",
            "created_at": "2026-06-02T00:00:00+00:00",
        }
        self.calls: list[dict] = []

    async def get_workflow_state(self, _task_id):
        return dict(self.workflow)

    async def update_workflow_state(self, task_id, **kwargs):
        self.calls.append({"task_id": task_id, **kwargs})
        merged = dict(self.workflow)
        merged.update(kwargs)
        merged["task_id"] = task_id
        self.workflow = merged
        return merged


def _consumer_module():
    import importlib.util
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "orchestrator_workflow_events",
        repo / "apps" / "orchestrator" / "src" / "workflow_events.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_qa_auto_fix_requested_flips_stage_to_qa_auto_fix(monkeypatch):
    we = _consumer_module()
    store = _FakeStore()
    consumer = we.WorkflowEventConsumer(store=store, event_bus=None)
    _run(
        consumer.handle_event(
            {
                "event": "qa.auto_fix_requested",
                "task_id": "t1",
                "workflow_id": "wf-1",
                "qa_run_id": "run-1",
                "fix_request_id": "fix-1",
                "attempt_number": 1,
                "max_auto_fix_attempts": 2,
            }
        )
    )
    assert store.calls, "workflow state updated"
    last = store.calls[-1]
    assert last["stage"] == "qa_auto_fix"
    assert last["execution_result"]["qa_auto_fix"]["fix_request_id"] == "fix-1"


def test_qa_blocked_for_human_review_flips_stage(monkeypatch):
    we = _consumer_module()
    store = _FakeStore()
    consumer = we.WorkflowEventConsumer(store=store, event_bus=None)
    _run(
        consumer.handle_event(
            {
                "event": "qa.blocked_for_human_review",
                "task_id": "t1",
                "workflow_id": "wf-1",
                "qa_run_id": "run-1",
                "reason": "unfixable_blocking_findings",
                "blocking_finding_ids": ["f-1"],
            }
        )
    )
    assert store.calls, "workflow state updated"
    last = store.calls[-1]
    assert last["stage"] == "blocked_for_human_review"
    assert last["execution_result"]["qa_blocked"]["reason"] == "unfixable_blocking_findings"
    assert last["execution_result"]["production_executed"] is False


def test_qa_completed_advances_workflow_in_progress(monkeypatch):
    we = _consumer_module()
    store = _FakeStore()
    consumer = we.WorkflowEventConsumer(store=store, event_bus=None)
    _run(
        consumer.handle_event(
            {
                "event": "qa.completed",
                "task_id": "t1",
                "workflow_id": "wf-1",
            }
        )
    )
    assert store.calls
    last = store.calls[-1]
    assert last["stage"] == "in_progress"
    assert last["execution_result"]["agent_progress"]["qa-agent"] == "completed"


def test_auto_fix_completed_keeps_workflow_in_progress(monkeypatch):
    we = _consumer_module()
    store = _FakeStore()
    consumer = we.WorkflowEventConsumer(store=store, event_bus=None)
    _run(
        consumer.handle_event(
            {
                "event": "development.auto_fix_completed",
                "task_id": "t1",
                "workflow_id": "wf-1",
            }
        )
    )
    last = store.calls[-1]
    assert last["stage"] == "in_progress"
    assert last["execution_result"]["agent_progress"]["development-agent-autofix"] == "completed"


def test_devops_event_after_qa_pass_completes_workflow(monkeypatch):
    we = _consumer_module()
    store = _FakeStore()
    consumer = we.WorkflowEventConsumer(store=store, event_bus=None)
    _run(
        consumer.handle_event(
            {
                "event": "devops.deployment_simulated",
                "task_id": "t1",
                "workflow_id": "wf-1",
                "deployment_record_id": "dep-1",
                "github": {"dry_run": True, "status": "success", "pr_url": "https://x"},
            }
        )
    )
    last = store.calls[-1]
    assert last["stage"] == "completed"
    assert last["execution_result"]["production_executed"] is False
