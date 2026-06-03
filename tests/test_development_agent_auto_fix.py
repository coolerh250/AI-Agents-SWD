"""Stage 29 — development-agent CodeAutoFixAgent flow tests."""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass, field
from typing import Any


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@dataclass
class _FakeWorkspace:
    workspace_id: str = "ws-fake"
    workspace_path: str = "/tmp/aiagents-workspaces/t1"


@dataclass
class _FakePRDraft:
    body: str
    pr_draft_id: str = "pr-fake"
    workflow_id: str | None = "wf-1"
    workspace_id: str | None = "ws-fake"
    title: str = "title"
    changed_files: list = field(default_factory=list)
    test_results: dict = field(default_factory=dict)
    risk_assessment: dict = field(default_factory=dict)
    rollback_plan: str = ""
    github_dry_run_result: dict = field(default_factory=dict)
    status: str = "ready"


@dataclass
class _FakeFinding:
    finding_id: str
    category: str
    auto_fixable: bool
    file_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class _FakeWorkItem:
    description: str
    request_type: str
    status: str = "ready_for_development"


class _FakeCodeStore:
    def __init__(self, workspace=None, pr_draft=None):
        self._workspace = workspace
        self._pr_draft = pr_draft
        self.pr_draft_writes: list[dict] = []
        self.artifacts: list[dict] = []

    async def get_workspace(self, _task_id):
        return self._workspace

    async def get_pr_draft_artifact(self, _task_id):
        return self._pr_draft

    async def create_pr_draft_artifact(self, **kwargs):
        self.pr_draft_writes.append(kwargs)

        class _D:
            pr_draft_id = "pr-after-fix"
            title = kwargs.get("title", "")
            status = kwargs.get("status", "ready")

        return _D()

    async def add_code_change_artifact(self, **kwargs):
        self.artifacts.append(kwargs)

        class _A:
            artifact_id = f"art-{len(self.artifacts)}"

        return _A()


class _FakeQAStore:
    def __init__(self, findings=None):
        self._findings = findings or []
        self.finding_status_updates: list[tuple[str, str, bool]] = []
        self.fix_request_updates: list[dict] = []

    async def list_findings(self, _task_id, qa_run_id=None):
        return list(self._findings)

    async def update_finding_status(self, finding_id, *, status, resolved=False):
        self.finding_status_updates.append((finding_id, status, resolved))
        return None

    async def update_auto_fix_request(self, fix_request_id, *, status, result=None):
        self.fix_request_updates.append(
            {"fix_request_id": fix_request_id, "status": status, "result": result}
        )

        class _R:
            status_value = status

        return _R()


class _FakeTaskStore:
    def __init__(self, work_item=None):
        self._wi = work_item

    async def get_work_item(self, _task_id):
        return self._wi


class _FakeBus:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    async def publish_event(self, stream, msg):
        self.events.append((stream, msg))
        return "stream-id-1"


def _wire(
    development_agent, monkeypatch, *, workspace=None, pr_draft=None, findings=None, work_item=None
):
    agent_module = sys.modules["agent"]
    agent = agent_module.CodeAutoFixAgent.__new__(agent_module.CodeAutoFixAgent)
    agent.name = "development-agent-autofix"
    agent.output_stream = "stream.qa"
    agent._code_store = _FakeCodeStore(workspace=workspace, pr_draft=pr_draft)
    agent._qa_store = _FakeQAStore(findings=findings or [])
    agent._task_store = _FakeTaskStore(work_item=work_item)
    agent.bus = _FakeBus()

    async def _publish(msg):
        agent.bus.events.append((agent.output_stream, msg))
        return "stream-1"

    monkeypatch.setattr(agent, "publish_next", _publish)

    async def _noop(*a, **kw):
        return None

    monkeypatch.setattr(agent_module, "publish_audit_event", _noop)
    monkeypatch.setattr(agent_module, "send_notification", _noop)
    monkeypatch.setenv("DEVELOPMENT_AGENT_WORKSPACE_ROOT", "/tmp/aiagents-workspaces")
    return agent


