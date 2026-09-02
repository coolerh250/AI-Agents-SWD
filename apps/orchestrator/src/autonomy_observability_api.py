"""Step AT-M3.6A -- the autonomous-runtime observability surface, mounted under ``/operations``.

WHY ``/operations`` AND NOT ``/observability``
``/operations/*`` is already this repository's canonical operational read domain: the Admin Console
calls nothing else, and eighteen routers -- ``/operations/admin-console``, ``/operations/metrics``,
``/operations/delivery``, ``/operations/readiness``, ``/operations/security`` and the rest -- are
sub-namespaces of it. A second root would produce two competing representations of one runtime, and
the first question a reader would then have to answer is which of the two is right. So AT-M3.6A
extends the existing domain with ``/operations/autonomy`` and changes no existing route, no existing
response schema and no existing field. It is purely additive; an Admin Console reading
``/operations`` today sees exactly what it saw before.

The AT-M3 command surfaces stay where they are. ``/planning``, ``/discussions``,
``/planning-decisions`` and ``/plan-delegation`` own the WRITES and their own read routes; this
router duplicates none of them. What it adds is the thing none of them can give: the lineage
ACROSS all four, from a Goal down to a dispatched step, without a caller joining six APIs by hand.

EVERY ROUTE HERE IS A GET, AND EVERY GET IS PURE
No POST, PUT, PATCH or DELETE is defined, and none may be added: a write on this router would be a
second authority over state the AT-M3.1-3.5 command surfaces own. No handler assigns, dispatches,
completes, replays, retries, cancels, aborts, approves, replans, materializes, calls a provider or
publishes to Redis. No handler writes a business audit event -- viewing a page is not a decision,
and an audit chain that records reads stops being a record of what the team DID.

TRUTHS THIS ROUTER REFUSES TO BLUR
* A dispatch is ``DISPATCHED_TO_CONTROL_STREAM``. The AT-M3.5 namespace has no consumer, so
  ``published_at`` is not evidence that work started, and no field here says "executing".
* A completion is ``internal_control_plane_simulation``. AT-M4 does not exist; nothing this surface
  can see is a real agent execution and nothing here is labelled one.
* A superseded revision's graph is ``HISTORICAL_SUPERSEDED`` and stays fully readable. It is never
  rebound to the current revision and never folded into current-plan progress.

PARTIAL STATE IS NOT AN ERROR. A Goal with no discussion, a converged discussion with no decision,
an accepted plan with no graph, a graph with no assignment, a dispatch with no publish and a
cancelled lineage all return 200 with the truth in them. 404 means an identifier resolved to
nothing at all.
"""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, HTTPException, Query

from shared.sdk.autonomy_observability.contracts import (
    DiscussionReasoningView,
    ExecutionGraphView,
    ExecutionUnit,
    GoalAutonomyOverview,
    GoalTimeline,
    PlanRevisionHistory,
)
from shared.sdk.autonomy_observability.service import (
    AutonomyObservabilityService,
    EntityNotFound,
    GoalNotFound,
)
from shared.sdk.autonomy_observability.store import DEFAULT_PAGE, MAX_PAGE

router = APIRouter(prefix="/operations/autonomy", tags=["autonomy-observability"])


def _service() -> AutonomyObservabilityService:
    """The read service, with no event bus and no audit client -- it has nothing to publish."""
    return AutonomyObservabilityService()


def _unavailable(exc: asyncpg.PostgresError) -> HTTPException:
    """A driver failure is an upstream availability problem, not a 500 the caller can act on.

    The same mapping AT-M3.2 adopted after its Validation 1 found a raw ``UniqueViolationError``
    escaping to the client: the exception TYPE is reported, never its message, so a DSN or a table
    fragment cannot ride out in an error body.
    """
    return HTTPException(
        status_code=503, detail=f"autonomy read model unavailable: {type(exc).__name__}"
    )


@router.get("/goals/{goal_id}", response_model=GoalAutonomyOverview)
async def goal_autonomy_overview(
    goal_id: str,
    turn_limit: int = Query(default=50, ge=1, le=MAX_PAGE),
) -> GoalAutonomyOverview:
    """What this autonomous team is doing right now, and why.

    One read returns the whole lineage as entities: Goal, Project, primary WorkItem, team,
    current discussion with its seats and turn summaries, TeamDecision, current accepted
    PlanRevision, the current execution graph with every unit's dependencies, assignment, routing
    evidence and dispatch, the derived phase, the blockers behind it, and the superseded graphs
    that came before.

    It answers with entities first and counts second. The failure this ordering exists to correct
    is a product that showed aggregate summaries while WorkItem identity, execution evidence and
    audit lineage stayed invisible.

    404 only when the goal id resolves to no Goal. Every legitimate partial state -- no team, no
    discussion, no plan, no graph, no assignment, cancelled -- is a 200 that says so.
    """
    try:
        return GoalAutonomyOverview.model_validate(
            await _service().goal_overview(goal_id, turn_limit=turn_limit)
        )
    except GoalNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"malformed goal id {goal_id!r}") from exc
    except asyncpg.PostgresError as exc:
        raise _unavailable(exc) from exc


