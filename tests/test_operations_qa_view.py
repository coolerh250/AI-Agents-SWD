"""Stage 29 — /operations/qa/* and qa_validation section tests."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.sdk.qa.models import AutoFixRequest, QAFinding, QAValidationRun

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_operations():
    src = _REPO_ROOT / "apps" / "orchestrator" / "src"
    added = False
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
        added = True
    spec = importlib.util.spec_from_file_location(
        "orchestrator_operations_qa", src / "operations.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if added:
        sys.path.remove(str(src))
    return module


@pytest.fixture
def operations_module():
    return _load_operations()


def _run(task_id="t1", final_result="pass") -> QAValidationRun:
    return QAValidationRun(
        qa_run_id=str(uuid4()),
        task_id=task_id,
        workflow_id="wf-1",
        workspace_id=str(uuid4()),
        pr_draft_id=str(uuid4()),
        status="passed" if final_result == "pass" else "blocked_for_human_review",
        validation_scope="workspace",
        qa_agent="qa-agent",
        total_findings=0,
        blocking_findings=0,
        non_blocking_findings=0,
        auto_fix_attempts=0,
        max_auto_fix_attempts=2,
        final_result=final_result,
        metadata={},
        created_at=datetime.now(timezone.utc).isoformat(),
        completed_at=datetime.now(timezone.utc).isoformat(),
    )


def _finding(task_id="t1", severity="warning") -> QAFinding:
    return QAFinding(
        finding_id=str(uuid4()),
        qa_run_id=str(uuid4()),
        task_id=task_id,
        workflow_id="wf-1",
        workspace_id=str(uuid4()),
        severity=severity,
        category="syntax",
        file_path="apps/demo-generated/x.py",
        title="x",
        description="y",
        recommendation="z",
        auto_fixable=True,
        status="open",
        metadata={},
        created_at=datetime.now(timezone.utc).isoformat(),
        resolved_at=None,
    )


def _fix_request(task_id="t1") -> AutoFixRequest:
    return AutoFixRequest(
        fix_request_id=str(uuid4()),
        task_id=task_id,
        workflow_id="wf-1",
        workspace_id=str(uuid4()),
        qa_run_id=str(uuid4()),
        finding_ids=["f-1"],
        attempt_number=1,
        status="requested",
        requested_by="qa-agent",
        reason="auto_fixable_blocking_findings",
        fix_strategy="deterministic",
        result={},
        created_at=datetime.now(timezone.utc).isoformat(),
        completed_at=None,
    )


class _StubStore:
    def __init__(self, runs=None, findings=None, fix_requests=None):
        self._runs = runs or []
        self._findings = findings or []
        self._fix_requests = fix_requests or []

    async def list_validation_runs(self, **kw):
        return list(self._runs)

    async def get_latest_validation_run(self, _task_id):
        return self._runs[0] if self._runs else None

    async def list_findings(self, _task_id, **kw):
        return list(self._findings)

    async def list_auto_fix_requests(self, _task_id, **kw):
        return list(self._fix_requests)


def _wire_app(monkeypatch, operations_module, store):
    monkeypatch.setattr(operations_module, "QAStore", lambda *a, **kw: store)
    app = FastAPI()
    app.include_router(operations_module.router)
    return TestClient(app)


def test_qa_runs_list_endpoint(monkeypatch, operations_module):
    store = _StubStore(runs=[_run(), _run(task_id="t2", final_result="blocked")])
    client = _wire_app(monkeypatch, operations_module, store)
    resp = client.get("/operations/qa/runs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2


def test_qa_runs_for_task_endpoint(monkeypatch, operations_module):
    store = _StubStore(runs=[_run("t-view-1")])
    client = _wire_app(monkeypatch, operations_module, store)
    resp = client.get("/operations/qa/runs/t-view-1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["task_id"] == "t-view-1"
    assert body["latest_run"]["final_result"] == "pass"


def test_qa_findings_for_task_endpoint(monkeypatch, operations_module):
    store = _StubStore(findings=[_finding("t-find-1"), _finding("t-find-1", severity="critical")])
    client = _wire_app(monkeypatch, operations_module, store)
    resp = client.get("/operations/qa/findings/t-find-1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 2


def test_qa_auto_fix_endpoint(monkeypatch, operations_module):
    store = _StubStore(fix_requests=[_fix_request("t-fix-1")])
    client = _wire_app(monkeypatch, operations_module, store)
    resp = client.get("/operations/qa/auto-fix/t-fix-1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["auto_fix_requests"][0]["status"] == "requested"