def test_fix_pr_draft_sections_appends_missing(development_agent, monkeypatch):
    pr_draft = _FakePRDraft(body="## Summary\nstub\n")
    finding = _FakeFinding(
        finding_id="f-1",
        category="documentation",
        auto_fixable=True,
        metadata={"missing_sections": ["## Safety Notes", "## Rollback Plan"]},
    )
    agent = _wire(
        development_agent,
        monkeypatch,
        workspace=_FakeWorkspace(),
        pr_draft=pr_draft,
        findings=[finding],
    )
    result = _run(
        agent.handle(
            {
                "task_id": "t1",
                "workflow_id": "wf-1",
                "fix_request_id": "fix-1",
                "qa_run_id": "run-1",
                "attempt_number": 1,
                "finding_ids": ["f-1"],
            }
        )
    )
    assert result["decision_type"] == "code_auto_fix_completed"
    assert agent._code_store.pr_draft_writes, "PR draft re-written"
    new_body = agent._code_store.pr_draft_writes[0]["body"]
    assert "## Safety Notes" in new_body
    assert "## Rollback Plan" in new_body
    # The auto_fix_request must be marked completed.
    assert agent._qa_store.fix_request_updates[-1]["status"] == "completed"
    # Re-publishes onto stream.qa so QA re-validates.
    streams = {s for s, _ in agent.bus.events}
    assert "stream.qa" in streams


def test_fix_refused_when_finding_not_auto_fixable(development_agent, monkeypatch):
    finding = _FakeFinding(finding_id="f-1", category="security", auto_fixable=False)
    agent = _wire(development_agent, monkeypatch, workspace=_FakeWorkspace(), findings=[finding])
    result = _run(
        agent.handle(
            {
                "task_id": "t1",
                "workflow_id": "wf-1",
                "fix_request_id": "fix-2",
                "qa_run_id": "run-2",
                "attempt_number": 1,
                "finding_ids": ["f-1"],
            }
        )
    )
    assert result["decision_type"] == "code_auto_fix_failed"
    assert agent._qa_store.fix_request_updates[-1]["status"] == "failed"


def test_fix_test_file_regenerates_via_template(development_agent, monkeypatch, tmp_path):
    """A 'test' category finding triggers template-driven regeneration."""
    finding = _FakeFinding(finding_id="f-1", category="test", auto_fixable=True)
    work_item = _FakeWorkItem(
        description="please implement a /healthz endpoint API with tests",
        request_type="dev.api",
        status="ready_for_development",
    )
    workspace = _FakeWorkspace(workspace_path=str(tmp_path))
    agent = _wire(
        development_agent,
        monkeypatch,
        workspace=workspace,
        findings=[finding],
        work_item=work_item,
    )
    result = _run(
        agent.handle(
            {
                "task_id": "t1",
                "workflow_id": "wf-1",
                "fix_request_id": "fix-3",
                "qa_run_id": "run-3",
                "attempt_number": 1,
                "finding_ids": ["f-1"],
            }
        )
    )
    assert result["decision_type"] == "code_auto_fix_completed"
    # The deterministic generator should have produced both app + test files.
    written_paths: list[str] = []
    for art in agent._code_store.artifacts:
        written_paths.append(art["file_path"])
    assert any(p.startswith("apps/demo-generated/") for p in written_paths)
    assert any(p.startswith("tests/generated/") for p in written_paths)
    # Workspace files actually exist on disk too.
    for p in written_paths:
        assert os.path.isfile(os.path.join(str(tmp_path), p))


def test_fix_refused_when_work_item_missing(development_agent, monkeypatch):
    """A test-category finding can't regenerate without the work item."""
    finding = _FakeFinding(finding_id="f-1", category="test", auto_fixable=True)
    agent = _wire(
        development_agent,
        monkeypatch,
        workspace=_FakeWorkspace(),
        findings=[finding],
        work_item=None,
    )
    result = _run(
        agent.handle(
            {
                "task_id": "t1",
                "workflow_id": "wf-1",
                "fix_request_id": "fix-4",
                "qa_run_id": "run-4",
                "attempt_number": 1,
                "finding_ids": ["f-1"],
            }
        )
    )
    assert result["decision_type"] == "code_auto_fix_failed"


def test_fix_publishes_development_auto_fix_completed_event(development_agent, monkeypatch):
    pr_draft = _FakePRDraft(body="## Summary\nstub\n")
    finding = _FakeFinding(
        finding_id="f-1",
        category="documentation",
        auto_fixable=True,
        metadata={"missing_sections": ["## Safety Notes"]},
    )
    agent = _wire(
        development_agent,
        monkeypatch,
        workspace=_FakeWorkspace(),
        pr_draft=pr_draft,
        findings=[finding],
    )
    _run(
        agent.handle(
            {
                "task_id": "t1",
                "workflow_id": "wf-1",
                "fix_request_id": "fix-5",
                "qa_run_id": "run-5",
                "attempt_number": 1,
                "finding_ids": ["f-1"],
            }
        )
    )
    event_types = [msg.get("event") for _stream, msg in agent.bus.events]
    assert "development.auto_fix_completed" in event_types
