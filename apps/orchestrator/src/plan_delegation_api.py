"""Step AT-M3.5 -- the plan-driven delegation surface.

Two write routes, each a whole command that leaves the graph in a valid state, and two read
routes.

What is deliberately NOT here, and is not an oversight: no route sets a unit ready, assigns a
principal, marks a unit dispatched, rebinds a unit to another PlanRevision, bypasses a dependency
or edits a recorded dispatch. Readiness is derived from dependency completion, ownership is decided
by the AT-M2 capability router from the live project team, and a dispatch is permanently bound to
the revision that authorized it. An endpoint that could override any of those would turn each
guarantee into a convention -- the same reason the AT-M3.4 surface exposes exactly one write route
and refuses a caller-supplied plan.

``materialize`` takes a goal id and a revision id and nothing else. The plan is read from the
revision row: a caller cannot supply steps, dependencies, capabilities or an owner, so an arbitrary
payload can never become "the work the team is doing". That refusal is the AT-M3.4 Validation 1
lesson applied one slice later.

``schedule`` is safe to retry and safe to call concurrently. It is the only way work is dispatched,
it takes no unit list, and it never dispatches anything a dependency still blocks.

**There is no completion route, and its absence is the point.** An earlier shape exposed
``POST .../result`` guarded by a ``correlation_id`` and a ``reported_by`` the caller supplied and
the server checked. Both values are returned by the read routes below. Checking a value the caller
can look up is not authentication, it is a lookup, so any client able to read the graph could
terminalize any dispatched step and unlock its dependents. Hiding the identifiers would not have
fixed it either -- that is secrecy standing in for authority, and it fails the first time a graph is
rendered in an operator console.

The real boundary needs an authenticated runtime-execution identity, and AT-M4 owns it: AT-M4 is not
authorized, so no such identity exists yet, so this slice must not expose a completion mutation at
all. Dependency-unlock mechanics are still exercised through
``PlanDelegationService.record_internal_result``, an internal scheduler seam that takes no principal
and no correlation id and derives every attributed identity from the canonical dispatch row. When
AT-M4 introduces authenticated agent ingress it will establish which unit is being answered and then
call that same operation.

Identifiers appearing on the read routes -- ``correlation_id``, ``assigned_principal_id``,
``routing_decision_id`` -- are **identifiers, not credentials and not authorization tokens**. They
exist so an operator can reconstruct a delegation, and nothing in this slice grants authority on the
strength of holding one.

Nothing here runs code, a shell, a test, a Git or GitHub operation, a deployment or an external
request, and nothing here creates, reads or bypasses a HumanApproval.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from shared.sdk.agent_planning.models import (
    PlanLineageError,
    PlanStepDraftError,
    StalePlanRevisionError,
)
from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from shared.sdk.plan_delegation.models import (
    ExecutionLineageCancelledError,
    ExecutionUnitStateError,
    PlanGraphInvalidError,
    PlanRevisionNotDispatchableError,
)
from shared.sdk.plan_delegation.service import PlanDelegationService

router = APIRouter(prefix="/plan-delegation", tags=["plan-delegation"])


def _service() -> PlanDelegationService:
    """The delegation runtime, wired to the internal event bus.

    The bus is the transport for a work ASSIGNMENT, never for an external action: the envelope it
    carries declares every external-effect flag false, and no consumer of it is authorized to
    perform one in this slice.
    """
    return PlanDelegationService(event_bus=RedisStreamEventBus())


class MaterializeRequest(BaseModel):
    """Two identifiers and an author. No plan, no steps, no owners -- deliberately.

    ``extra="forbid"`` is load-bearing rather than tidy: a request carrying a ``plan`` or a
    ``steps`` field is refused with a 422 naming it, instead of being silently ignored and leaving
    the sender believing it defined the work.
    """

    model_config = ConfigDict(extra="forbid")

    goal_id: str = Field(min_length=1)
    #: The principal recorded as having materialized the graph. An attribution, not an authority:
    #: it grants nothing, and the plan it materializes is the one the team already accepted.
    materialized_by: str = Field(min_length=1)


class ScheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Propagated onto every dispatch envelope so one plan's delegation shares a distributed trace.
    trace_id: str = Field(default="", max_length=200)


def _unit_view(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "execution_unit_id": str(row["execution_unit_id"]),
        "plan_revision_id": str(row["plan_revision_id"]),
        "step_key": row["step_key"],
        "work_item_id": str(row["work_item_id"]),
        "state": row["state"],
        "required_capabilities": list(row["required_capabilities"] or []),
        "expected_outputs": list(row["expected_outputs"] or []),
        "intended_owner_role": row.get("intended_owner_role"),
        # Present exactly when the unit is ready and the team has nobody eligible.
        "unavailable_reason": row.get("unavailable_reason"),
        "assigned_principal_id": (
            str(row["assigned_principal_id"]) if row.get("assigned_principal_id") else None
        ),
        "assigned_role": row.get("assigned_role"),
        "assigned_agent_key": row.get("assigned_agent_key"),
        # The AT-M2 routing evidence: eligible set, rejection reasons, and why the winner won.
        "routing_decision_id": (
            str(row["routing_decision_id"]) if row.get("routing_decision_id") else None
        ),
        "assigned_at": row.get("assigned_at"),
        "disposition": row.get("disposition"),
        "result_ref": row.get("result_ref"),
        "completed_at": row.get("completed_at"),
    }


def _dispatch_view(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "execution_unit_id": str(row["execution_unit_id"]),
        # The exact revision that authorized this dispatch. Never rebound.
        "plan_revision_id": str(row["plan_revision_id"]),
        "step_key": row["step_key"],
        "assigned_principal_id": str(row["assigned_principal_id"]),
        # The isolated delegation stream this command was staged on -- never a live agent input
        # stream, and nothing consumes it until AT-M4.
        "target_stream": row["target_stream"],
        # An IDENTIFIER, not a credential. It exists so a delegation can be reconstructed and
        # so a future AT-M4 consumer can dedupe a redelivery; holding it grants nothing, and no
        # operation in this slice accepts it as authority.
        "correlation_id": str(row["correlation_id"]),
        # NULL means the canonical dispatch exists but the transport has not carried it yet.
        "published_at": row.get("published_at"),
        "created_at": row.get("created_at"),
    }


def _graph_view(graph: dict[str, Any]) -> dict[str, Any]:
    row = graph["graph"]
    return {
        "plan_execution_graph_id": str(row["plan_execution_graph_id"]),
        "project_id": str(row["project_id"]),
        "goal_id": str(row["goal_id"]),
        "plan_revision_id": str(row["plan_revision_id"]),
        # Derived from lineage, never stored: false means a successor revision exists, so this
        # graph may no longer authorize NEW dispatch.
        "is_current": graph.get("is_current"),
        "primary_work_item_id": str(graph["primary_work_item_id"]),
        "step_count": row["step_count"],
        "units": [_unit_view(unit) for unit in graph["units"]],
        "dependencies": [dict(edge) for edge in graph.get("dependencies", [])],
        "dispatches": [_dispatch_view(d) for d in graph.get("dispatches", [])],
    }


def _raise_domain(exc: Exception) -> None:
    """Map a delegation domain failure onto a status code. Never a 500 for a caller-visible fact."""
    if isinstance(exc, StalePlanRevisionError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, ExecutionLineageCancelledError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, PlanRevisionNotDispatchableError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, PlanLineageError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, ExecutionUnitStateError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, (PlanGraphInvalidError, PlanStepDraftError)):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, asyncpg.PostgresError):
        raise HTTPException(
            status_code=503, detail=f"delegation store unavailable: {type(exc).__name__}"
        ) from exc
    raise exc


@router.post("/plan-revisions/{plan_revision_id}/materialize")
async def materialize_plan(plan_revision_id: str, payload: MaterializeRequest) -> dict:
    """Turn one accepted, current PlanRevision into its durable execution graph.

    Safe to retry and safe to call concurrently: a repeat returns the canonical graph with
    ``created=false`` rather than building a second one. That is an outcome, not an error.

    409 means the revision may not create a graph -- it is a draft, it belongs to another Goal, or
    a successor has superseded it. A superseded revision is never silently materialized: the work
    it would have authorized is not authoritative any more, and the successor materializes its own
    graph rather than adopting this one.

    422 means the stored plan is not executable -- a cycle, a dependency on a step that does not
    exist, or no steps at all. Nothing is written in that case; there is no partial graph.
    """
    try:
        result = await _service().materialize_accepted_plan(
            goal_id=payload.goal_id,
            plan_revision_id=plan_revision_id,
            materialized_by=payload.materialized_by,
        )
    except Exception as exc:  # noqa: BLE001 - re-raised unless it is a mapped domain failure
        _raise_domain(exc)
        raise
    graph = await _service().get_graph(plan_revision_id)
    return {"created": result["created"], "graph": _graph_view(graph)}  # type: ignore[arg-type]


@router.post("/plan-revisions/{plan_revision_id}/schedule")
async def schedule_plan(plan_revision_id: str, payload: ScheduleRequest) -> dict:
    """Assign, dispatch and publish every step of this graph that is due.

    One pass. A step with an unmet dependency is not touched; a step nobody on the team can take is
    left ready with an honest reason rather than given to an unrelated agent; a step already
    dispatched is not dispatched again.

    409 means the whole graph may not proceed: its revision has been superseded, or the Goal's
    primary work item is cancelled. Both are facts about the graph rather than about one step, so
    the pass stops instead of dispatching the rest of a plan that is no longer authoritative.
    """
    try:
        return await _service().schedule_ready_work(
            plan_revision_id=plan_revision_id, trace_id=payload.trace_id
        )
    except Exception as exc:  # noqa: BLE001 - re-raised unless it is a mapped domain failure
        _raise_domain(exc)
        raise


@router.get("/plan-revisions/{plan_revision_id}/graph")
async def get_graph(plan_revision_id: str) -> dict:
    """The execution graph for one PlanRevision: units, states, dependencies and dispatches."""
    graph = await _service().get_graph(plan_revision_id)
    if graph is None:
        raise HTTPException(
            status_code=404,
            detail=f"plan revision {plan_revision_id} has no materialized execution graph",
        )
    return _graph_view(graph)


@router.get("/execution-units/{execution_unit_id}")
async def get_execution_unit(execution_unit_id: str) -> dict:
    """One execution unit: its state, its owner, why it has one, and its dispatch."""
    unit = await _service().get_unit(execution_unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail=f"unknown execution unit {execution_unit_id}")
    view = _unit_view(unit)
    view["dispatch"] = _dispatch_view(unit.get("dispatch"))
    return view
