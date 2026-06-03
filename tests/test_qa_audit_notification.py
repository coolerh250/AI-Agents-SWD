"""Stage 29 — qa-agent + auto-fix audit + notification event coverage."""

from __future__ import annotations

import asyncio
import os
import sys


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _CodeStoreStub:
    def __init__(self, workspace=None, artifacts=None, pr_draft=None):
        self.workspace = workspace
        self.artifacts = artifacts or []
        self.pr_draft = pr_draft

    async def get_workspace(self, _t):
        return self.workspace

    async def list_code_change_artifacts(self, _t):
        return list(self.artifacts)

    async def get_pr_draft_artifact(self, _t):
        return self.pr_draft


class _TaskStoreStub:
    def __init__(self, work_item=None):
        self.work_item = work_item
        self.discussions: list[dict] = []
        self.status_updates: list[tuple[str, str]] = []

    async def get_work_item(self, _t):
        return self.work_item

    async def add_agent_discussion(self, **kwargs):
        self.discussions.append(kwargs)

        class _R:
            discussion_id = "d-fake"

        return _R()

    async def update_work_item_status(self, task_id, status):
        self.status_updates.append((task_id, status))


class _QAStoreStub:
    def __init__(self):
        self.runs: list[dict] = []
        self.findings: list[dict] = []
        self.fix_requests: list[dict] = []
        self.complete_calls: list[dict] = []

    async def get_latest_validation_run(self, _t):
        return None

    async def create_validation_run(self, **kwargs):
        self.runs.append(kwargs)

        class _R:
            qa_run_id = "run-1"

        return _R()

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
        return None

    async def create_auto_fix_request(self, **kwargs):
        self.fix_requests.append(kwargs)

        class _Req:
            fix_request_id = "fix-1"

        return _Req()


class _BusStub:
    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    async def publish_event(self, stream, msg):
        self.events.append((stream, msg))


def _patch_recorders(monkeypatch):
    audit_calls: list[dict] = []
    notify_calls: list[tuple[str, str, str]] = []

    async def _audit(**kwargs):
        audit_calls.append(kwargs)

    async def _notify(task_id, event_type, message):
        notify_calls.append((task_id, event_type, message))

    qa_module = sys.modules["agent"]
    monkeypatch.setattr(qa_module, "publish_audit_event", _audit)
    monkeypatch.setattr(qa_module, "send_notification", _notify)
    return audit_calls, notify_calls


def _full_pr_body() -> str:
    return (
        "## Summary\nx\n## Changed Files\nx\n## Generated Diff Summary\nx\n"
        "## Validation Result\nx\n## Risk Assessment\nx\n## Rollback Plan\nx\n"
        "## Safety Notes\nx\n"
    )


def _wire(qa_agent, monkeypatch, *, workspace, artifacts, pr_draft, work_item):
    agent = qa_agent.QAAgent.__new__(qa_agent.QAAgent)
    agent.name = "qa-agent"
    agent.output_stream = "stream.deployments"
    agent._code_store = _CodeStoreStub(workspace=workspace, artifacts=artifacts, pr_draft=pr_draft)
    agent._task_store = _TaskStoreStub(work_item=work_item)
    agent._qa_store = _QAStoreStub()
    agent.bus = _BusStub()

    async def _publish(msg):
        agent.bus.events.append((agent.output_stream, msg))

    monkeypatch.setattr(agent, "publish_next", _publish)
    monkeypatch.delenv("QA_MAX_AUTO_FIX_ATTEMPTS", raising=False)
    return agent


class _Artifact:
    def __init__(self, file_path):
        self.file_path = file_path
        self.diff_text = "--- a/x\n+++ b/x\n@@ -0,0 +1 @@\n+x\n"
        self.change_type = "create"

    def to_dict(self):
        return {
            "file_path": self.file_path,
            "diff_text": self.diff_text,
            "change_type": self.change_type,
        }


class _PRDraft:
    def __init__(self, body):
        self.body = body
        self.pr_draft_id = "pr-fake"
        self.status = "ready"
        self.test_results = {"status": "passed"}
        self.risk_assessment = {"risk_level": "low"}

    def to_dict(self):
        return {
            "body": self.body,
            "pr_draft_id": self.pr_draft_id,
            "status": self.status,
            "test_results": self.test_results,
            "risk_assessment": self.risk_assessment,
        }


class _Workspace:
    def __init__(self, path):
        self.workspace_id = "ws-1"
        self.workspace_path = path


class _WI:
    def __init__(self):
        self.task_id = "t1"
        self.execution_mode = "delivery_task"
        self.status = "ready_for_development"
        self.request_type = "dev.api"
        self.description = ""
        self.acceptance_criteria = None

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "execution_mode": self.execution_mode,
            "status": self.status,
            "request_type": self.request_type,
            "description": self.description,
            "acceptance_criteria": self.acceptance_criteria,
        }


def test_qa_pass_emits_audit_validation_started_and_passed(qa_agent, monkeypatch, tmp_path):
    app_rel = "apps/demo-generated/task_api.py"
    test_rel = "tests/generated/test_task_api.py"
    for rel, body in ((app_rel, "x=1\n"), (test_rel, "def test_x():\n    assert True\n")):
        full = os.path.join(str(tmp_path), rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(body)
    agent = _wire(
        qa_agent,
        monkeypatch,
        workspace=_Workspace(str(tmp_path)),
        artifacts=[_Artifact(app_rel), _Artifact(test_rel)],
        pr_draft=_PRDraft(_full_pr_body()),
        work_item=_WI(),
    )
    audit_calls, notify_calls = _patch_recorders(monkeypatch)
    _run(
        agent.handle(
            {
                "event": "development.completed",
                "task_id": "t1",
                "workflow_id": "wf-1",
                "code_generation": {"template": "demo_api"},
            }
        )
    )
    decisions = {c["decision_type"] for c in audit_calls}
    assert "qa_validation_started" in decisions
    assert "qa_validation_passed" in decisions
    notifs = {n[1] for n in notify_calls}
    assert "qa.validation_started" in notifs
    assert "qa.validation_passed" in notifs
    for call in audit_calls:
        refs = call.get("artifact_refs") or {}
        if "production_executed" in refs:
            assert refs["production_executed"] is False


def test_qa_blocked_emits_audit_blocked(qa_agent, monkeypatch, tmp_path):
    rel = "docs/generated/oops.md"
    full = os.path.join(str(tmp_path), rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write("token = ghp_" + "A" * 40 + "\n")
    agent = _wire(
        qa_agent,
        monkeypatch,
        workspace=_Workspace(str(tmp_path)),
        artifacts=[_Artifact(rel)],
        pr_draft=_PRDraft(_full_pr_body()),
        work_item=_WI(),
    )
    audit_calls, notify_calls = _patch_recorders(monkeypatch)
    _run(
        agent.handle(
            {
                "event": "development.completed",
                "task_id": "t1",
                "workflow_id": "wf-1",
                "code_generation": {"template": "documentation"},
            }
        )
    )
    decisions = {c["decision_type"] for c in audit_calls}
    assert "qa_blocked_for_human_review" in decisions
    notifs = {n[1] for n in notify_calls}
    assert "qa.blocked_for_human_review" in notifs
