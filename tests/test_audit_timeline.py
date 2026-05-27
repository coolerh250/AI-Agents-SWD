"""Tests for the audit_timeline that orchestrator surfaces on
/workflow/timeline/{task_id}.

We exercise the pure builder (build_audit_timeline) without needing a DB,
plus a single end-to-end shape assertion through the FastAPI endpoint when
Postgres is available.
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path
from types import ModuleType

import pytest

_ORCH_SRC = Path(__file__).resolve().parents[1] / "apps" / "orchestrator" / "src"


def _load_progress() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "orchestrator_progress",
        _ORCH_SRC / "progress.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_audit_timeline_orders_by_created_at():
    progress = _load_progress()
    events = [
        {
            "decision_type": "qa",
            "agent": "qa-agent",
            "created_at": "2026-05-25T01:00:02+00:00",
            "summary": "qa ok",
            "result": "ok",
            "artifact_refs": {},
        },
        {
            "decision_type": "intake",
            "agent": "intake-agent",
            "created_at": "2026-05-25T01:00:00+00:00",
            "summary": "intake ok",
            "result": "ok",
            "artifact_refs": {"x": 1},
        },
        {
            "decision_type": "github_pr_integration",
            "agent": "devops-agent",
            "created_at": "2026-05-25T01:00:03+00:00",
            "summary": "github_pr_integration",
            "result": "success",
            "artifact_refs": {"pr_url": "https://github.com/x/y/pull/1"},
        },
    ]
    timeline = progress.build_audit_timeline(events)
    assert [e["decision_type"] for e in timeline] == [
        "intake",
        "qa",
        "github_pr_integration",
    ]
    # Each entry carries the expected fields.
    for entry in timeline:
        assert "agent" in entry
        assert "created_at" in entry
        assert "summary" in entry
        assert "result" in entry
        assert isinstance(entry["artifact_refs"], dict)


def test_build_audit_timeline_handles_missing_created_at():
    progress = _load_progress()
    timeline = progress.build_audit_timeline(
        [
            {"decision_type": "x"},
            {"decision_type": "y", "created_at": "2026-05-25T01:00:00+00:00"},
        ]
    )
    assert len(timeline) == 2


def test_build_audit_timeline_skips_non_dict_entries():
    progress = _load_progress()
    timeline = progress.build_audit_timeline(["not-a-dict", None, {}])  # type: ignore[arg-type]
    assert len(timeline) == 1


# End-to-end shape — only when Postgres is up. We skip on connection error.
async def test_workflow_timeline_includes_audit_timeline_field():
    # We import lazily to avoid pulling FastAPI deps at module load when
    # Postgres isn't required for the other tests in this file.
    sys.path.insert(0, str(_ORCH_SRC))
    try:
        from fastapi import HTTPException
        from main import workflow_timeline  # type: ignore
        from shared.sdk.workflow_store.store import WorkflowStore
    finally:
        sys.path.remove(str(_ORCH_SRC))

    store = WorkflowStore()
    try:
        existing = await store.list_workflows(None)
    except Exception:
        pytest.skip("Postgres unavailable in this run")
    if not existing:
        # Insert a tiny row so the endpoint has something to return.
        task_id = f"audit-tl-{uuid.uuid4().hex[:8]}"
        await store.upsert_workflow_state(
            task_id=task_id,
            workflow_id="wf-audit-tl",
            state={
                "task_id": task_id,
                "workflow_id": "wf-audit-tl",
                "stage": "dispatched",
                "audit_refs": [],
            },
            approval_required=False,
            approval_status="not_required",
            risk_level="low",
            execution_result={},
        )
    else:
        task_id = existing[0]["task_id"]
    try:
        result = await workflow_timeline(task_id)
    except HTTPException as exc:
        if exc.status_code == 404:
            pytest.skip("no workflow row to inspect")
        raise
    assert "audit_timeline" in result
    assert isinstance(result["audit_timeline"], list)
