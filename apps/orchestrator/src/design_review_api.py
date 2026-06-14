"""Stage 46 -- Agent Discussion & Design Review operations API.

Read-only discussion/review views plus a single review-only write endpoint
(``POST /operations/projects/{id}/design-review``). The review endpoint runs
the deterministic multi-role review -- it never calls an LLM, never writes
GitHub, never deploys, never dispatches work items. Responses carry findings /
gates / decisions / summaries only -- never secrets, never chain-of-thought.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from shared.sdk.agent_discussion import AgentDiscussionStore
from shared.sdk.design_review import (
    DesignReviewStore,
    compute_acceptance_coverage,
    run_design_review,
)
from shared.sdk.design_review.models import ReviewContext
from shared.sdk.project_planning import ProjectPlanningStore

router = APIRouter(prefix="/operations", tags=["design-review"])


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_store() -> ProjectPlanningStore:
    return ProjectPlanningStore()


def _discussion_store() -> AgentDiscussionStore:
    return AgentDiscussionStore()


def _review_store() -> DesignReviewStore:
    return DesignReviewStore()


async def _require_project(project_id: str) -> dict:
    try:
        project = await _project_store().get_project(project_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"project store unavailable: {exc}") from exc
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    return project


# ---------------------------------------------------------------------------
# Design review (write -- review-only).
# ---------------------------------------------------------------------------
@router.post("/projects/{project_id}/design-review")
async def run_project_design_review(project_id: str, payload: dict | None = None) -> dict:
    await _require_project(project_id)
    review_type = str((payload or {}).get("review_type") or "full_pre_execution")
    import os

    planning_only = str(
        os.environ.get("DESIGN_REVIEW_PLANNING_ONLY", "true")
    ).strip().lower() not in (
        "false",
        "0",
        "no",
    )
    dispatch = str(
        os.environ.get("ENABLE_DESIGN_REVIEW_WORK_ITEM_DISPATCH", "false")
    ).strip().lower() in ("true", "1", "yes")
    try:
        output = await run_design_review(
            project_id=project_id,
            project_store=_project_store(),
            discussion_store=_discussion_store(),
            review_store=_review_store(),
            review_type=review_type,
            planning_only=planning_only,
            work_item_dispatch_enabled=dispatch,
            requested_by_agent="operations-api",
            emit_events=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"design review failed: {exc}") from exc
    result = output.model_dump()
    result["generated_at"] = _utcnow_iso()
    return result


# ---------------------------------------------------------------------------
# Discussion reads.
# ---------------------------------------------------------------------------
@router.get("/projects/{project_id}/discussions")
async def list_project_discussions(project_id: str) -> dict:
    await _require_project(project_id)
    rows = await _discussion_store().list_project_discussions(project_id)
    return {"count": len(rows), "discussions": rows}


async def _require_session(session_id: str) -> dict:
    try:
        session = await _discussion_store().get_session(session_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"discussion store unavailable: {exc}") from exc
    if session is None:
        raise HTTPException(status_code=404, detail="discussion session not found")
    return session


@router.get("/discussions/{session_id}")
async def get_discussion(session_id: str) -> dict:
    return await _require_session(session_id)


@router.get("/discussions/{session_id}/participants")
async def get_discussion_participants(session_id: str) -> dict:
    await _require_session(session_id)
    rows = await _discussion_store().list_participants(session_id)
    return {"count": len(rows), "participants": rows}


@router.get("/discussions/{session_id}/contributions")
async def get_discussion_contributions(session_id: str) -> dict:
    await _require_session(session_id)
    rows = await _discussion_store().list_contributions(session_id)
    return {"count": len(rows), "contributions": rows}


@router.get("/discussions/{session_id}/artifacts")
async def get_discussion_artifacts(session_id: str) -> dict:
    await _require_session(session_id)
    rows = await _discussion_store().list_artifacts(session_id)
    return {"count": len(rows), "artifacts": rows}


# ---------------------------------------------------------------------------
# Design review reads.
# ---------------------------------------------------------------------------
@router.get("/projects/{project_id}/design-reviews")
async def list_project_design_reviews(project_id: str) -> dict:
    await _require_project(project_id)
    rows = await _review_store().list_project_reviews(project_id)
    return {"count": len(rows), "design_reviews": rows}


async def _require_review(review_session_id: str) -> dict:
    try:
        review = await _review_store().get_review(review_session_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"review store unavailable: {exc}") from exc
    if review is None:
        raise HTTPException(status_code=404, detail="design review not found")
    return review


@router.get("/design-reviews/{review_session_id}")
async def get_design_review(review_session_id: str) -> dict:
    return await _require_review(review_session_id)


@router.get("/design-reviews/{review_session_id}/findings")
async def get_design_review_findings(review_session_id: str) -> dict:
    await _require_review(review_session_id)
    rows = await _review_store().list_findings(review_session_id)
    return {"count": len(rows), "findings": rows}


@router.get("/design-reviews/{review_session_id}/decisions")
async def get_design_review_decisions(review_session_id: str) -> dict:
    await _require_review(review_session_id)
    rows = await _review_store().list_decisions(review_session_id)
    return {"count": len(rows), "decisions": rows}


@router.get("/projects/{project_id}/review-gates")
async def get_project_review_gates(project_id: str) -> dict:
    await _require_project(project_id)
    rows = await _review_store().list_gates(project_id)
    return {"count": len(rows), "review_gates": rows}


@router.get("/projects/{project_id}/go-no-go-summary")
async def get_project_go_no_go(project_id: str) -> dict:
    await _require_project(project_id)
    return await _review_store().compute_review_summary(project_id)


@router.get("/projects/{project_id}/acceptance-coverage")
async def get_project_acceptance_coverage(project_id: str) -> dict:
    await _require_project(project_id)
    store = _project_store()
    criteria = await store.list_acceptance_criteria(project_id)
    ctx = ReviewContext(project_id=project_id, acceptance_criteria=criteria)
    cov = compute_acceptance_coverage(ctx)
    result = cov.to_dict()
    result["project_id"] = project_id
    return result


__all__ = ["router"]
