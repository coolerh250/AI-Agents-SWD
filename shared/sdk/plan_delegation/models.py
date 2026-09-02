"""Step AT-M3.5 -- plan-driven delegation domain logic. Pure: no I/O, no database, no transport.

Everything here is a function of its arguments, which is what makes a delegation decision
reproducible: the same accepted plan and the same team always produce the same graph, the same
assignment and the same reason. Persistence, transactions and dispatch are ``store.py`` and
``service.py``.

Three things this module deliberately does NOT do:

* **It does not define a capability vocabulary.** ``shared/sdk/agent_team/capabilities.py`` is the
  only one, and :func:`resolve_step_assignment` reads the plan's declared capabilities against it
  rather than translating them into a local dialect.
* **It does not decide successors.** The AT-M2 router does, from the team as it is right now.
  There is no ``intake -> requirement -> development -> qa -> devops`` anywhere in this slice, and
  the negative test for that is part of the suite.
* **It does not re-validate what PlanContent already guarantees, except where a stored plan could
  violate it.** Duplicate step keys, unknown dependency targets and self-dependency are checked by
  ``PlanContent`` at parse time and are re-checked here only because a plan row is read back out
  of JSONB years later and must fail closed rather than materialize half a graph. Cycles are the
  genuinely new check: ``PlanContent`` never looked for one.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from shared.sdk.agent_planning.models import PlanContent, PlanStep
from shared.sdk.agent_team.capabilities import requires_human_approval
from shared.sdk.agent_team.models import assert_content_is_safe
from shared.sdk.agent_team.router import (
    RoutingCandidate,
    RoutingDecision,
    RoutingRequest,
    route,
)
from shared.sdk.project_planning.dependency_validator import (
    STATUS_INVALID,
    validate_dependencies,
)
from shared.sdk.project_planning.models import (
    ProjectWorkItem,
    TaskGraph,
    WorkItemDependency,
)

# --- unit state vocabulary ---------------------------------------------------------------------
#
# Seven values, matching the migration's CHECK. Not a new state machine: it is the minimum needed
# to say whether a step may be assigned, has been handed to someone, or is over.

UNIT_BLOCKED = "blocked"
UNIT_READY = "ready"
UNIT_ASSIGNED = "assigned"
UNIT_DISPATCHED = "dispatched"
UNIT_COMPLETED = "completed"
UNIT_FAILED = "failed"
UNIT_CANCELLED = "cancelled"

UNIT_STATES: frozenset[str] = frozenset(
    {
        UNIT_BLOCKED,
        UNIT_READY,
        UNIT_ASSIGNED,
        UNIT_DISPATCHED,
        UNIT_COMPLETED,
        UNIT_FAILED,
        UNIT_CANCELLED,
    }
)

TERMINAL_UNIT_STATES: frozenset[str] = frozenset({UNIT_COMPLETED, UNIT_FAILED, UNIT_CANCELLED})

#: The completion condition a dependency must satisfy before a dependent may become ready. Only
#: ``completed`` unlocks: a failed or cancelled dependency has NOT produced what its dependent was
#: promised, and treating it as satisfied would dispatch work against outputs that do not exist.
DEPENDENCY_SATISFIED_STATES: frozenset[str] = frozenset({UNIT_COMPLETED})

#: Terminal outcomes an assigned principal may report back. Deliberately two: this slice tracks
#: whether the step is over and how, not why. Diagnosis is AT-M4's ``DebugAttempt``.
DISPOSITION_SUCCEEDED = "succeeded"
DISPOSITION_FAILED = "failed"
DISPOSITIONS: frozenset[str] = frozenset({DISPOSITION_SUCCEEDED, DISPOSITION_FAILED})

#: Why a ready unit has no owner. A closed vocabulary, so the read surface reports a fact rather
#: than free text, and so "nobody can do this" is never confused with "nobody has looked yet".
UNAVAILABLE_NO_ELIGIBLE_AGENT = "capability_unavailable"
UNAVAILABLE_REQUIRES_HUMAN_APPROVAL = "requires_human_approval"

_ROUTING_OUTCOME_TO_REASON = {
    "no_eligible_agent": UNAVAILABLE_NO_ELIGIBLE_AGENT,
    "requires_human_approval": UNAVAILABLE_REQUIRES_HUMAN_APPROVAL,
}

#: The isolated namespace AT-M3.5 stages its delegation commands on.
#:
#: AT-M3.5 must NOT publish onto an agent's own ``transport_stream``. Those streams
#: (``stream.development``, ``stream.qa``, ``stream.design_review`` ...) are live: a ``StreamAgent``
#: subclass consumes each of them and calls ``handle(payload)`` unconditionally, and the
#: orchestrator's workflow-event consumer watches several of them too. Putting a
#: ``plan_step.dispatched`` envelope there would hand an L3 coordination message to an L4 executor
#: that this slice has no authority to start -- AT-M4 execution reached by accident, through a
#: stream name.
#:
#: So routing and transport are separated, and only transport moves. The AT-M2 router still decides
#: WHO, from capability over the live team, and its answer -- including the agent's real
#: ``transport_stream`` -- is recorded unchanged in ``agent_routing_decisions``. What changes is
#: WHERE the coordination message is staged: a dedicated namespace with no consumer at all until
#: AT-M4 introduces one.
DELEGATION_STREAM_PREFIX = "stream.plan_delegation"

#: ``agent_key`` is a ``TEXT`` column, and this is the one place a database value becomes an
#: addressable Redis key. Keys outside this shape are refused rather than escaped, so a delegation
#: stream can never be coaxed into naming something else.
_SAFE_AGENT_KEY = re.compile(r"^[A-Za-z0-9._-]{1,100}$")

#: How a unit's runtime state is mirrored onto the work item that carries it. The work item is the
#: execution-lineage row every existing reader already knows how to read; leaving it permanently
#: 'pending' while the unit moved would make the lineage carrier lie. The unit remains canonical --
#: this mapping is lossy on purpose (``assigned`` and ``ready`` are both 'ready' to a work item,
#: which has no vocabulary for "owned but not yet handed over").
_WORK_ITEM_STATUS = {
    UNIT_BLOCKED: "blocked",
    UNIT_READY: "ready",
    UNIT_ASSIGNED: "ready",
    UNIT_DISPATCHED: "in_progress",
    UNIT_COMPLETED: "completed",
    UNIT_FAILED: "failed",
    UNIT_CANCELLED: "cancelled",
}


class PlanGraphInvalidError(ValueError):
    """A stored plan cannot become an execution graph.

    Raised BEFORE anything is written, so an invalid plan never leaves a partial graph behind.
    Carries the structured errors the shared dependency validator produced rather than a sentence,
    because the caller that has to fix the plan needs to know which step is wrong.
    """

    def __init__(self, message: str, *, errors: tuple[dict[str, Any], ...] = ()) -> None:
        self.errors = errors
        super().__init__(message)


class PlanRevisionNotDispatchableError(ValueError):
    """The named revision may not create or advance an execution graph.

    A draft, proposed or rejected revision, or a revision belonging to another Goal. Superseded
    revisions are NOT reported through this type: staleness is AT-M3.2's
    ``StalePlanRevisionError``, raised by AT-M3.2's own compare-and-swap, and giving it a second
    name here would let a reader think there were two stale-plan mechanisms.
    """


class ExecutionUnitStateError(RuntimeError):
    """A unit was asked to make a transition its current state does not permit."""


class DispatchLineageError(RuntimeError):
    """A result was reported for a unit that has no canonical dispatch.

    Nothing was ever handed to anyone, so there is no assignment for a result to answer. The
    identity a result is attributed to -- assigned principal, correlation id, plan revision, step --
    is READ from that row and is never accepted from a caller, so the only way to be wrong about it
    is for it not to exist.
    """


class DispatchTransportError(RuntimeError):
    """A selected agent's key cannot be turned into an isolated delegation stream name.

    Fail closed rather than build an unpredictable Redis key out of arbitrary text: a stream name
    is the one place where a database value becomes an addressable destination, and an unsanitised
    one could collide with a stream something else already consumes.
    """


class ExecutionLineageCancelledError(RuntimeError):
    """The Goal's primary work item is cancelled; no new work may be assigned or dispatched.

    Existing dispatches are not withdrawn by this -- cancellation stops NEW work, and the
    already-dispatched command follows the existing work-item cancel semantics.
    """


# --- isolated delegation transport ---------------------------------------------------------------


def delegation_stream_for(agent_key: str) -> str:
    """The isolated delegation stream for one selected agent.

    Keyed on ``agent_key`` rather than on ``role`` because ``agent_key`` is the unique one:
    ``development-agent`` and ``development-agent-autofix`` share the role ``development`` and are
    two different workers, and giving them one stream would put a command addressed to one of them
    in the other's reach.
    """
    if not agent_key or not _SAFE_AGENT_KEY.match(agent_key):
        raise DispatchTransportError(
            f"agent key {agent_key!r} cannot be used to derive a delegation stream name; "
            "expected 1-100 characters of [A-Za-z0-9._-]"
        )
    return f"{DELEGATION_STREAM_PREFIX}.{agent_key}"


def is_delegation_stream(stream: str) -> bool:
    """True for the delegation namespace itself and anything under it."""
    return stream == DELEGATION_STREAM_PREFIX or stream.startswith(f"{DELEGATION_STREAM_PREFIX}.")


# --- graph validation ---------------------------------------------------------------------------


def plan_dependency_edges(plan: PlanContent) -> tuple[tuple[str, str], ...]:
    """Every ``(step_key, depends_on_step_key)`` edge in the plan, in declared order."""
    return tuple((step.step_key, parent) for step in plan.steps for parent in step.depends_on)


def _as_task_graph(plan: PlanContent) -> TaskGraph:
    """Express the plan as the shape the EXISTING dependency validator already understands.

    planning-and-plan-revision-model.md section 4 says plan validation "reuses the EXISTING
    dependency validator -- that logic is sound and is preserved". This is that reuse: a
    translation, not a second validator. Only the fields the validator reads are populated.
    """
    return TaskGraph(
        project_type="plan_revision",
        template="at_m3_5_runtime",
        work_items=[
            ProjectWorkItem(work_item_key=step.step_key, title=step.title) for step in plan.steps
        ],
        dependencies=[
            WorkItemDependency(work_item_key=child, depends_on_work_item_key=parent)
            for child, parent in plan_dependency_edges(plan)
        ],
    )


def root_step_keys(plan: PlanContent) -> tuple[str, ...]:
    """The steps with no dependencies -- ready the moment the graph is materialized."""
    return tuple(step.step_key for step in plan.steps if not step.depends_on)


def validate_plan_graph(plan: PlanContent) -> None:
    """Fail closed unless this plan can become a runtime DAG.

    ``PlanContent`` already rejects duplicate step keys, dependencies on steps that do not exist
    and self-dependency at parse time. Those are re-checked here through the shared validator
    because a plan is read back out of a JSONB column that outlives the code which wrote it, and
    a historical row that violates today's assumptions must stop the materialization rather than
    produce half a graph.

    Two checks are genuinely new. ``PlanContent`` never looked for a CYCLE -- three steps that
    depend on each other satisfy every one of its rules and would produce a graph in which nothing
    is ever ready. And a plan with NO steps has no executable work at all, which is a plan the
    delegation layer cannot honour rather than an empty success.
    """
    if not plan.steps:
        raise PlanGraphInvalidError(
            "the plan declares no steps, so it materializes no executable work"
        )

    result = validate_dependencies(_as_task_graph(plan))
    if result.status == STATUS_INVALID:
        raise PlanGraphInvalidError(
            f"the plan's dependency graph is not executable: {result.to_list()}",
            errors=tuple(result.to_list()),
        )

    # Belt and braces after a clean validator run: a DAG with at least one node always has a node
    # with no incoming dependency, so an empty root set here means the validator's cycle detection
    # and this function disagree. Failing closed is the only safe response to that.
    if not root_step_keys(plan):
        raise PlanGraphInvalidError(
            "every step depends on another, so no step can ever become ready"
        )


# --- assignment ---------------------------------------------------------------------------------


def _considered_against_all(
    candidate: RoutingCandidate, capabilities: tuple[str, ...]
) -> dict[str, Any]:
    """One candidate's eligibility for the WHOLE conjunction the step requires.

    Same shape the AT-M2 router records for a single capability, so the evidence in
    ``agent_routing_decisions.candidates_considered`` reads identically whether a step needed one
    capability or three.
    """
    rejected = ""
    for capability in capabilities:
        reason = candidate.ineligibility(capability)
        if reason:
            rejected = reason if reason != "capability_not_declared" else f"missing:{capability}"
            break
    return {
        "principal_id": candidate.principal_id,
        "agent_key": candidate.agent_key,
        "role": candidate.role,
        "eligible": not rejected,
        "rejected_because": rejected or None,
    }


def resolve_step_assignment(
    *,
    required_capabilities: tuple[str, ...],
    candidates: list[RoutingCandidate],
    project_id: str,
    intended_owner_role: str | None = None,
    work_item_id: str | None = None,
) -> RoutingDecision:
    """Decide which Project-team principal takes this plan step, and say why.

    The AT-M2 router remains the selection authority: it applies the policy boundary, the
    eligibility rules and the deterministic tie-break, and it produces the reason and the
    considered set. Two things it cannot express are supplied here, and only those two.

    **A conjunction.** ``route()`` answers "who can do X". A plan step may require X *and* Y, and
    an agent that declares only X must not receive it. Candidates are therefore pre-filtered on
    the full set before the router chooses among them -- and the considered set is rebuilt over
    ALL candidates against the full conjunction, so a member excluded by the filter still appears
    with the capability it was missing rather than vanishing from the evidence.

    **The policy boundary over the whole set.** ``route()`` refers a production-effect capability
    to the human approval boundary; it checks the capability it was asked about. A step requiring
    a safe capability *and* a production-effect one must be referred too, so a production-effect
    member of the set is promoted to the requested capability and the router reaches its own
    ``requires_human_approval`` answer. Routing still never approves anything.

    ``intended_owner_role`` is the plan's ownership INTENT. It travels as ``preferred_role``: a
    preference the router honours when someone eligible matches and ignores otherwise. Plan text
    can therefore influence which eligible principal is chosen and can never invent one.
    """
    capabilities = tuple(required_capabilities)
    considered = tuple(_considered_against_all(c, capabilities) for c in candidates)

    # A production-effect capability anywhere in the set is the answer for the whole step.
    gated = next((c for c in capabilities if requires_human_approval(c)), None)
    primary = gated or (capabilities[0] if capabilities else "")

    if gated is None and len(capabilities) > 1:
        secondary = tuple(c for c in capabilities if c != primary)
        eligible = [c for c in candidates if all(not c.ineligibility(cap) for cap in secondary)]
    else:
        eligible = list(candidates)

    decision = route(
        RoutingRequest(
            requested_capability=primary,
            project_id=str(project_id),
            work_item_id=work_item_id,
            preferred_role=intended_owner_role,
        ),
        eligible,
    )
    decision = replace(decision, candidates_considered=considered)

    if len(capabilities) > 1:
        joined = ", ".join(capabilities)
        if decision.outcome == "selected":
            decision = replace(decision, reason=f"{decision.reason}; covers all of {joined}")
        elif decision.outcome == "no_eligible_agent":
            decision = replace(
                decision,
                reason=(
                    f"no active team member covers all of {joined} "
                    f"({len(candidates)} member(s) considered)"
                ),
            )
    if not capabilities:
        decision = replace(
            decision,
            reason=(
                "the plan step declares no required capability, so no agent can be selected "
                "from capability"
            ),
        )
    return decision


def unavailable_reason_for(decision: RoutingDecision) -> str | None:
    """The closed-vocabulary reason a ready unit has no owner, or None when it does."""
    if decision.outcome == "selected":
        return None
    return _ROUTING_OUTCOME_TO_REASON.get(decision.outcome, UNAVAILABLE_NO_ELIGIBLE_AGENT)


def work_item_status_for(unit_state: str) -> str:
    """The ``project_work_items.status`` that mirrors a unit state."""
    return _WORK_ITEM_STATUS[unit_state]


# --- dispatch envelope ---------------------------------------------------------------------------


def build_dispatch_envelope(
    *,
    project_id: str,
    goal_id: str,
    primary_work_item_id: str,
    work_item_id: str,
    execution_unit_id: str,
    plan_revision_id: str,
    step: PlanStep,
    assigned_principal_id: str,
    assigned_role: str | None,
    correlation_id: str,
    trace_id: str = "",
) -> dict[str, Any]:
    """The structured work command handed to the assigned principal.

    Identifiers plus THIS STEP'S OWN contract, and nothing else. Not the PlanContent, not the
    sibling steps, not the objective, not the discussion the plan came from, not a reasoning
    artifact -- a principal receiving one step is told what that step is and what it must produce,
    which is the bounded contract the security boundary requires and not full internal state.

    Every external-effect flag is present and false, following the Step 57 dispatch envelope's own
    convention: an agent reading this event is told explicitly that no production action, GitHub
    write, deployment or external send is authorized by it. This slice hands over a work
    assignment; it does not hand over permission.

    Screened with the same ``assert_content_is_safe`` helper every other AT-M2/AT-M3 payload uses,
    rather than a second, parallel mechanism.
    """
    envelope: dict[str, Any] = {
        "event": "plan_step.dispatched",
        # --- lineage -------------------------------------------------------------------------
        "project_id": str(project_id),
        "goal_id": str(goal_id),
        "primary_work_item_id": str(primary_work_item_id),
        "work_item_id": str(work_item_id),
        "execution_unit_id": str(execution_unit_id),
        "plan_revision_id": str(plan_revision_id),
        "step_key": step.step_key,
        # --- the step's own bounded contract ---------------------------------------------------
        "title": step.title,
        "description": step.description,
        "required_capabilities": list(step.required_capabilities),
        "expected_outputs": list(step.expected_outputs),
        "constraints": list(step.constraints),
        "depends_on": list(step.depends_on),
        # --- ownership -------------------------------------------------------------------------
        "assigned_principal_id": str(assigned_principal_id),
        "assigned_role": assigned_role,
        # --- transport identity ------------------------------------------------------------------
        # Stable across redelivery: a consumer that has applied this id knows the second copy is
        # the same dispatch, not a second one.
        "correlation_id": str(correlation_id),
        # --- what this command does NOT authorize -------------------------------------------------
        "production_action": False,
        "production_effect": False,
        "github_write": False,
        "argocd_sync": False,
        "external_notification_send": False,
        "code_execution": False,
    }
    if trace_id:
        envelope["trace_id"] = trace_id
    assert_content_is_safe(envelope, field="dispatch_envelope")
    return envelope


__all__ = [
    "DELEGATION_STREAM_PREFIX",
    "DEPENDENCY_SATISFIED_STATES",
    "DISPOSITIONS",
    "DISPOSITION_FAILED",
    "DISPOSITION_SUCCEEDED",
    "DispatchLineageError",
    "DispatchTransportError",
    "ExecutionLineageCancelledError",
    "ExecutionUnitStateError",
    "PlanGraphInvalidError",
    "PlanRevisionNotDispatchableError",
    "TERMINAL_UNIT_STATES",
    "UNAVAILABLE_NO_ELIGIBLE_AGENT",
    "UNAVAILABLE_REQUIRES_HUMAN_APPROVAL",
    "UNIT_ASSIGNED",
    "UNIT_BLOCKED",
    "UNIT_CANCELLED",
    "UNIT_COMPLETED",
    "UNIT_DISPATCHED",
    "UNIT_FAILED",
    "UNIT_READY",
    "UNIT_STATES",
    "build_dispatch_envelope",
    "delegation_stream_for",
    "is_delegation_stream",
    "plan_dependency_edges",
    "resolve_step_assignment",
    "root_step_keys",
    "unavailable_reason_for",
    "validate_plan_graph",
    "work_item_status_for",
]
