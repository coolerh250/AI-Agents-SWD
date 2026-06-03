"""Stage 29 — qa-agent validation flow tests.

Each test drives ``QAAgent.handle`` against fake stores; no Postgres /
Redis is touched. The fixtures bypass the StreamAgent base init by
constructing the agent via ``__new__`` and injecting attributes.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@dataclass
class _FakeWorkspace:
    workspace_id: str = "ws-fake"
    workspace_path: str = "/tmp/aiagents-workspaces/t1"
    status: str = "ready_for_pr_draft"
    execution_mode: str = "delivery_task"
    generator_mode: str = "deterministic_template"
    blocked_reason: str = ""


@dataclass
class _FakeArtifact:
    file_path: str
    diff_text: str = "--- a/x\n+++ b/x\n@@ -0,0 +1 @@\n+hello\n"
    change_type: str = "create"

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": self.file_path,
            "diff_text": self.diff_text,
            "change_type": self.change_type,
        }


@dataclass
class _FakePRDraft:
    body: str
    pr_draft_id: str = "pr-fake"
    status: str = "ready"
    test_results: dict[str, Any] | None = None
    risk_assessment: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pr_draft_id": self.pr_draft_id,
            "status": self.status,
            "body": self.body,
            "test_results": self.test_results or {"status": "passed"},
            "risk_assessment": self.risk_assessment or {"risk_level": "low"},
        }


@dataclass
class _FakeWorkItem:
    task_id: str = "t1"
    execution_mode: str = "delivery_task"
    status: str = "ready_for_development"
    request_type: str = "dev.api"
    description: str = ""
    acceptance_criteria: list | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "execution_mode": self.execution_mode,
            "status": self.status,
            "request_type": self.request_type,
            "description": self.description,
            "acceptance_criteria": self.acceptance_criteria,
        }


class _FakeCodeStore:
    def __init__(self, workspace=None, artifacts=None, pr_draft=None):
        self._workspace = workspace
        self._artifacts = artifacts or []
        self._pr_draft = pr_draft

    async def get_workspace(self, _task_id):
        return self._workspace

    async def list_code_change_artifacts(self, _task_id):
        return list(self._artifacts)

    async def get_pr_draft_artifact(self, _task_id):
        return self._pr_draft


class _FakeTaskStore:
    def __init__(self, work_item=None):
        self._wi = work_item
        self.discussions: list[dict] = []
        self.status_updates: list[tuple[str, str]] = []

    async def get_work_item(self, _task_id):
        return self._wi

    async def add_agent_discussion(self, **kwargs):
        self.discussions.append(kwargs)

        class _R:
            discussion_id = "d-fake"

        return _R()

    async def update_work_item_status(self, task_id, status):
        self.status_updates.append((task_id, status))


class _FakeQAStore:
    def __init__(self):
        self.runs: list[dict] = []
        self.findings: list[dict] = []
        self.fix_requests: list[dict] = []
        self.complete_calls: list[dict] = []
        self._latest_attempts = 0

    async def get_latest_validation_run(self, _task_id):
        if not self.runs:
            return None

        class _R:
            auto_fix_attempts = self._latest_attempts

        return _R()

    async def create_validation_run(self, **kwargs):
        self.runs.append(kwargs)

        class _Run:
            qa_run_id = f"run-{len(self.runs)}"
            auto_fix_attempts = kwargs.get("auto_fix_attempts", 0)
            max_auto_fix_attempts = kwargs.get("max_auto_fix_attempts", 2)

        return _Run()

    async def add_finding(self, **kwargs):
        self.findings.append(kwargs)

        class _F:
            finding_id = f"f-{len(self.findings)}"
            severity = kwargs["severity"]
            category = kwargs["category"]
            auto_fixable = kwargs["auto_fixable"]

        return _F()

    async def complete_validation_run(self, qa_run_id, **kwargs):
        self.complete_calls.append({"qa_run_id": qa_run_id, **kwargs})

        class _Run:
            qa_run_id = "run-1"

        return _Run()

    async def create_auto_fix_request(self, **kwargs):
        self.fix_requests.append(kwargs)

        class _Req:
            fix_request_id = f"fix-{len(self.fix_requests)}"

        return _Req()


class _FakeBus:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    async def publish_event(self, stream, message):
        self.events.append((stream, message))
        return "stream-id-1"


async def _no_audit(**kwargs):
    return None


async def _no_notify(*args, **kwargs):
    return None


def _wire(qa_agent, monkeypatch, *, workspace=None, artifacts=None, pr_draft=None, work_item=None):
    agent = qa_agent.QAAgent.__new__(qa_agent.QAAgent)
    agent.name = "qa-agent"
    agent.output_stream = "stream.deployments"
    agent._code_store = _FakeCodeStore(workspace=workspace, artifacts=artifacts, pr_draft=pr_draft)
    agent._task_store = _FakeTaskStore(work_item=work_item)
    agent._qa_store = _FakeQAStore()
    agent.bus = _FakeBus()

    async def _publish(_msg):
        agent.bus.events.append((agent.output_stream, _msg))
        return "stream-1"

    monkeypatch.setattr(agent, "publish_next", _publish)
    # Suppress real audit + notification side effects.
    import sys

    qa_module = sys.modules["agent"]
    monkeypatch.setattr(qa_module, "publish_audit_event", _no_audit)
    monkeypatch.setattr(qa_module, "send_notification", _no_notify)
    # Don't touch QA_MAX_AUTO_FIX_ATTEMPTS here — individual tests set it.
    return agent


def _full_pr_body() -> str:
    return (
        "## Summary\nx\n## Changed Files\nx\n## Generated Diff Summary\nx\n"
        "## Validation Result\nx\n## Risk Assessment\nx\n## Rollback Plan\nx\n"
        "## Safety Notes\nx\n"
    )


def test_qa_pass_when_no_blocking_findings(qa_agent, monkeypatch, tmp_path):
    # Write the actual files so validate_generated_files_exist passes.
    app_rel = "apps/demo-generated/task_api.py"
    test_rel = "tests/generated/test_task_api.py"
    for rel, body in ((app_rel, "x = 1\n"), (test_rel, "def test_x():\n    assert True\n")):
        full = os.path.join(str(tmp_path), rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(body)
    workspace = _FakeWorkspace(workspace_path=str(tmp_path))
    artifacts = [_FakeArtifact(file_path=app_rel), _FakeArtifact(file_path=test_rel)]
    pr_draft = _FakePRDraft(body=_full_pr_body())
    work_item = _FakeWorkItem()
    agent = _wire(
        qa_agent,
        monkeypatch,
        workspace=workspace,
        artifacts=artifacts,
        pr_draft=pr_draft,
        work_item=work_item,
    )
    result = _run(
        agent.handle(
            {
                "event": "development.completed",
                "task_id": "t1",
                "workflow_id": "wf-1",
                "code_generation": {"template": "demo_api"},
            }
        )
    )
    assert result["decision_type"] == "qa_validation_passed"
    assert result["event_type"] == "qa.completed"
    assert any(s == "stream.deployments" for s, _ in agent.bus.events)


def test_qa_auto_fix_when_blocking_auto_fixable(qa_agent, monkeypatch, tmp_path):
    # Missing test file is auto-fixable; app file exists, test file does not.
    app_rel = "apps/demo-generated/task_api.py"
    full_app = os.path.join(str(tmp_path), app_rel)
    os.makedirs(os.path.dirname(full_app), exist_ok=True)
    with open(full_app, "w", encoding="utf-8") as fh:
        fh.write("x = 1\n")
    workspace = _FakeWorkspace(workspace_path=str(tmp_path))
    artifacts = [_FakeArtifact(file_path=app_rel)]
    # PR draft missing required sections → another auto-fixable blocking finding.
    pr_draft = _FakePRDraft(body="## Summary\nstub\n")
    work_item = _FakeWorkItem()
    agent = _wire(
        qa_agent,
        monkeypatch,
        workspace=workspace,
        artifacts=artifacts,
        pr_draft=pr_draft,
        work_item=work_item,
    )
    result = _run(
        agent.handle(
            {
                "event": "development.completed",
                "task_id": "t1",
                "workflow_id": "wf-1",
                "code_generation": {"template": "demo_api"},
            }
        )
    )
    assert result["decision_type"] == "qa_auto_fix_requested"
    # Both an auto-fix request stream and a qa.auto_fix_requested event onto stream.qa.
    streams = {s for s, _ in agent.bus.events}
    assert "stream.development.autofix" in streams
    assert "stream.qa" in streams
    assert agent._qa_store.fix_requests, "auto_fix_request row created"


def test_qa_blocked_when_unfixable_critical(qa_agent, monkeypatch, tmp_path):
    # Put a secret pattern in the file -> security critical, not auto-fixable.
    rel = "docs/generated/oops.md"
    full = os.path.join(str(tmp_path), rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write("token = ghp_" + "A" * 40 + "\n")
    workspace = _FakeWorkspace(workspace_path=str(tmp_path))
    artifacts = [_FakeArtifact(file_path=rel)]
    pr_draft = _FakePRDraft(body=_full_pr_body())
    agent = _wire(
        qa_agent,
        monkeypatch,
        workspace=workspace,
        artifacts=artifacts,
        pr_draft=pr_draft,
        work_item=_FakeWorkItem(),
    )
    result = _run(
        agent.handle(
            {
                "event": "development.completed",
                "task_id": "t1",
                "workflow_id": "wf-1",
                "code_generation": {"template": "documentation"},
            }
        )
    )
    assert result["decision_type"] == "qa_blocked_for_human_review"
    streams = {s for s, _ in agent.bus.events}
    assert "stream.qa" in streams
    assert "stream.development.autofix" not in streams


def test_max_attempts_blocks_even_when_auto_fixable(qa_agent, monkeypatch, tmp_path):
    """When auto_fix_attempts == max, an auto-fixable finding still blocks."""
    app_rel = "apps/demo-generated/task_api.py"
    full_app = os.path.join(str(tmp_path), app_rel)
    os.makedirs(os.path.dirname(full_app), exist_ok=True)
    with open(full_app, "w", encoding="utf-8") as fh:
        fh.write("x = 1\n")
    workspace = _FakeWorkspace(workspace_path=str(tmp_path))
    artifacts = [_FakeArtifact(file_path=app_rel)]
    pr_draft = _FakePRDraft(body="## Summary\nstub\n")
    work_item = _FakeWorkItem()
    monkeypatch.setenv("QA_MAX_AUTO_FIX_ATTEMPTS", "1")
    agent = _wire(
        qa_agent,
        monkeypatch,
        workspace=workspace,
        artifacts=artifacts,
        pr_draft=pr_draft,
        work_item=work_item,
    )
    result = _run(
        agent.handle(
            {
                "event": "development.auto_fix_completed",
                "task_id": "t1",
                "workflow_id": "wf-1",
                "code_generation": {"template": "demo_api"},
            }
        )
    )
    assert result["decision_type"] == "qa_blocked_for_human_review"
    assert "max_attempts" in str(result["artifact_refs"]["reason"]).lower()


def test_qa_ignores_self_emitted_event(qa_agent, monkeypatch):
    agent = _wire(qa_agent, monkeypatch)
    result = _run(
        agent.handle(
            {
                "event": "qa.auto_fix_requested",
                "task_id": "t1",
                "workflow_id": "wf-1",
            }
        )
    )
    assert result["decision_type"] == "qa_ignored_self_event"
