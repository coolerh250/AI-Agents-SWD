"""orchestrator WorkflowEventConsumer + progress integration tests.

We don't stand up the real Redis / Postgres here — we run handle_event
in-process with a tiny in-memory WorkflowStore stub and assert that the
github result coming off the devops event lands on
``execution_result.github`` and surfaces through ``build_progress``.
"""

from __future__ import annotations

import asyncio
from typing import Any


class _StubStore:
    """Minimal WorkflowStore replacement for the consumer."""

    def __init__(self, workflow: dict[str, Any]) -> None:
        self._workflow = workflow
        self.updates: list[dict[str, Any]] = []

    async def get_workflow_state(self, task_id: str) -> dict | None:
        return self._workflow if self._workflow["task_id"] == task_id else None

    async def update_workflow_state(
        self,
        task_id: str,
        *,
        stage: str,
        state: dict,
        approval_required: bool,
        approval_status: str,
        risk_level: str,
        execution_result: dict,
    ) -> dict:
        self._workflow = dict(self._workflow)
        self._workflow["stage"] = stage
        self._workflow["state"] = state
        self._workflow["approval_required"] = approval_required
        self._workflow["approval_status"] = approval_status
        self._workflow["risk_level"] = risk_level
        self._workflow["execution_result"] = execution_result
        self.updates.append(
            {
                "stage": stage,
                "execution_result": execution_result,
            }
        )
        return self._workflow


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _base_workflow(task_id: str) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "stage": "in_progress",
        "state": {
            "task_id": task_id,
            "workflow_id": f"wf-{task_id}",
            "trace_id": "ab" * 16,
            "stage": "in_progress",
            "execution_result": {"status": "in_progress"},
        },
        "execution_result": {"status": "in_progress"},
        "approval_required": False,
        "approval_status": "none",
        "risk_level": "low",
        "created_at": "2026-05-27T00:00:00+00:00",
        "updated_at": "2026-05-27T00:00:00+00:00",
    }


def test_workflow_event_consumer_persists_github_result():
    from workflow_events import WorkflowEventConsumer  # type: ignore

    workflow = _base_workflow("t-gh-1")
    store = _StubStore(workflow)
    consumer = WorkflowEventConsumer(store=store, event_bus=None)  # type: ignore[arg-type]
    payload = {
        "event": "devops.deployment_simulated",
        "task_id": "t-gh-1",
        "workflow_id": "wf-t-gh-1",
        "deployment_record_id": "abc",
        "github": {
            "status": "success",
            "dry_run": True,
            "issue_url": "https://github.com/owner/repo/issues/1",
            "branch": "ai-agents/t-gh-1",
            "pr_url": "https://github.com/owner/repo/pull/77",
            "pr_number": 77,
            "checks_status": "success",
            "event_type": "github.pr.dry_run",
        },
    }
    updated = _run(consumer.handle_event(payload))
    assert updated is not None
    exec_result = updated["execution_result"]
    assert exec_result["status"] == "completed"
    assert exec_result["production_executed"] is False
    assert exec_result["github"]["pr_url"] == "https://github.com/owner/repo/pull/77"
    assert exec_result["github"]["dry_run"] is True
    assert exec_result["github"]["checks_status"] == "success"


def test_build_progress_exposes_github_fields():
    from progress import build_progress  # type: ignore

    workflow = {
        "task_id": "t-gh-2",
        "stage": "completed",
        "state": {
            "task_id": "t-gh-2",
            "workflow_id": "wf-t-gh-2",
            "trace_id": "cd" * 16,
            "stage": "completed",
            "execution_result": {
                "status": "completed",
                "production_executed": False,
                "github": {
                    "status": "success",
                    "dry_run": True,
                    "pr_url": "https://github.com/owner/repo/pull/77",
                    "pr_number": 77,
                    "branch": "ai-agents/t-gh-2",
                    "issue_url": "",
                    "checks_status": "success",
                    "event_type": "github.pr.dry_run",
                },
            },
        },
        "execution_result": {"status": "completed"},
        "approval_status": "none",
        "updated_at": "2026-05-27T01:00:00+00:00",
    }
    progress = build_progress(workflow, executions=[])
    assert progress["pr_url"] == "https://github.com/owner/repo/pull/77"
    assert progress["github_status"] == "success"
    assert progress["github_dry_run"] is True
    assert progress["github"]["pr_url"] == "https://github.com/owner/repo/pull/77"
    # Timeline event must be appended.
    phases = [entry.get("phase") for entry in progress["agent_timeline"]]
    assert "github.demo_pr.dry_run" in phases


def test_build_progress_renders_failed_timeline_phase():
    from progress import build_progress  # type: ignore

    workflow = {
        "task_id": "t-gh-3",
        "stage": "completed",
        "state": {
            "task_id": "t-gh-3",
            "execution_result": {
                "github": {
                    "status": "failed",
                    "dry_run": True,
                    "error": "http error",
                }
            },
        },
        "execution_result": {"status": "completed"},
        "approval_status": "none",
        "updated_at": "2026-05-27T02:00:00+00:00",
    }
    progress = build_progress(workflow, executions=[])
    phases = [entry.get("phase") for entry in progress["agent_timeline"]]
    assert "github.demo_pr.failed" in phases
    assert progress["github_status"] == "failed"
