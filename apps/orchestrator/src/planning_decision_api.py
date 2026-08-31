"""Step AT-M3.4 -- the formal planning decision surface.

ONE write route, and that is the design rather than an omission. Creating a proposal, recording a
TeamDecision and accepting a PlanRevision are exposed as a single command because exposing them
separately would make every invalid partial state reachable from outside: a decision naming a
revision nobody accepted, an accepted revision no decision ever chose, two decisions for one
discussion. The stores stay composable internally; the public boundary is where the invariant is
kept.

What is NOT here, and is not an oversight: no route accepts a PlanRevision directly, no route
creates a TeamDecision on its own, no route edits a decision or a plan once recorded, and there is
no PUT, PATCH or DELETE at all. A recorded decision is what the team chose; an endpoint that could
rewrite it would make the record unciteable.

Also not here: anything that decomposes a plan into work items, routes them, dispatches an agent,
runs a tool or touches an approval. Those are AT-M3.5, AT-M4 and the Approval Engine respectively.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from shared.sdk.agent_planning.models import (
    PlanLineageError,
    PlanRevisionAllocationError,
    PlanRevisionLifecycleError,
    StalePlanRevisionError,
)
from shared.sdk.agent_planning_decision.models import (
    DiscussionNotAdmissibleError,
    PlanningDecisionStateError,
)
from shared.sdk.agent_planning_decision.service import PlanningDecisionService

router = APIRouter(prefix="/planning-decisions", tags=["planning-decisions"])


def _service() -> PlanningDecisionService:
    return PlanningDecisionService()


class PlanStepRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_key: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    required_capabilities: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    intended_owner_role: str | None = Field(default=None, max_length=100)


class PlanRequest(BaseModel):
    """The structured plan the decision accepts. Prose is not a plan.

    Mirrors AT-M3.2's ``PlanContent`` so a caller gets a 422 with a field path rather than an
    opaque store error, and so the accepted revision is diffable against its predecessor by
    construction. M3.4 does not author this content -- no AT-M3.1 reasoning verb produces a plan,
    and adding one would be an extension of that contract with its own authorization.
    """

    model_config = ConfigDict(extra="forbid")

    objective: str = Field(min_length=1, max_length=2000)
    steps: list[PlanStepRequest] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)


class FinalizeDecisionRequest(BaseModel):
    """Formalize one converged discussion into one decision and one accepted plan."""

    model_config = ConfigDict(extra="forbid")

    goal_id: str = Field(min_length=1)
    discussion_id: str = Field(min_length=1)
    #: The principal recording the decision on the team's behalf. Not an approver: this names who
    #: wrote the decision down, and grants nothing.
    decided_by: str = Field(min_length=1)
    plan: PlanRequest


def _decision_view(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "planning_decision_id": str(row["planning_decision_id"]),
        "project_id": str(row["project_id"]),
        "goal_id": str(row["goal_id"]),
        "discussion_id": str(row["discussion_id"]),
        "result_message_id": str(row["result_message_id"]),
        "predecessor_plan_revision_id": (
            str(row["predecessor_plan_revision_id"])
            if row.get("predecessor_plan_revision_id")
            else None
        ),
        "team_decision_id": str(row["team_decision_id"]),
        "resulting_plan_revision_id": str(row["resulting_plan_revision_id"]),
        "outcome": row["outcome"],
        "created_at": row.get("created_at"),
    }


def _team_decision_view(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "decision_id": str(row["decision_id"]),
        "thread_id": str(row["thread_id"]),
        "proposed_by": str(row["proposed_by"]),
        "options_considered": list(row["options_considered"] or []),
        "selected_option": row["selected_option"],
        "rationale_summary": row["rationale_summary"],
        # Unresolved objections are reported, never suppressed.
        "dissent_summary": row.get("dissent_summary"),
        "resulting_plan_revision_id": (
            str(row["resulting_plan_revision_id"])
            if row.get("resulting_plan_revision_id")
            else None
        ),
        "created_at": row.get("created_at"),
    }


def _revision_view(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "plan_revision_id": str(row["plan_revision_id"]),
        "goal_id": str(row["goal_id"]),
        "revision_number": row["revision_number"],
        "reason": row["reason"],
        "status": row["status"],
        "supersedes_revision_id": (
            str(row["supersedes_revision_id"]) if row.get("supersedes_revision_id") else None
        ),
        "plan": row["plan"],
        "diff": row["diff"],
        "trace_ref": row.get("trace_ref"),
        "created_at": row.get("created_at"),
    }


def _result_view(outcome: dict[str, Any]) -> dict[str, Any]:
    return {
        "created": outcome["created"],
        "detail": outcome["detail"],
        "planning_decision": _decision_view(outcome["planning_decision"]),
        "team_decision": _team_decision_view(outcome.get("team_decision")),
        "plan_revision": _revision_view(outcome.get("plan_revision")),
    }


@router.post("")
async def finalize_planning_decision(payload: FinalizeDecisionRequest) -> dict:
    """Turn one converged discussion into one TeamDecision and one accepted PlanRevision.

    Safe to retry and safe to call concurrently. A repeat returns the canonical decision with
    ``created=false`` rather than making a second one — that is an outcome, not an error.

    409 means the discussion is not consumable: it did not converge, produced no result, is about
    another Goal, or is bound to a revision that is no longer current. A stale discussion is never
    silently rebound to the current revision; it stays evidence about the revision it discussed.
    """
    service = _service()
    try:
        outcome = await service.finalize(
            goal_id=payload.goal_id,
            discussion_id=payload.discussion_id,
            decided_by=payload.decided_by,
            plan=payload.plan.model_dump(),
        )
    except DiscussionNotAdmissibleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except StalePlanRevisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (PlanLineageError, PlanRevisionLifecycleError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PlanRevisionAllocationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PlanningDecisionStateError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except asyncpg.PostgresError as exc:
        # An expected domain conflict is mapped above; anything left from the driver is an upstream
        # availability problem, not a bug the caller can act on and not a 500.
        raise HTTPException(
            status_code=503, detail=f"decision could not be recorded: {type(exc).__name__}"
        ) from exc
    return _result_view(outcome)


@router.get("/{planning_decision_id}")
async def get_planning_decision(planning_decision_id: str) -> dict:
    outcome = await _service().get(planning_decision_id)
    if outcome is None:
        raise HTTPException(
            status_code=404, detail=f"unknown planning decision {planning_decision_id}"
        )
    return {
        "planning_decision": _decision_view(outcome["planning_decision"]),
        "team_decision": _team_decision_view(outcome.get("team_decision")),
        "plan_revision": _revision_view(outcome.get("plan_revision")),
    }


@router.get("/{planning_decision_id}/evidence")
async def get_planning_decision_evidence(planning_decision_id: str) -> dict:
    """What was proposed and what was challenged, read from the thread that actually holds it.

    There is no proposal table and no challenge table to expose: the approved architecture defines
    propose/challenge as message types, so this reads them from the discussion's own messages and
    labels each with the AT-M3.3 turn intent that produced it.
    """
    evidence = await _service().get_evidence(planning_decision_id)
    if evidence is None:
        raise HTTPException(
            status_code=404, detail=f"unknown planning decision {planning_decision_id}"
        )
    return evidence


@router.get("/by-discussion/{discussion_id}")
async def get_planning_decision_for_discussion(discussion_id: str) -> dict:
    """Has this discussion already been formalized, and into what?"""
    outcome = await _service().get_by_discussion(discussion_id)
    if outcome is None:
        raise HTTPException(
            status_code=404, detail=f"discussion {discussion_id} has no planning decision"
        )
    return {
        "planning_decision": _decision_view(outcome["planning_decision"]),
        "team_decision": _team_decision_view(outcome.get("team_decision")),
        "plan_revision": _revision_view(outcome.get("plan_revision")),
    }
