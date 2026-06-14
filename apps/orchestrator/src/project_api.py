"""Stage 45 -- Project Planner & Task Graph operations API.

Read-only project views plus a single planning-only write endpoint
(``POST /operations/projects/plan``). The plan endpoint runs the
deterministic template planner -- it never calls an LLM, never writes
GitHub, never deploys. Responses carry project briefs / task graphs /
summaries only -- never secrets, never chain-of-thought.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from shared.sdk.observability.metrics import PROJECT_DELIVERY_READINESS_CHECKS_TOTAL
from shared.sdk.project_planning import (
    PlannerInput,
    ProjectPlanningStore,
    evaluate_delivery_readiness,
    plan_project,
)

router = APIRouter(prefix="/operations", tags=["projects"])


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store() -> ProjectPlanningStore:
    return ProjectPlanningStore()


class PlanRequest(BaseModel):
    request_text: str = Field(default="")
    request: str | None = None
    task_id: str | None = None
    requirement_summary: str | None = None
    source: str = "operator"
    requester: str | None = None
    project_type: str | None = None
    autonomy_level: str = "autonomous_dev_test"


# ---------------------------------------------------------------------------
# POST /operations/projects/plan -- planning-only.
# ---------------------------------------------------------------------------
@router.post("/projects/plan")
async def plan_project_endpoint(payload: PlanRequest) -> dict:
    request_text = (payload.request_text or payload.request or "").strip()
    if not request_text:
        raise HTTPException(status_code=400, detail="request_text is required")
    planner_input = PlannerInput(
        task_id=payload.task_id,
        request_text=request_text,
        requirement_summary=payload.requirement_summary,
        source=payload.source,
        requester=payload.requester,
        project_type=payload.project_type,
        autonomy_level=payload.autonomy_level,
        dispatch_policy="planning_only",
    )
    try:
        output = await plan_project(planner_input, _store(), emit_events=True, planning_only=True)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"project planning failed: {exc}") from exc
    result = output.model_dump()
    result["generated_at"] = _utcnow_iso()
    return result


# ---------------------------------------------------------------------------
# GET project views.
# ---------------------------------------------------------------------------
@router.get("/projects")
async def list_projects(status: str | None = None, limit: int = 100) -> dict:
    try:
        projects = await _store().list_projects(status=status, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"project store unavailable: {exc}") from exc
    return {"count": len(projects), "projects": projects, "generated_at": _utcnow_iso()}


async def _require_project(project_id: str) -> dict:
    try:
        project = await _store().get_project(project_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"project store unavailable: {exc}") from exc
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


@router.get("/projects/{project_id}")
async def get_project(project_id: str) -> dict:
    return await _require_project(project_id)


@router.get("/projects/{project_id}/brief")
async def get_project_brief(project_id: str) -> dict:
    await _require_project(project_id)
    brief = await _store().get_brief(project_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="brief not found")
    return brief


@router.get("/projects/{project_id}/stories")
async def get_project_stories(project_id: str) -> dict:
    await _require_project(project_id)
    stories = await _store().list_user_stories(project_id)
    return {"count": len(stories), "stories": stories}


@router.get("/projects/{project_id}/acceptance-criteria")
async def get_project_acceptance(project_id: str) -> dict:
    await _require_project(project_id)
    criteria = await _store().list_acceptance_criteria(project_id)
    return {"count": len(criteria), "acceptance_criteria": criteria}


@router.get("/projects/{project_id}/milestones")
async def get_project_milestones(project_id: str) -> dict:
    await _require_project(project_id)
    milestones = await _store().list_milestones(project_id)
    return {"count": len(milestones), "milestones": milestones}


@router.get("/projects/{project_id}/work-items")
async def get_project_work_items(project_id: str, status: str | None = None) -> dict:
    await _require_project(project_id)
    items = await _store().list_work_items(project_id, status=status)
    return {"count": len(items), "work_items": items}


@router.get("/projects/{project_id}/dependencies")
async def get_project_dependencies(project_id: str) -> dict:
    await _require_project(project_id)
    deps = await _store().list_dependencies(project_id)
    return {"count": len(deps), "dependencies": deps}


@router.get("/projects/{project_id}/risks")
async def get_project_risks(project_id: str) -> dict:
    await _require_project(project_id)
    risks = await _store().list_risks(project_id)
    return {"count": len(risks), "risks": risks}


@router.get("/projects/{project_id}/graph")
async def get_project_graph(project_id: str) -> dict:
    await _require_project(project_id)
    snapshot = await _store().get_latest_graph_snapshot(project_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="graph snapshot not found")
    return snapshot


@router.get("/projects/{project_id}/progress")
async def get_project_progress(project_id: str) -> dict:
    await _require_project(project_id)
    progress = await _store().compute_project_progress(project_id)
    progress["project_id"] = project_id
    return progress


@router.get("/projects/{project_id}/delivery-readiness")
async def get_project_delivery_readiness(project_id: str) -> dict:
    await _require_project(project_id)
    store = _store()
    criteria = await store.list_acceptance_criteria(project_id)
    work_items = await store.list_work_items(project_id)
    artifacts = await store.list_artifacts(project_id)
    readiness = evaluate_delivery_readiness(
        acceptance_criteria=criteria,
        work_items=work_items,
        artifacts=artifacts,
    )
    PROJECT_DELIVERY_READINESS_CHECKS_TOTAL.labels(
        status="ready" if readiness.ready else "not_ready"
    ).inc()
    result = readiness.to_dict()
    result["project_id"] = project_id
    return result


# ---------------------------------------------------------------------------
# Work-item views.
# ---------------------------------------------------------------------------
@router.get("/project-work-items")
async def list_project_work_items(project_id: str | None = None, status: str | None = None) -> dict:
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id query param is required")
    items = await _store().list_work_items(project_id, status=status)
    return {"count": len(items), "work_items": items}


async def _require_work_item(work_item_id: str) -> dict:
    try:
        item = await _store().get_work_item(work_item_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"project store unavailable: {exc}") from exc
    if item is None:
        raise HTTPException(status_code=404, detail="work item not found")
    return item


@router.get("/project-work-items/{work_item_id}")
async def get_project_work_item(work_item_id: str) -> dict:
    return await _require_work_item(work_item_id)


class WorkItemStatusUpdate(BaseModel):
    status: str


@router.post("/project-work-items/{work_item_id}/status")
async def update_work_item_status(work_item_id: str, payload: WorkItemStatusUpdate) -> dict:
    await _require_work_item(work_item_id)
    updated = await _store().update_work_item_status(work_item_id, payload.status)
    if updated is None:
        raise HTTPException(status_code=404, detail="work item not found")
    return updated


@router.get("/project-work-items/{work_item_id}/dependencies")
async def get_work_item_dependencies(work_item_id: str) -> dict:
    await _require_work_item(work_item_id)
    deps = await _store().list_work_item_dependencies(work_item_id)
    return {"count": len(deps), "dependencies": deps}


@router.get("/project-work-items/{work_item_id}/acceptance-criteria")
async def get_work_item_acceptance(work_item_id: str) -> dict:
    item = await _require_work_item(work_item_id)
    criteria = await _store().list_acceptance_criteria(
        item["project_id"], work_item_id=work_item_id
    )
    return {"count": len(criteria), "acceptance_criteria": criteria}


__all__ = ["router"]
