"""Stage 30 — audit + notification side-effect tests for the LLM planner.

The planner pipeline emits:

* ``llm_proposal_created`` / ``llm_proposal_blocked`` audit decision
* one ``llm_interaction_recorded`` per LLM call
* ``llm.proposal_created`` / ``llm.proposal_blocked`` /
  ``llm.proposal_policy_passed`` notification events
* ``llm.real_test_skipped`` notification when the external provider
  guard is active

Here we patch the publishers to in-memory recorders and assert the
shape of every call.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_ROOT = Path(__file__).resolve().parents[1]


def _load_planner() -> ModuleType:
    if "llm_planner" in sys.modules:
        return sys.modules["llm_planner"]
    src = _ROOT / "agents" / "development-agent" / "src"
    for name in ("code_generator", "llm_planner"):
        if name in sys.modules:
            continue
        spec = importlib.util.spec_from_file_location(name, src / f"{name}.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    return sys.modules["llm_planner"]


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeLLMStore:
    def __init__(self) -> None:
        self.interactions: list[dict] = []
        self.proposals: list[dict] = []
        self.usage: list[dict] = []
        self.status_updates: list[tuple] = []

    async def record_interaction(self, **kwargs):
        self.interactions.append(kwargs)

        class _R:
            interaction_id = f"i-{len(self.interactions)}"
            status = "ok"

        return _R()

    async def record_proposal(self, **kwargs):
        self.proposals.append(kwargs)

        class _R:
            proposal_id = f"p-{len(self.proposals)}"
            status = kwargs["status"]
            requires_human_review = True

        return _R()

    async def update_proposal_status(self, pid, *, status, linked_workspace_id=None):
        self.status_updates.append((pid, status, linked_workspace_id))

    async def record_usage(self, **kwargs):
        self.usage.append(kwargs)

        class _R:
            usage_id = f"u-{len(self.usage)}"

        return _R()


def _patch_audit_notify(monkeypatch, planner):
    audit_calls: list[dict] = []
    notify_calls: list[tuple] = []

    async def _fake_publish_audit_event(**kwargs):
        audit_calls.append(kwargs)
        return "audit-1"

    async def _fake_send_notification(task_id, event_type, message):
        notify_calls.append((task_id, event_type, message))

    monkeypatch.setattr(planner, "publish_audit_event", _fake_publish_audit_event)
    monkeypatch.setattr(planner, "send_notification", _fake_send_notification)
    return audit_calls, notify_calls


def test_planner_emits_audit_and_notification_on_pass(monkeypatch):
    planner = _load_planner()
    audit, notify = _patch_audit_notify(monkeypatch, planner)
    pipeline = planner.LLMPlannerPipeline()
    pipeline._llm_store = _FakeLLMStore()
    _run(
        pipeline.run(
            task_id="t-pass",
            workflow_id="w1",
            description="please add /healthz api",
            request_type="dev.api",
            execution_mode="delivery_task",
            acceptance_criteria=None,
        )
    )
    decision_types = {a["decision_type"] for a in audit}
    assert "llm_proposal_created" in decision_types
    assert "llm_interaction_recorded" in decision_types
    event_types = {n[1] for n in notify}
    assert "llm.proposal_created" in event_types
    assert "llm.proposal_policy_passed" in event_types


def test_planner_emits_audit_and_notification_on_block(monkeypatch):
    planner = _load_planner()
    audit, notify = _patch_audit_notify(monkeypatch, planner)
    pipeline = planner.LLMPlannerPipeline()
    pipeline._llm_store = _FakeLLMStore()
    _run(
        pipeline.run(
            task_id="t-deny",
            workflow_id="w1",
            description="please denied path",
            request_type="dev.api",
            execution_mode="delivery_task",
            acceptance_criteria=None,
        )
    )
    decision_types = {a["decision_type"] for a in audit}
    assert "llm_proposal_blocked" in decision_types
    event_types = {n[1] for n in notify}
    assert "llm.proposal_blocked" in event_types


def test_audit_payload_does_not_leak_api_key(monkeypatch):
    planner = _load_planner()
    audit, _ = _patch_audit_notify(monkeypatch, planner)
    pipeline = planner.LLMPlannerPipeline()
    pipeline._llm_store = _FakeLLMStore()
    leaky = "please add api OPENAI_API_KEY=sk-" + "A" * 40
    _run(
        pipeline.run(
            task_id="t-leak",
            workflow_id="w1",
            description=leaky,
            request_type="dev.api",
            execution_mode="delivery_task",
            acceptance_criteria=None,
        )
    )
    flat = " ".join(str(call) for call in audit)
    assert "sk-" + "A" * 40 not in flat


def test_audit_payload_marks_production_executed_false(monkeypatch):
    planner = _load_planner()
    audit, _ = _patch_audit_notify(monkeypatch, planner)
    pipeline = planner.LLMPlannerPipeline()
    pipeline._llm_store = _FakeLLMStore()
    _run(
        pipeline.run(
            task_id="t-pe",
            workflow_id="w1",
            description="please add api",
            request_type="dev.api",
            execution_mode="delivery_task",
            acceptance_criteria=None,
        )
    )
    for call in audit:
        refs = call.get("artifact_refs") or {}
        assert refs.get("production_executed") is False
        assert refs.get("real_call") is False


def test_external_provider_emits_real_test_skipped_notification(monkeypatch):
    planner = _load_planner()
    audit, notify = _patch_audit_notify(monkeypatch, planner)
    pipeline = planner.LLMPlannerPipeline(provider_name="external_openai_placeholder")
    pipeline._llm_store = _FakeLLMStore()
    _run(
        pipeline.run(
            task_id="t-ext",
            workflow_id="w1",
            description="please add api",
            request_type="dev.api",
            execution_mode="delivery_task",
            acceptance_criteria=None,
        )
    )
    event_types = {n[1] for n in notify}
    assert "llm.real_test_skipped" in event_types
    decision_types = {a["decision_type"] for a in audit}
    assert "llm_real_test_skipped" in decision_types
