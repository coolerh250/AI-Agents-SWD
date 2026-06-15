"""Stage 47 -- Real Repo Workspace Operator operations API.

Read-only workspace views plus a single controlled write endpoint
(``POST /operations/projects/{id}/workspace/execute``). The execute endpoint
runs the controlled workspace operator -- it generates a deterministic FastAPI
Todo project in an allowlisted workspace, runs pytest + static checks, and
records diff / artifacts / work-item links. It NEVER calls an LLM, writes
GitHub, opens a PR, merges, deploys, or writes the repo root. Responses carry
metadata only -- never file content, secrets, or chain-of-thought.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from shared.sdk.design_review import DesignReviewStore
from shared.sdk.project_planning import ProjectPlanningStore
from shared.sdk.workspace_operator import (
    WorkspaceExecutionRequest,
    WorkspaceOperatorStore,
    run_workspace_execution,
)

router = APIRouter(prefix="/operations", tags=["workspace-operator"])


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_store() -> ProjectPlanningStore:
    return ProjectPlanningStore()


def _review_store() -> DesignReviewStore:
    return DesignReviewStore()


def _workspace_store() -> WorkspaceOperatorStore:
    return WorkspaceOperatorStore()


async def _require_project(project_id: str) -> dict:
    try:
        project = await _project_store().get_project(project_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"project store unavailable: {exc}") from exc
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


async def _require_workspace(workspace_id: str) -> dict:
    try:
        ws = await _workspace_store().get_workspace(workspace_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"workspace store unavailable: {exc}") from exc
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    return ws


# ---------------------------------------------------------------------------
# Controlled workspace execution (write -- controlled-only).
# ---------------------------------------------------------------------------
@router.post("/projects/{project_id}/workspace/execute")
async def execute_workspace(project_id: str, payload: dict | None = None) -> dict:
    await _require_project(project_id)
    body = payload or {}
    request = WorkspaceExecutionRequest(
        project_id=project_id,
        design_review_session_id=(str(body.get("design_review_session_id") or "") or None),
        graph_snapshot_id=(str(body.get("graph_snapshot_id") or "") or None),
        execution_type=str(body.get("execution_type") or "fastapi_todo_generation"),
        workspace_type=str(body.get("workspace_type") or "generated_project"),
        requested_by_agent="operations-api",
        controlled_only=True,
    )
    try:
        result = await run_workspace_execution(
            request=request,
            project_store=_project_store(),
            review_store=_review_store(),
            workspace_store=_workspace_store(),
            emit_events=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"workspace execution failed: {exc}") from exc
    out = result.model_dump()
    out["generated_at"] = _utcnow_iso()
    return out


# ---------------------------------------------------------------------------
# Workspace reads.
# ---------------------------------------------------------------------------
@router.get("/workspaces")
async def list_workspaces(project_id: str | None = None) -> dict:
    rows = await _workspace_store().list_workspaces(project_id=project_id)
    return {"count": len(rows), "workspaces": rows}


@router.get("/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str) -> dict:
    return await _require_workspace(workspace_id)


@router.get("/workspaces/{workspace_id}/files")
async def get_workspace_files(workspace_id: str) -> dict:
    await _require_workspace(workspace_id)
    rows = await _workspace_store().list_workspace_files(workspace_id)
    return {"count": len(rows), "files": rows}


@router.get("/workspaces/{workspace_id}/operations")
async def get_workspace_operations(workspace_id: str) -> dict:
    await _require_workspace(workspace_id)
    rows = await _workspace_store().list_operations(workspace_id)
    return {"count": len(rows), "operations": rows}


@router.get("/workspaces/{workspace_id}/test-runs")
async def get_workspace_test_runs(workspace_id: str) -> dict:
    await _require_workspace(workspace_id)
    rows = await _workspace_store().list_test_runs(workspace_id)
    return {"count": len(rows), "test_runs": rows}


@router.get("/workspaces/{workspace_id}/diff-summary")
async def get_workspace_diff_summary(workspace_id: str) -> dict:
    await _require_workspace(workspace_id)
    diff = await _workspace_store().get_diff_summary(workspace_id)
    if diff is None:
        raise HTTPException(status_code=404, detail="diff summary not found")
    return diff


@router.get("/workspaces/{workspace_id}/artifacts")
async def get_workspace_artifacts(workspace_id: str) -> dict:
    await _require_workspace(workspace_id)
    rows = await _workspace_store().list_artifacts(workspace_id)
    return {"count": len(rows), "artifacts": rows}


@router.get("/workspaces/{workspace_id}/report")
async def get_workspace_report(workspace_id: str) -> dict:
    await _require_workspace(workspace_id)
    return await _workspace_store().get_workspace_report(workspace_id)


@router.get("/projects/{project_id}/work-item-execution-links")
async def get_work_item_execution_links(project_id: str) -> dict:
    await _require_project(project_id)
    rows = await _workspace_store().list_work_item_links(project_id)
    return {"count": len(rows), "work_item_execution_links": rows}


@router.get("/projects/{project_id}/workspace-summary")
async def get_workspace_summary(project_id: str) -> dict:
    await _require_project(project_id)
    return await _workspace_store().compute_workspace_summary(project_id)


__all__ = ["router"]
