"""Step AT-M3.2 -- the minimal Goal / PlanRevision surface later AT-M3 slices need.

Deliberately append-only. There is no PUT, PATCH or DELETE for a revision, and no endpoint that
accepts a diff: a plan changes by POSTing a successor, and the diff is computed server-side from
the predecessor's stored plan. Exposing an update route would contradict the immutability the
schema enforces, and would be the obvious way for a later slice to break it by accident.

It runs no workflow, dispatches nothing, decomposes nothing, calls no provider and executes no
production action. This is not the Autonomous Team UX (AT-M5) and not the planner (AT-M3.4).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from shared.sdk.agent_planning.models import (
    PlanLineageError,
    PlanStepDraftError,
    StalePlanRevisionError,
)
from shared.sdk.agent_planning.service import PlanningService

router = APIRouter(prefix="/planning", tags=["planning"])


def _service() -> PlanningService:
    return PlanningService()


class CreateGoalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1)
    statement: str = Field(min_length=1, max_length=4000)
    created_by: str = Field(min_length=1)
    acceptance_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    status: str = Field(default="draft", pattern="^(draft|active|achieved|abandoned)$")


class CreateInitialRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created_by: str = Field(min_length=1)
    plan: dict[str, Any]
    status: str = Field(default="draft", pattern="^(draft|proposed|accepted|rejected)$")
    trace_ref: str | None = Field(default=None, max_length=500)


class CreateSuccessorRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Required, never inferred. A caller that cannot say which revision it planned against has
    #: no basis for a successor, and inferring "whatever is current now" would silently rebase it.
    expected_current_revision_id: str = Field(min_length=1)
    created_by: str = Field(min_length=1)
    plan: dict[str, Any]
    reason: str = Field(
        pattern=(
            "^(goal_changed|clarification_answered|team_decision|debug_plan_invalid"
            "|dependency_discovered|scope_correction|blocked_resolution)$"
        )
    )
    status: str = Field(default="draft", pattern="^(draft|proposed|accepted|rejected)$")
    rationale: str | None = Field(default=None, max_length=2000)
    trace_ref: str | None = Field(default=None, max_length=500)


def _goal_view(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "goal_id": str(row["goal_id"]),
        "project_id": str(row["project_id"]),
        "statement": row["statement"],
        "acceptance_criteria": list(row["acceptance_criteria"]),
        "constraints": list(row["constraints"]),
        "created_by": str(row["created_by"]),
        "status": row["status"],
        "created_at": row.get("created_at"),
    }


def _revision_view(row: dict[str, Any], *, is_current: bool | None = None) -> dict[str, Any]:
    view = {
        "plan_revision_id": str(row["plan_revision_id"]),
        "project_id": str(row["project_id"]),
        "goal_id": str(row["goal_id"]),
        "revision_number": row["revision_number"],
        "created_by": str(row["created_by"]),
        "reason": row["reason"],
        "supersedes_revision_id": (
            str(row["supersedes_revision_id"]) if row["supersedes_revision_id"] else None
        ),
        "status": row["status"],
        "plan": row["plan"],
        "diff": row["diff"],
        "trace_ref": row.get("trace_ref"),
        "created_at": row.get("created_at"),
    }
    if is_current is not None:
        view["is_current"] = is_current
    return view


@router.post("/goals")
async def create_goal(payload: CreateGoalRequest) -> dict:
    try:
        row = await _service().create_goal(
            project_id=payload.project_id,
            statement=payload.statement,
            created_by=payload.created_by,
            acceptance_criteria=tuple(payload.acceptance_criteria),
            constraints=tuple(payload.constraints),
            status=payload.status,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"goal could not be created: {exc}") from exc
    return _goal_view(row)


@router.get("/goals/{goal_id}")
async def get_goal(goal_id: str) -> dict:
    row = await _service().get_goal(goal_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"unknown goal {goal_id}")
    return _goal_view(row)


@router.post("/goals/{goal_id}/plan-revisions")
async def create_initial_revision(goal_id: str, payload: CreateInitialRevisionRequest) -> dict:
    """Revision 1. A goal may have exactly one root revision; a second is a 409, not a fork."""
    service = _service()
    try:
        row = await service.create_initial_revision(
            goal_id=goal_id,
            created_by=payload.created_by,
            plan=payload.plan,
            status=payload.status,
            trace_ref=payload.trace_ref,
        )
    except PlanStepDraftError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PlanLineageError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _revision_view(row, is_current=True)


@router.post("/goals/{goal_id}/plan-revisions/successor")
async def create_successor_revision(goal_id: str, payload: CreateSuccessorRevisionRequest) -> dict:
    """Append revision N+1. Fails closed with 409 when the caller's expected revision is stale."""
    service = _service()
    try:
        row = await service.create_successor_revision(
            goal_id=goal_id,
            expected_current_revision_id=payload.expected_current_revision_id,
            created_by=payload.created_by,
            plan=payload.plan,
            reason=payload.reason,
            status=payload.status,
            rationale=payload.rationale,
            trace_ref=payload.trace_ref,
        )
    except StalePlanRevisionError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "stale_plan_revision",
                "goal_id": exc.goal_id,
                "expected_current_revision_id": exc.expected_revision_id,
                "actual_current_revision_id": exc.actual_revision_id,
                "message": (
                    "the plan changed since this successor was derived; re-read the current "
                    "revision and decide again"
                ),
            },
        ) from exc
    except PlanStepDraftError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PlanLineageError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _revision_view(row, is_current=True)


@router.get("/goals/{goal_id}/plan-revisions/current")
async def get_current_revision(goal_id: str) -> dict:
    row = await _service().get_current_revision(goal_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"goal {goal_id} has no plan revision yet")
    return _revision_view(row, is_current=True)


@router.get("/goals/{goal_id}/plan-revisions")
async def list_revisions(goal_id: str, limit: int = 200) -> dict:
    """Full history, oldest first. A replan never removes an entry from it."""
    rows = await _service().list_revisions(goal_id, limit=limit)
    superseded = {
        str(row["supersedes_revision_id"]) for row in rows if row["supersedes_revision_id"]
    }
    return {
        "goal_id": goal_id,
        "count": len(rows),
        "revisions": [
            _revision_view(row, is_current=str(row["plan_revision_id"]) not in superseded)
            for row in rows
        ],
    }


@router.get("/plan-revisions/{plan_revision_id}/diff")
async def get_diff(plan_revision_id: str) -> dict:
    diff = await _service().get_diff(plan_revision_id)
    if diff is None:
        raise HTTPException(status_code=404, detail=f"unknown plan revision {plan_revision_id}")
    return diff
