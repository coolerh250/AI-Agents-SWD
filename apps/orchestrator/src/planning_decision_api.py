"""Step AT-M3.4 -- the formal planning decision surface.

ONE write route taking TWO identifiers, and both halves of that are the design rather than
omissions.

One route, because authoring a candidate plan, recording a TeamDecision and accepting a
PlanRevision exposed separately would make every invalid partial state reachable from outside: a
decision naming a revision nobody accepted, an accepted revision no decision ever chose, two
decisions for one discussion. The stores stay composable internally; the public boundary is where
the invariant is kept.

Two identifiers, because AT-M3.4 Validation 1 showed what the third one cost. The command used to
accept a ``plan`` and a ``decided_by``, and a caller could therefore hand it any structurally valid
plan and any principal id -- so an arbitrary payload became "the plan the team selected", with
commit ordering deciding between two racing callers, attributed to whoever the request named. Both
fields are gone. The plan is authored by the routed planner principal and read back from that
principal's own durable message; the author is that same principal. Substitution is not blocked by
a check here, it is unrepresentable.

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
    PlannerUnavailableError,
    PlanningDecisionConflictError,
    PlanningDecisionStateError,
)
from shared.sdk.agent_planning_decision.service import PlanningDecisionService

router = APIRouter(prefix="/planning-decisions", tags=["planning-decisions"])


def _service() -> PlanningDecisionService:
    return PlanningDecisionService()


class FinalizeDecisionRequest(BaseModel):
    """Formalize one converged discussion. Two identifiers, and deliberately nothing else.

    ``extra="forbid"`` is load-bearing rather than tidy: a request that still carries a ``plan`` or
    a ``decided_by`` -- from an older client, or from someone trying -- is refused with a 422 that
    names the field, instead of being silently ignored and leaving the sender believing it chose
    the plan.
    """

    model_config = ConfigDict(extra="forbid")

    goal_id: str = Field(min_length=1)
    discussion_id: str = Field(min_length=1)


def _decision_view(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "planning_decision_id": str(row["planning_decision_id"]),
        "project_id": str(row["project_id"]),
        "goal_id": str(row["goal_id"]),
        "discussion_id": str(row["discussion_id"]),
        "result_message_id": str(row["result_message_id"]),
        "candidate_plan_message_id": str(row["candidate_plan_message_id"]),
        "predecessor_plan_revision_id": (
            str(row["predecessor_plan_revision_id"])
            if row.get("predecessor_plan_revision_id")
            else None
        ),
        "team_decision_id": str(row["team_decision_id"]),
        # None exactly when the outcome is no_change: the team decided, and the plan it decided on
        # is the one it already had.
        "resulting_plan_revision_id": (
            str(row["resulting_plan_revision_id"])
            if row.get("resulting_plan_revision_id")
            else None
        ),
        "outcome": row["outcome"],
        "created_at": row.get("created_at"),
    }


def _team_decision_view(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "decision_id": str(row["decision_id"]),
        "thread_id": str(row["thread_id"]),
        # The principal that authored the plan, resolved from the team. Never a request field.
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
        "created_by": str(row["created_by"]) if row.get("created_by") else None,
        "plan": row["plan"],
        "diff": row["diff"],
        "trace_ref": row.get("trace_ref"),
        "created_at": row.get("created_at"),
    }


def _result_view(outcome: dict[str, Any]) -> dict[str, Any]:
    return {
        "created": outcome["created"],
        "detail": outcome["detail"],
        "outcome": outcome["outcome"],
        "candidate_plan_message_id": outcome["candidate_plan_message_id"],
        "planning_decision": _decision_view(outcome["planning_decision"]),
        "team_decision": _team_decision_view(outcome.get("team_decision")),
        "plan_revision": _revision_view(outcome.get("plan_revision")),
    }


@router.post("")
async def finalize_planning_decision(payload: FinalizeDecisionRequest) -> dict:
    """Turn one converged discussion into one TeamDecision and the plan the team decided on.

    The team's planner authors a structured candidate plan from the Goal and the convergence
    result; the decision then either accepts it as a new revision, accepts the revision the Goal
    already had, or records that nothing changed. Which of those happens is derived here, never
    requested.

    Safe to retry and safe to call concurrently. A repeat returns the canonical decision with
    ``created=false`` rather than making a second one — that is an outcome, not an error.

    409 means the discussion is not consumable, or something else reached the plan first: it did
    not converge, produced no result, is about another Goal, is bound to a revision that is no
    longer current, or the revision it wanted to accept was accepted by another decision. A stale
    discussion is never silently rebound; it stays evidence about the revision it discussed.
    """
    service = _service()
    try:
        outcome = await service.finalize(
            goal_id=payload.goal_id, discussion_id=payload.discussion_id
        )
    except DiscussionNotAdmissibleError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except StalePlanRevisionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PlanningDecisionConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (PlanLineageError, PlanRevisionLifecycleError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PlanRevisionAllocationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PlannerUnavailableError as exc:
        # The team has nobody who can plan. Not the caller's request to fix, and not a server
        # fault: the project's roster is the thing that is wrong.
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
    """What was proposed, what was challenged, and the exact plan the decision selected.

    There is no proposal table and no challenge table to expose: the approved architecture defines
    propose/challenge as message types, so this reads them from the discussion's own messages and
    labels each with the AT-M3.3 turn intent that produced it. The candidate plan is read by the id
    the decision names and verified to belong to that same discussion, thread and Goal, so an
    unrelated proposal can never appear in its place. No prompt, completion or reasoning trace is
    exposed — only the structured artifact and the invocation id that produced it.
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
