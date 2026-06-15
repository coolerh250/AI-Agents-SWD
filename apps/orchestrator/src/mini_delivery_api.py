"""Stage 48 -- Mini Project Delivery Pilot operations API.

Read-only pilot views plus a single controlled write endpoint
(``POST /operations/mini-delivery-pilots/run``). The run endpoint chains the
controlled project-plan -> design-review -> workspace-execution stages and
builds acceptance / QA / safety evidence + a mini delivery report. It NEVER
calls an LLM, writes GitHub, opens a PR, merges, deploys, or delivers
externally. Responses carry summaries / evidence refs only -- never file
content, secrets, or chain-of-thought.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from shared.sdk.agent_discussion import AgentDiscussionStore
from shared.sdk.design_review import DesignReviewStore
from shared.sdk.mini_delivery_pilot import (
    MiniDeliveryPilotRequest,
    MiniDeliveryPilotStore,
    run_mini_delivery_pilot,
)
from shared.sdk.project_planning import ProjectPlanningStore
from shared.sdk.workspace_operator import WorkspaceOperatorStore

router = APIRouter(prefix="/operations", tags=["mini-delivery-pilot"])


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_store() -> ProjectPlanningStore:
    return ProjectPlanningStore()


def _discussion_store() -> AgentDiscussionStore:
    return AgentDiscussionStore()


def _review_store() -> DesignReviewStore:
    return DesignReviewStore()


def _workspace_store() -> WorkspaceOperatorStore:
    return WorkspaceOperatorStore()


def _pilot_store() -> MiniDeliveryPilotStore:
    return MiniDeliveryPilotStore()


async def _require_pilot(pilot_id: str) -> dict:
    try:
        pilot = await _pilot_store().get_pilot(pilot_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"pilot store unavailable: {exc}") from exc
    if pilot is None:
        raise HTTPException(status_code=404, detail="pilot not found")
    return pilot


# ---------------------------------------------------------------------------
# Run (write -- controlled-only).
# ---------------------------------------------------------------------------
@router.post("/mini-delivery-pilots/run")
async def run_pilot(payload: dict | None = None) -> dict:
    body = payload or {}
    request = MiniDeliveryPilotRequest(
        request_text=str(
            body.get("request_text")
            or "Create a FastAPI Todo Service with CRUD, SQLite, pytest, README, and API examples."
        ),
        project_id=(str(body.get("project_id") or "") or None),
        pilot_type=str(body.get("pilot_type") or "fastapi_todo_service"),
        controlled_only=True,
        requested_by_agent="operations-api",
    )
    try:
        result = await run_mini_delivery_pilot(
            request=request,
            project_store=_project_store(),
            discussion_store=_discussion_store(),
            review_store=_review_store(),
            workspace_store=_workspace_store(),
            pilot_store=_pilot_store(),
            emit_events=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"mini delivery pilot failed: {exc}") from exc
    out = result.model_dump()
    out["generated_at"] = _utcnow_iso()
    return out


# ---------------------------------------------------------------------------
# Reads.
# ---------------------------------------------------------------------------
@router.get("/mini-delivery-pilots")
async def list_pilots(project_id: str | None = None) -> dict:
    rows = await _pilot_store().list_pilots(project_id=project_id)
    return {"count": len(rows), "pilots": rows}


@router.get("/mini-delivery-pilots/{pilot_id}")
async def get_pilot(pilot_id: str) -> dict:
    return await _require_pilot(pilot_id)


@router.get("/mini-delivery-pilots/{pilot_id}/steps")
async def get_pilot_steps(pilot_id: str) -> dict:
    await _require_pilot(pilot_id)
    rows = await _pilot_store().list_steps(pilot_id)
    return {"count": len(rows), "steps": rows}


@router.get("/mini-delivery-pilots/{pilot_id}/acceptance-evaluations")
async def get_pilot_acceptance(pilot_id: str) -> dict:
    await _require_pilot(pilot_id)
    store = _pilot_store()
    rows = await store.list_acceptance_evaluations(pilot_id)
    summary = await store.get_acceptance_summary(pilot_id)
    return {"count": len(rows), "summary": summary, "acceptance_evaluations": rows}


@router.get("/mini-delivery-pilots/{pilot_id}/qa-report")
async def get_pilot_qa(pilot_id: str) -> dict:
    await _require_pilot(pilot_id)
    qa = await _pilot_store().get_qa_report(pilot_id)
    if qa is None:
        raise HTTPException(status_code=404, detail="qa report not found")
    return qa


@router.get("/mini-delivery-pilots/{pilot_id}/safety-report")
async def get_pilot_safety(pilot_id: str) -> dict:
    await _require_pilot(pilot_id)
    safety = await _pilot_store().get_safety_report(pilot_id)
    if safety is None:
        raise HTTPException(status_code=404, detail="safety report not found")
    return safety


@router.get("/mini-delivery-pilots/{pilot_id}/report")
async def get_pilot_delivery_report(pilot_id: str) -> dict:
    await _require_pilot(pilot_id)
    report = await _pilot_store().get_pilot_report(pilot_id)
    if report is None:
        raise HTTPException(status_code=404, detail="delivery report not found")
    return report


@router.get("/mini-delivery-pilots/{pilot_id}/artifacts")
async def get_pilot_artifacts(pilot_id: str) -> dict:
    await _require_pilot(pilot_id)
    rows = await _pilot_store().list_artifacts(pilot_id)
    return {"count": len(rows), "artifacts": rows}


@router.get("/mini-delivery-pilots/{pilot_id}/timeline")
async def get_pilot_timeline(pilot_id: str) -> dict:
    await _require_pilot(pilot_id)
    return await _pilot_store().get_pilot_timeline(pilot_id)


@router.get("/projects/{project_id}/mini-delivery-pilots")
async def list_project_pilots(project_id: str) -> dict:
    rows = await _pilot_store().list_pilots(project_id=project_id)
    return {"count": len(rows), "pilots": rows}


@router.get("/projects/{project_id}/latest-mini-delivery-pilot")
async def latest_project_pilot(project_id: str) -> dict:
    pilot = await _pilot_store().get_latest_pilot(project_id)
    if pilot is None:
        raise HTTPException(status_code=404, detail="no pilot for project")
    return pilot


__all__ = ["router"]
