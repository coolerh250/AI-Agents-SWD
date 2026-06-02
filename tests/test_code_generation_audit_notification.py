"""Stage 28 — assert development-agent emits the right audit / notification
events for the controlled code generation lifecycle.
"""

from __future__ import annotations

import asyncio
from typing import Any


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _RecordingFakeTaskStore:
    async def get_work_item(self, task_id):
        class _WI:
            work_item_id = "wi-fake"
            execution_mode = "delivery_task"
            status = "ready_for_development"

        return _WI()

    async def add_agent_discussion(self, **kwargs):
        class _R:
            discussion_id = "d-fake"

        return _R()


class _RecordingFakeCodeStore:
    def __init__(self) -> None:
        self.workspaces: list[dict] = []
        self.artifacts: list[dict] = []
        self.pr_drafts: list[dict] = []
        self._status = "created"
        self._gen_mode = "deterministic_template"

    async def get_workspace(self, task_id):
        if not self.workspaces:
            return None

        class _WS:
            workspace_id = "ws-fake"
            status = self._status
            execution_mode = "delivery_task"
            generator_mode = self._gen_mode
            blocked_reason = ""

            def to_dict(_self):
                return {"workspace_id": "ws-fake", "status": _self.status}

        return _WS()

    async def create_workspace(self, **kwargs):
        self.workspaces.append(kwargs)
        self._status = kwargs.get("status", self._status)
        self._gen_mode = kwargs.get("generator_mode", self._gen_mode)

        class _WS:
            workspace_id = "ws-fake"
            status = self._status
            execution_mode = "delivery_task"
            generator_mode = self._gen_mode
            blocked_reason = kwargs.get("blocked_reason", "")

        return _WS()

    async def update_workspace_status(self, task_id, status, **kwargs):
        self._status = status
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


def _patch_audit_and_notify(monkeypatch, _agent_mod):
    """Patch the names imported into ``agent.py`` so the dev-agent's
    ``publish_audit_event`` and ``send_notification`` calls land on
    these recorders instead of the real Stage 19 stream / notification
    plumbing.
    """
    import sys

    audit_calls: list[dict[str, Any]] = []
    notify_calls: list[tuple[str, str, str]] = []

    async def _audit(**kwargs):
        audit_calls.append(kwargs)

    async def _notify(task_id, event_type, message):
        notify_calls.append((task_id, event_type, message))

    agent_module = sys.modules["agent"]
    monkeypatch.setattr(agent_module, "publish_audit_event", _audit)
    monkeypatch.setattr(agent_module, "send_notification", _notify)
    return audit_calls, notify_calls


def _wire(development_agent, monkeypatch, tmp_path):
    agent = development_agent.DevelopmentAgent.__new__(development_agent.DevelopmentAgent)
    agent.name = "development-agent"
    agent.output_stream = "stream.qa"
    agent._task_store = _RecordingFakeTaskStore()
    agent._code_store = _RecordingFakeCodeStore()

    async def _publish(_msg):
        return "stream-1"

    monkeypatch.setattr(agent, "publish_next", _publish)
    monkeypatch.setenv("DEVELOPMENT_AGENT_WORKSPACE_ROOT", str(tmp_path))
    return agent


def test_successful_generation_emits_full_audit_and_notification_chain(
    development_agent, monkeypatch, tmp_path
):
    agent = _wire(development_agent, monkeypatch, tmp_path)
    audit_calls, notify_calls = _patch_audit_and_notify(monkeypatch, development_agent)
    payload = {
        "task_id": "audit-1",
        "workflow_id": "wf-audit-1",
        "request": {"type": "dev.api", "description": "build a /healthz endpoint API"},
    }
    _run(agent.handle(payload))

    decision_types = {c["decision_type"] for c in audit_calls}
    assert "code_workspace_created" in decision_types
    assert "code_generated" in decision_types
    assert "code_validation_passed" in decision_types
    assert "code_pr_draft_created" in decision_types

    notif_types = {n[1] for n in notify_calls}
    assert "code.workspace_created" in notif_types
    assert "code.generated" in notif_types
    assert "code.validation_passed" in notif_types
    assert "code.pr_draft_ready" in notif_types

    # production_executed must be false in every audit row.
    for call in audit_calls:
        refs = call.get("artifact_refs") or {}
        if "production_executed" in refs:
            assert refs["production_executed"] is False


def test_blocked_generation_emits_blocked_audit_and_notification(
    development_agent, monkeypatch, tmp_path
):
    agent = _wire(development_agent, monkeypatch, tmp_path)
    audit_calls, notify_calls = _patch_audit_and_notify(monkeypatch, development_agent)
    payload = {
        "task_id": "audit-blocked-1",
        "workflow_id": "wf-audit-2",
        "request": {"type": "dev.test", "description": "qwertyuiop"},
    }
    _run(agent.handle(payload))

    decision_types = {c["decision_type"] for c in audit_calls}
    assert "code_generation_blocked" in decision_types
    notif_types = {n[1] for n in notify_calls}
    assert "code.generation_blocked" in notif_types


def test_validation_failure_emits_failed_event(development_agent, monkeypatch, tmp_path):
    agent = _wire(development_agent, monkeypatch, tmp_path)
    audit_calls, notify_calls = _patch_audit_and_notify(monkeypatch, development_agent)

    # Force the validator to fail py_compile by monkeypatching the
    # development-agent's validate_python_syntax_if_py import.
    import sys

    def _fail(workspace_path, files):
        return False, "py_compile_error:forced"

    monkeypatch.setattr(sys.modules["agent"], "validate_python_syntax_if_py", _fail)

    payload = {
        "task_id": "audit-validate-1",
        "workflow_id": "wf-audit-3",
        "request": {"type": "dev.api", "description": "build a /healthz endpoint API"},
    }
    _run(agent.handle(payload))

    decision_types = {c["decision_type"] for c in audit_calls}
    assert "code_validation_failed" in decision_types
    notif_types = {n[1] for n in notify_calls}
    assert "code.validation_failed" in notif_types
