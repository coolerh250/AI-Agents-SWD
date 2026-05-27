"""Stage 19 unified-audit-path tests.

The three Stage 17 producers (devops-agent github_pr_integration,
retry-scheduler workflow_failed, github-automation github_automation) used to
write into audit_logs over HTTP. As of Stage 19 they publish onto
``stream.audit`` and the audit-worker consumes + persists. These tests assert
the producers actually publish to the stream — we monkey-patch
``shared.sdk.audit.publisher.publish_audit_event`` and check the call shape.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _load_devops_agent() -> ModuleType:
    src = Path(__file__).resolve().parents[1] / "agents" / "devops-agent" / "src"
    agent_spec = importlib.util.spec_from_file_location("agent", src / "agent.py")
    assert agent_spec is not None and agent_spec.loader is not None
    module = importlib.util.module_from_spec(agent_spec)
    import sys

    sys.modules["agent"] = module
    agent_spec.loader.exec_module(module)
    return module


def _load_retry_scheduler() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "apps" / "retry-scheduler" / "src" / "scheduler.py"
    spec = importlib.util.spec_from_file_location("scheduler", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_github_automation_module() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "apps" / "github-automation" / "src" / "main.py"
    spec = importlib.util.spec_from_file_location("github_automation_main", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Captured:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def capture(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        return "1-0"


def test_devops_agent_publishes_github_pr_integration_to_stream_audit(monkeypatch):
    agent_module = _load_devops_agent()
    captured = _Captured()
    monkeypatch.setattr(agent_module, "publish_audit_event", captured.capture)

    devops_agent = agent_module.DevOpsAgent()
    record = {"task_id": "t-dev", "workflow_id": "wf-dev"}
    github_result = {
        "status": "success",
        "dry_run": True,
        "pr_url": "https://github.com/x/y/pull/1",
        "branch": "ai-agents/t-dev",
        "issue_url": "https://github.com/x/y/issues/1",
    }
    _run(devops_agent._write_github_audit(record, github_result))

    assert len(captured.calls) == 1
    call = captured.calls[0]
    assert call["agent"] == "devops-agent"
    assert call["decision_type"] == "github_pr_integration"
    assert call["task_id"] == "t-dev"
    assert call["workflow_id"] == "wf-dev"
    assert call["result"] == "success"
    refs = call["artifact_refs"]
    assert refs["pr_url"] == "https://github.com/x/y/pull/1"
    assert refs["dry_run"] is True


def test_retry_scheduler_publishes_workflow_failed_to_stream_audit(monkeypatch):
    scheduler = _load_retry_scheduler()
    captured = _Captured()
    monkeypatch.setattr(scheduler, "publish_audit_event", captured.capture)

    # Side-effect helpers (incident store, notifications, workflow store) all
    # use contextlib.suppress, so we don't need to stub them — they fail
    # silently and the function still reaches the audit publish.
    scheduler_instance = scheduler.RetryScheduler()
    payload = {
        "task_id": "t-fail",
        "workflow_id": "wf-fail",
        "failure_reason": "boom",
        "original_stream": "stream.development",
    }
    _run(scheduler_instance._on_terminal_failure(payload, message_id="9-9"))

    assert any(
        call["decision_type"] == "workflow_failed" and call["agent"] == "retry-scheduler"
        for call in captured.calls
    ), captured.calls


def test_github_automation_publishes_github_automation_to_stream_audit(monkeypatch):
    module = _load_github_automation_module()
    captured = _Captured()
    monkeypatch.setattr(module, "publish_audit_event", captured.capture)

    _run(
        module._record_audit(
            task_id="t-gha",
            workflow_id="wf-gha",
            summary="GitHub demo PR (dry-run)",
            result="ok",
            artifact_refs={"pr_url": "https://github.com/x/y/pull/1", "dry_run": True},
        )
    )
    assert len(captured.calls) == 1
    call = captured.calls[0]
    assert call["agent"] == "github-automation"
    assert call["decision_type"] == "github_automation"
    assert call["task_id"] == "t-gha"
    assert call["workflow_id"] == "wf-gha"
    assert call["result"] == "ok"


def test_no_direct_http_audit_client_in_migrated_modules():
    """Regression guard: the three migrated modules no longer import AuditHttpClient.

    Keeping a stray HTTP import would silently create a second write path; this
    test fails fast if anyone re-adds it.
    """
    migrated = [
        Path(__file__).resolve().parents[1] / "agents" / "devops-agent" / "src" / "agent.py",
        Path(__file__).resolve().parents[1] / "apps" / "retry-scheduler" / "src" / "scheduler.py",
        Path(__file__).resolve().parents[1] / "apps" / "github-automation" / "src" / "main.py",
    ]
    for path in migrated:
        text = path.read_text(encoding="utf-8")
        assert "from shared.sdk.http_clients.audit_http_client import" not in text, path
        assert "AuditHttpClient(" not in text, path


@pytest.mark.asyncio
async def test_publish_audit_event_safe_on_redis_error(monkeypatch):
    """publish_audit_event must NEVER raise into the caller's hot path."""
    from shared.sdk.audit import publisher

    class _BoomBus:
        async def publish_event(self, *_a: Any, **_kw: Any) -> str:
            raise RuntimeError("redis down")

        async def close(self) -> None:
            return None

    out = await publisher.publish_audit_event(
        task_id="t",
        agent="x",
        decision_type="d",
        summary="s",
        result="r",
        event_bus=_BoomBus(),
    )
    assert out is None