@router.get("/goals/{goal_id}/plan-revisions", response_model=PlanRevisionHistory)
async def goal_plan_revision_history(
    goal_id: str,
    limit: int = Query(default=DEFAULT_PAGE, ge=1, le=MAX_PAGE),
    offset: int = Query(default=0, ge=0),
) -> PlanRevisionHistory:
    """Every PlanRevision this Goal has had, oldest first, with what each one actually dispatched.

    Revision N stays here when N+1 becomes current -- history is not rewritten to look current --
    and each entry carries its own graph's state counts and canonical dispatch counts, so "did the
    work the superseded plan dispatched ever finish" is answerable without a second call per
    revision.
    """
    try:
        return PlanRevisionHistory.model_validate(
            await _service().plan_revision_history(goal_id, limit=limit, offset=offset)
        )
    except GoalNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"malformed goal id {goal_id!r}") from exc
    except asyncpg.PostgresError as exc:
        raise _unavailable(exc) from exc


@router.get("/plan-revisions/{plan_revision_id}/execution-graph", response_model=ExecutionGraphView)
async def plan_revision_execution_graph(
    plan_revision_id: str,
    limit: int = Query(default=MAX_PAGE, ge=1, le=MAX_PAGE),
    offset: int = Query(default=0, ge=0),
) -> ExecutionGraphView:
    """One revision's execution graph: units, dependency topology, routing, dispatch, terminal state.

    Every unit carries ``depends_on`` and ``unlocks`` as execution-unit and step identifiers, so a
    frontend can lay the DAG out without parsing PlanContent text. Both endpoints of every edge are
    required to belong to this revision, so another revision's -- or another Goal's -- work can
    never appear as this graph's topology.

    A superseded revision returns its graph in full, marked ``HISTORICAL_SUPERSEDED``. Hiding it
    would destroy the record of work that genuinely happened under it.
    """
    try:
        return ExecutionGraphView.model_validate(
            await _service().execution_graph(plan_revision_id, limit=limit, offset=offset)
        )
    except EntityNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"malformed plan revision id {plan_revision_id!r}"
        ) from exc
    except asyncpg.PostgresError as exc:
        raise _unavailable(exc) from exc


@router.get("/execution-units/{execution_unit_id}", response_model=ExecutionUnit)
async def execution_unit_detail(execution_unit_id: str) -> ExecutionUnit:
    """One execution unit: its state, its owner, why it has one, its dispatch and its lineage.

    ``routing.candidates_considered`` answers "why was this agent selected" from the recorded
    AT-M2 evidence -- the eligible set, each rejection reason, and the reason the winner won. That
    is explainability of a deterministic rule; there is no model reasoning in it to leak.
    """
    try:
        return ExecutionUnit.model_validate(await _service().execution_unit(execution_unit_id))
    except EntityNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"malformed execution unit id {execution_unit_id!r}"
        ) from exc
    except asyncpg.PostgresError as exc:
        raise _unavailable(exc) from exc


@router.get("/goals/{goal_id}/timeline", response_model=GoalTimeline)
async def goal_audit_timeline(
    goal_id: str,
    limit: int = Query(default=DEFAULT_PAGE, ge=1, le=MAX_PAGE),
    offset: int = Query(default=0, ge=0),
) -> GoalTimeline:
    """The Goal's correlated operational timeline, from audit events that were actually written.

    Discussion, reasoning, TeamDecision, plan acceptance, materialization, assignment, dispatch and
    internal completion, in one ordered, bounded list. Ordering is ``created_at ASC, audit_id ASC``
    -- the audit row's UUID primary key is the stable secondary key, so events sharing a timestamp
    cannot be duplicated or skipped across a page boundary.

    EVIDENCE, NOT AUTHORITY. Nothing here is synthesised from current state: an event that was never
    recorded produces no entry, so a gap is a real gap. Where evidence and the canonical tables
    disagree, the canonical tables are what is true.
    """
    try:
        return GoalTimeline.model_validate(
            await _service().goal_timeline(goal_id, limit=limit, offset=offset)
        )
    except GoalNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"malformed goal id {goal_id!r}") from exc
    except asyncpg.PostgresError as exc:
        raise _unavailable(exc) from exc


@router.get("/discussions/{discussion_id}/reasoning", response_model=DiscussionReasoningView)
async def discussion_reasoning(
    discussion_id: str,
    limit: int = Query(default=DEFAULT_PAGE, ge=1, le=MAX_PAGE),
    offset: int = Query(default=0, ge=0),
) -> DiscussionReasoningView:
    """Safe operational metadata for the reasoning behind one discussion.

    Verb, provider name and mode, status, attempt, round, timing, token counts, sanitized failure
    reason, artifact TYPE, and the turn each attempt belonged to.

    THE ARTIFACT BODY IS NOT HERE, and that is a design decision rather than an omission.
    ``reasoning_invocations.artifact`` is AT-M3.4's durable RECOVERY record; exposing it would make
    this endpoint a second business surface for a decision that already has one. The business
    artifact is read through TeamMessage, the planning candidate message and PlanRevision. No
    prompt, completion, scratchpad, hidden instruction or token trace exists in these columns to
    expose -- AT-D03 R8 / INV-04 keeps them out of the schema entirely.
    """
    try:
        return DiscussionReasoningView.model_validate(
            await _service().discussion_reasoning(discussion_id, limit=limit, offset=offset)
        )
    except EntityNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"malformed discussion id {discussion_id!r}"
        ) from exc
    except asyncpg.PostgresError as exc:
        raise _unavailable(exc) from exc
