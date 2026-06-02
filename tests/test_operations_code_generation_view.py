"""Stage 28 — operations API code_generation view tests."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from shared.sdk.code_workspace.models import (
    CodeChangeArtifact,
    CodeWorkspace,
    PRDraftArtifact,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_operations():
    """Load the orchestrator's operations.py as a standalone module.

    apps/orchestrator/src has multiple sibling files (workflow.py,
    progress.py, …) that operations.py imports. We mirror the
    sys.path manipulation that conftest does for the main service so
    those imports resolve.
    """
    src = _REPO_ROOT / "apps" / "orchestrator" / "src"
    added = False
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
        added = True
    spec = importlib.util.spec_from_file_location("orchestrator_operations", src / "operations.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if added:
        sys.path.remove(str(src))
    return module


@pytest.fixture
def operations_module():
    return _load_operations()


def _ws_model(task_id: str = "t1", status: str = "ready_for_pr_draft") -> CodeWorkspace:
    return CodeWorkspace(
        workspace_id=str(uuid4()),
        task_id=task_id,
        workflow_id="wf-1",
        work_item_id=str(uuid4()),
        execution_mode="delivery_task",
        status=status,
        base_commit="abc",
        branch_name=f"ai-agents/{task_id}",
        workspace_path=f"/tmp/aiagents-workspaces/{task_id}",
        allowed_paths=["docs/generated/"],
        denied_paths=[".github/*"],
        generator_mode="deterministic_template",
        blocked_reason="",
        created_by_agent="development-agent",
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )


def _artifact_model(task_id: str = "t1") -> CodeChangeArtifact:
    return CodeChangeArtifact(
        artifact_id=str(uuid4()),
        task_id=task_id,
        workflow_id="wf-1",
        workspace_id=str(uuid4()),
        file_path=f"docs/generated/{task_id}.md",
        change_type="create",
        diff_summary="+5/-0 across 1 hunk(s)",
        diff_text="@@ -0,0 +1 @@\n+hello\n",
        generated_content_preview="hello",
        validation_status="passed",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _pr_draft_model(task_id: str = "t1") -> PRDraftArtifact:
    return PRDraftArtifact(
        pr_draft_id=str(uuid4()),
        task_id=task_id,
        workflow_id="wf-1",
        workspace_id=str(uuid4()),
        title=f"[ai-agents-swd] documentation — {task_id}",
        body="## Summary\n\nstub\n",
        changed_files=[{"file_path": f"docs/generated/{task_id}.md"}],
        test_results={"status": "passed", "py_compile": "pass"},
        risk_assessment={"risk_level": "low"},
        rollback_plan="Revert manually.",
        github_dry_run_result={"dry_run": True, "production_executed": False},
        status="ready",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


class _StubStore:
    def __init__(self, ws=None, artifacts=None, pr_draft=None):
        self._ws = ws
        self._artifacts = artifacts or []
        self._pr_draft = pr_draft

    async def get_workspace(self, task_id):
        if self._ws and self._ws.task_id == task_id:
            return self._ws
        return None

    async def list_workspaces(self, **kwargs):
        return [self._ws] if self._ws else []

    async def list_code_change_artifacts(self, task_id):
        return [a for a in self._artifacts if a.task_id == task_id]

    async def get_pr_draft_artifact(self, task_id):
        if self._pr_draft and self._pr_draft.task_id == task_id:
            return self._pr_draft
        return None


def _wire_router(monkeypatch, operations_module, store):
    monkeypatch.setattr(operations_module, "CodeWorkspaceStore", lambda *a, **kw: store)
    app = FastAPI()
    app.include_router(operations_module.router)
    return TestClient(app)


def test_list_code_workspaces(monkeypatch, operations_module):
    store = _StubStore(ws=_ws_model("ws-list-1"))
    client = _wire_router(monkeypatch, operations_module, store)
    resp = client.get("/operations/code/workspaces")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["workspaces"][0]["task_id"] == "ws-list-1"


def test_code_workspace_view_returns_full_bundle(monkeypatch, operations_module):
    store = _StubStore(
        ws=_ws_model("ws-view-1"),
        artifacts=[_artifact_model("ws-view-1")],
        pr_draft=_pr_draft_model("ws-view-1"),
    )
    client = _wire_router(monkeypatch, operations_module, store)
    resp = client.get("/operations/code/workspaces/ws-view-1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["workspace"]["task_id"] == "ws-view-1"
    assert body["code_change_artifacts"]
    assert body["pr_draft"]["status"] == "ready"


def test_code_workspace_view_returns_404_when_missing(monkeypatch, operations_module):
    store = _StubStore()
    client = _wire_router(monkeypatch, operations_module, store)
    resp = client.get("/operations/code/workspaces/missing")
    assert resp.status_code == 404


def test_code_artifacts_view_lists_artifacts(monkeypatch, operations_module):
    store = _StubStore(artifacts=[_artifact_model("ws-art-1")])
    client = _wire_router(monkeypatch, operations_module, store)
    resp = client.get("/operations/code/artifacts/ws-art-1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["code_change_artifacts"][0]["task_id"] == "ws-art-1"


def test_pr_draft_view_returns_payload(monkeypatch, operations_module):
    store = _StubStore(pr_draft=_pr_draft_model("ws-pr-1"))
    client = _wire_router(monkeypatch, operations_module, store)
    resp = client.get("/operations/code/pr-drafts/ws-pr-1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["pr_draft"]["status"] == "ready"
    assert body["pr_draft"]["risk_assessment"]["risk_level"] == "low"


def test_pr_draft_view_returns_404_when_missing(monkeypatch, operations_module):
    store = _StubStore()
    client = _wire_router(monkeypatch, operations_module, store)
    resp = client.get("/operations/code/pr-drafts/missing")
    assert resp.status_code == 404
