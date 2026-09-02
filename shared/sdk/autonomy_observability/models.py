"""Step AT-M3.6A -- the derivation rules behind the autonomous-runtime read surface.

Pure. No I/O, no store, no connection. Every function here takes a snapshot of canonical rows that
a caller already read and returns a DERIVED answer, so the same snapshot always produces the same
phase, the same blockers and the same progress -- and so those rules can be tested without a
database standing in for a decision table.

**Nothing derived here is authoritative, and none of it is persisted.** ``autonomy_phase``,
``progress``, ``blockers`` and currentness are read-time functions of canonical state, exactly as
``planning-and-plan-revision-model.md`` 11b keeps plan currency a function of lineage. A stored
copy would be this project's first second answer to a question the canonical tables already answer
exactly -- and would need a writer, a race story and a repair path that the derived form does not.
That is why AT-M3.6A adds no observability table, no phase column and no percent-complete column.

TRUTH BOUNDARIES THIS MODULE IS RESPONSIBLE FOR

* A canonical dispatch is ``DISPATCHED_TO_CONTROL_STREAM``, never ``EXECUTING``. The AT-M3.5
  delegation namespace has no consumer, so ``published_at`` proves a command was staged, not that
  work began.
* A terminal unit carries ``execution_mode = internal_control_plane_simulation``. AT-M4 does not
  exist, so no completion this surface can see is a real agent execution, and none may be
  labelled one.
* A superseded revision's graph stays visible and stays HISTORICAL. It is never rebound to the
  current revision and never counted in current-plan progress.
"""

from __future__ import annotations

from typing import Any

# --- derived autonomy phase ----------------------------------------------------------------------
#
# A LABEL for what the team is doing right now, derived on every read. It is not a lifecycle, it
# has no transitions, nothing writes it, and nothing reads it to decide anything. A phase column
# would create a second authority over a question the discussion, planning-decision, revision,
# graph and unit rows already answer between them.

PHASE_TEAM_FORMATION = "TEAM_FORMATION"
PHASE_DELIBERATING = "DELIBERATING"
PHASE_PLANNING = "PLANNING"
PHASE_PLAN_ACCEPTED = "PLAN_ACCEPTED"
PHASE_MATERIALIZED = "MATERIALIZED"
PHASE_WAITING_FOR_CAPABILITY = "WAITING_FOR_CAPABILITY"
PHASE_READY_TO_DISPATCH = "READY_TO_DISPATCH"
PHASE_DISPATCHED = "DISPATCHED"
PHASE_PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
PHASE_COMPLETED = "COMPLETED"
PHASE_CANCELLED = "CANCELLED"
PHASE_BLOCKED = "BLOCKED"

AUTONOMY_PHASES: frozenset[str] = frozenset(
    {
        PHASE_TEAM_FORMATION,
        PHASE_DELIBERATING,
        PHASE_PLANNING,
        PHASE_PLAN_ACCEPTED,
        PHASE_MATERIALIZED,
        PHASE_WAITING_FOR_CAPABILITY,
        PHASE_READY_TO_DISPATCH,
        PHASE_DISPATCHED,
        PHASE_PARTIALLY_COMPLETED,
        PHASE_COMPLETED,
        PHASE_CANCELLED,
        PHASE_BLOCKED,
    }
)

# --- blocker vocabulary --------------------------------------------------------------------------
#
# Closed, and every member is DERIVABLE from a canonical column. Where a canonical vocabulary
# already exists the blocker code IS that value -- `capability_unavailable` and
# `requires_human_approval` are `plan_execution_units.unavailable_reason` verbatim -- so a reader
# comparing a blocker against the row it came from sees the same word, not a translation of it.

BLOCKER_CANCELLED_LINEAGE = "cancelled_lineage"
BLOCKER_DISCUSSION_NOT_CONVERGED = "discussion_not_converged"
BLOCKER_REASONING_IN_PROGRESS = "reasoning_in_progress"
BLOCKER_REASONING_FAILED = "reasoning_failed"
BLOCKER_PLANNER_UNAVAILABLE = "planner_unavailable"
BLOCKER_PLAN_NOT_ACCEPTED = "plan_not_accepted"
BLOCKER_MATERIALIZATION_NOT_STARTED = "materialization_not_started"
BLOCKER_DEPENDENCY_BLOCKED = "dependency_blocked"
BLOCKER_CAPABILITY_UNAVAILABLE = "capability_unavailable"
BLOCKER_REQUIRES_HUMAN_APPROVAL = "requires_human_approval"
BLOCKER_DISPATCH_UNPUBLISHED = "dispatch_unpublished"
BLOCKER_STALE_PLAN = "stale_plan"

BLOCKER_CODES: frozenset[str] = frozenset(
    {
        BLOCKER_CANCELLED_LINEAGE,
        BLOCKER_DISCUSSION_NOT_CONVERGED,
        BLOCKER_REASONING_IN_PROGRESS,
        BLOCKER_REASONING_FAILED,
        BLOCKER_PLANNER_UNAVAILABLE,
        BLOCKER_PLAN_NOT_ACCEPTED,
        BLOCKER_MATERIALIZATION_NOT_STARTED,
        BLOCKER_DEPENDENCY_BLOCKED,
        BLOCKER_CAPABILITY_UNAVAILABLE,
        BLOCKER_REQUIRES_HUMAN_APPROVAL,
        BLOCKER_DISPATCH_UNPUBLISHED,
        BLOCKER_STALE_PLAN,
    }
)

#: `discussion_sessions.stop_reason` values that mean the TEAM could not deliberate, as opposed to
#: the deliberation running out of room. A mapping rather than a rename: the canonical stop_reason
#: travels with the blocker, so the two are never confused for one another.
_STOP_REASON_TO_BLOCKER = {
    "reasoning_provider_failure": BLOCKER_REASONING_FAILED,
    "participant_unavailable": BLOCKER_PLANNER_UNAVAILABLE,
    "insufficient_participants": BLOCKER_PLANNER_UNAVAILABLE,
    "insufficient_capability_coverage": BLOCKER_PLANNER_UNAVAILABLE,
}

# --- execution-mode truth ------------------------------------------------------------------------

#: What a terminal AT-M3.5 unit actually is. AT-M4 is not authorized, the delegation namespace has
#: no consumer, and `record_internal_result` is an internal scheduler seam with no public route --
#: so every completion this surface can see was produced inside the control plane. Calling one
#: "agent execution completed" would be the most misleading thing this read surface could say,
#: which is why the field is mandatory on every progress and unit view rather than optional.
EXECUTION_MODE_INTERNAL = "internal_control_plane_simulation"

#: What a published dispatch actually proves.
DISPATCH_STATE_NOT_DISPATCHED = "NOT_DISPATCHED"
DISPATCH_STATE_RECORDED_UNPUBLISHED = "CANONICAL_DISPATCH_RECORDED_UNPUBLISHED"
DISPATCH_STATE_TO_CONTROL_STREAM = "DISPATCHED_TO_CONTROL_STREAM"

#: Stated on every dispatch view, so a UI cannot render "dispatched" as "running" by omission.
DISPATCH_TRUTH_NOTE = (
    "a canonical dispatch and its published_at record that a coordination command was staged on "
    "an isolated control stream that has no consumer; neither is evidence that work executed"
)

_UNIT_TERMINAL = frozenset({"completed", "failed", "cancelled"})
_UNIT_IN_FLIGHT = frozenset({"ready", "assigned", "dispatched"})


def _blocker(
    code: str,
    *,
    entity_type: str,
    entity_id: Any,
    canonical_reason: str | None,
    detail: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One explainable reason the lineage is not moving.

    ``canonical_reason`` is the value AS STORED -- a ``stop_reason``, an ``unavailable_reason``, a
    work-item ``status`` -- and is None only where the blocker is the ABSENCE of a row. There is no
    canonical column that says "materialization has not started", so claiming one would be a
    fiction dressed as evidence.
    """
    return {
        "code": code,
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id else None,
        "canonical_reason": canonical_reason,
        "detail": detail,
        "evidence": evidence or {},
    }


def unit_dispatch_state(unit: dict[str, Any]) -> str:
    """What the transport actually did for this unit. Three answers, none of them "executing"."""
    dispatch = unit.get("dispatch")
    if not dispatch:
        return DISPATCH_STATE_NOT_DISPATCHED
    if dispatch.get("published_at") is None:
        return DISPATCH_STATE_RECORDED_UNPUBLISHED
    return DISPATCH_STATE_TO_CONTROL_STREAM


def unit_has_been_routed(unit: dict[str, Any]) -> bool:
    """Whether a scheduling pass has ever tried to give this unit an owner.

    Routing leaves exactly two marks: a ``routing_decision_id`` when someone eligible was found,
    and an ``unavailable_reason`` when nobody was. Their joint absence is what distinguishes
    "materialized, never scheduled" from "scheduled, and this is the result". The assembled unit
    view carries the answer as ``has_routing_decision`` so this reads one key rather than reaching
    into a nested routing block.
    """
    if "has_routing_decision" in unit:
        return bool(unit["has_routing_decision"]) or bool(unit.get("unavailable_reason"))
    return bool(unit.get("routing_decision_id")) or bool(unit.get("unavailable_reason"))


def graph_progress(units: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts and a completion percentage over ONE graph's units.

    Called with the units of exactly one PlanRevision, never with a Goal's whole unit history: a
    superseded revision's finished work is real, is reported separately as historical, and folding
    it in here would make a replanned Goal look further along than its current plan actually is.

    ``unavailable`` is a SUBSET of ``ready`` -- a unit nobody eligible can take is genuinely ready
    and the TEAM is what is missing -- so the seven state counts sum to ``total_units`` and
    ``unavailable`` deliberately does not participate in that sum.

    THE FORMULA, stated rather than implied::

        completion_percent = round(100 * completed / total_units, 1)

    ``completed`` counts units in state 'completed' and nothing else. A dispatched unit contributes
    ZERO: a staged command is not finished work, and any formula giving it partial credit would
    report progress no canonical row supports. A ``total_units`` of 0 yields None rather than 0.0,
    because "no graph" and "a graph with nothing done" are different facts.
    """
    counts = {
        state: 0
        for state in (
            "blocked",
            "ready",
            "assigned",
            "dispatched",
            "completed",
            "failed",
            "cancelled",
        )
    }
    unavailable = 0
    for unit in units:
        state = unit.get("state")
        if state in counts:
            counts[state] += 1
        if state == "ready" and unit.get("unavailable_reason"):
            unavailable += 1
    total = len(units)
    return {
        "total_units": total,
        **counts,
        "unavailable": unavailable,
        "completion_percent": (round(100.0 * counts["completed"] / total, 1) if total else None),
        "completion_percent_formula": "round(100 * completed / total_units, 1)",
        "execution_mode": EXECUTION_MODE_INTERNAL,
    }


def unit_blockers(unit: dict[str, Any], *, plan_is_current: bool) -> list[dict[str, Any]]:
    """Why this one unit is not moving. Empty for a unit that is moving, or already terminal."""
    blockers: list[dict[str, Any]] = []
    unit_id = unit.get("execution_unit_id")
    evidence = {
        "execution_unit_id": str(unit_id) if unit_id else None,
        "plan_revision_id": (
            str(unit["plan_revision_id"]) if unit.get("plan_revision_id") else None
        ),
        "step_key": unit.get("step_key"),
        "work_item_id": str(unit["work_item_id"]) if unit.get("work_item_id") else None,
    }
    state = unit.get("state")

    if state == "blocked":
        waiting = [
            edge["depends_on_step_key"]
            for edge in unit.get("depends_on", [])
            if edge.get("state") != "completed"
        ]
        blockers.append(
            _blocker(
                BLOCKER_DEPENDENCY_BLOCKED,
                entity_type="execution_unit",
                entity_id=unit_id,
                canonical_reason="blocked",
                detail=(
                    f"step {unit.get('step_key')!r} waits on {len(waiting)} dependency step(s) "
                    "that have not completed"
                ),
                evidence={**evidence, "waiting_on_step_keys": waiting},
            )
        )

    reason = unit.get("unavailable_reason")
    if reason:
        code = (
            reason
            if reason in (BLOCKER_CAPABILITY_UNAVAILABLE, BLOCKER_REQUIRES_HUMAN_APPROVAL)
            else BLOCKER_CAPABILITY_UNAVAILABLE
        )
        blockers.append(
            _blocker(
                code,
                entity_type="execution_unit",
                entity_id=unit_id,
                canonical_reason=reason,
                detail=(
                    f"step {unit.get('step_key')!r} is ready and has no owner: "
                    f"plan_execution_units.unavailable_reason = {reason!r}"
                ),
                evidence={
                    **evidence,
                    "required_capabilities": list(unit.get("required_capabilities") or []),
                    "routing_decision_id": (
                        str(unit["routing_decision_id"])
                        if unit.get("routing_decision_id")
                        else None
                    ),
                },
            )
        )

    if unit_dispatch_state(unit) == DISPATCH_STATE_RECORDED_UNPUBLISHED:
        dispatch = unit.get("dispatch") or {}
        blockers.append(
            _blocker(
                BLOCKER_DISPATCH_UNPUBLISHED,
                entity_type="plan_execution_dispatch",
                entity_id=unit_id,
                canonical_reason=None,
                detail=(
                    "the canonical dispatch row exists and plan_execution_dispatches.published_at "
                    "is NULL; the transport has not carried it yet"
                ),
                evidence={
                    **evidence,
                    "correlation_id": (
                        str(dispatch["correlation_id"]) if dispatch.get("correlation_id") else None
                    ),
                },
            )
        )

    if not plan_is_current and state not in _UNIT_TERMINAL:
        blockers.append(
            _blocker(
                BLOCKER_STALE_PLAN,
                entity_type="plan_revision",
                entity_id=unit.get("plan_revision_id"),
                canonical_reason=None,
                detail=(
                    "a successor PlanRevision exists, so this revision authorizes no NEW dispatch; "
                    "work it already dispatched stays historically valid"
                ),
                evidence=evidence,
            )
        )
    return blockers


def goal_blockers(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Every reason this Goal's autonomous lineage is not advancing, most structural first.

    Deterministic: lineage-level facts (cancelled, not converged, not accepted, not materialized)
    precede unit-level ones, and unit-level blockers follow the caller's step_key ordering, so two
    identical reads produce identical lists.
    """
    blockers: list[dict[str, Any]] = []
    lineage = snapshot.get("lineage")
    discussion = snapshot.get("discussion")
    current_revision = snapshot.get("current_revision")
    graph = snapshot.get("current_graph")
    units = snapshot.get("current_units") or []

    if lineage and lineage.get("is_cancelled"):
        blockers.append(
            _blocker(
                BLOCKER_CANCELLED_LINEAGE,
                entity_type="work_item",
                entity_id=lineage.get("primary_work_item_id"),
                canonical_reason=lineage.get("primary_work_item_status"),
                detail=(
                    "the Goal's primary work item is cancelled; AT-M3.5 refuses new work under a "
                    "cancelled execution lineage"
                ),
                evidence={
                    "primary_work_item_id": str(lineage.get("primary_work_item_id")),
                    "lifecycle_state": lineage.get("primary_work_item_lifecycle_state"),
                },
            )
        )

    if discussion:
        state = discussion.get("state")
        stop_reason = discussion.get("stop_reason")
        discussion_id = str(discussion.get("discussion_id"))
        if state == "open" and discussion.get("open_reasoning_count"):
            blockers.append(
                _blocker(
                    BLOCKER_REASONING_IN_PROGRESS,
                    entity_type="discussion",
                    entity_id=discussion_id,
                    canonical_reason="started",
                    detail=(
                        f"{discussion['open_reasoning_count']} reasoning invocation(s) on this "
                        "discussion's thread are still in status 'started'"
                    ),
                    evidence={"discussion_id": discussion_id},
                )
            )
        if state not in ("open", "converged"):
            blockers.append(
                _blocker(
                    _STOP_REASON_TO_BLOCKER.get(stop_reason, BLOCKER_DISCUSSION_NOT_CONVERGED),
                    entity_type="discussion",
                    entity_id=discussion_id,
                    canonical_reason=stop_reason,
                    detail=(
                        f"discussion ended in state {state!r} with stop_reason {stop_reason!r} "
                        "and produced no convergence"
                    ),
                    evidence={"discussion_id": discussion_id, "state": state},
                )
            )
        elif (
            state == "converged"
            and snapshot.get("planning_decision") is None
            and current_revision is None
        ):
            blockers.append(
                _blocker(
                    BLOCKER_PLAN_NOT_ACCEPTED,
                    entity_type="discussion",
                    entity_id=discussion_id,
                    canonical_reason=stop_reason,
                    detail=(
                        "the discussion converged and no planning decision and no PlanRevision "
                        "record its outcome"
                    ),
                    evidence={"discussion_id": discussion_id},
                )
            )

    if current_revision is not None and current_revision.get("status") != "accepted":
        blockers.append(
            _blocker(
                BLOCKER_PLAN_NOT_ACCEPTED,
                entity_type="plan_revision",
                entity_id=current_revision.get("plan_revision_id"),
                canonical_reason=current_revision.get("status"),
                detail=(
                    f"the current PlanRevision is {current_revision.get('status')!r}; only an "
                    "accepted revision may be materialized"
                ),
                evidence={"revision_number": current_revision.get("revision_number")},
            )
        )
    elif current_revision is not None and graph is None:
        blockers.append(
            _blocker(
                BLOCKER_MATERIALIZATION_NOT_STARTED,
                entity_type="plan_revision",
                entity_id=current_revision.get("plan_revision_id"),
                canonical_reason=None,
                detail=(
                    "the current PlanRevision is accepted and has no plan_execution_graphs row; "
                    "nothing has materialized it yet"
                ),
                evidence={"revision_number": current_revision.get("revision_number")},
            )
        )

    for unit in units:
        # An assembled unit view already carries its own blockers, computed against the raw row
        # while every column was still in scope. Reusing them avoids deriving the same answer from
        # a narrower input and getting a thinner one.
        existing = unit.get("blockers")
        blockers.extend(
            existing if existing is not None else unit_blockers(unit, plan_is_current=True)
        )
    return blockers


def autonomy_phase(snapshot: dict[str, Any]) -> dict[str, Any]:
    """The one derived label for what this team is doing right now, and why that label.

    DETERMINISTIC PRECEDENCE, first match wins. Every rule reads canonical rows only::

        1   CANCELLED               the Goal's primary work item is cancelled or archived
        2   TEAM_FORMATION          the project has no active team membership
        3   TEAM_FORMATION          a team exists and no discussion was opened for this Goal
        4   DELIBERATING            the latest discussion is state='open'
        5   BLOCKED                 the latest discussion is terminal, did not converge, and the
                                    Goal has no PlanRevision to fall back on
        6   PLANNING                a discussion converged and no PlanRevision exists yet
        7   BLOCKED                 the current PlanRevision is not accepted
        8   PLAN_ACCEPTED           the current accepted revision has no execution graph
        9   COMPLETED               every unit of the current graph is 'completed'
        10  PARTIALLY_COMPLETED     at least one unit is completed or failed, and work remains
        11  MATERIALIZED            no unit has been routed yet -- the graph exists and no
                                    scheduling pass has touched it
        12  DISPATCHED              at least one unit is 'dispatched'
        13  READY_TO_DISPATCH       at least one unit is 'assigned', or ready with an owner
        14  WAITING_FOR_CAPABILITY  at least one ready unit carries an unavailable_reason
        15  BLOCKED                 nothing above matched: the graph has been scheduled, nothing
                                    has finished, and no unit is ready, assigned or dispatched

    Rules 9-15 read the CURRENT revision's graph only. A superseded revision's graph is reported
    separately as historical and never decides the current phase.

    MATERIALIZED at rule 11 means "materialized and not yet scheduled", derived from the absence of
    any routing evidence on any unit. It deliberately does NOT mean "every unit is blocked": a
    validated plan is a DAG, so it always has a root step, and materialization leaves that root
    ``ready`` -- a graph in which every unit is blocked from the start is not a state AT-M3.5 can
    produce. BLOCKED is the fall-through at rule 15 instead, which is the honest answer when a
    scheduled graph has nothing in flight and nothing finished.

    Ambiguity is reported, never hidden: the answer always carries the ``reason`` that selected it
    and the ``blocker_codes`` that apply at the same time, so "DISPATCHED, and one step nobody can
    take" stays legible instead of collapsing into a single word.
    """
    blockers = goal_blockers(snapshot)
    codes = sorted({b["code"] for b in blockers})

    def answer(phase: str, reason: str) -> dict[str, Any]:
        return {
            "phase": phase,
            "reason": reason,
            "blocker_codes": codes,
            "is_derived": True,
            "authority": (
                "derived at read time from canonical rows; AT-M3.6A persists no phase and no "
                "lifecycle state"
            ),
        }

    lineage = snapshot.get("lineage")
    if lineage and lineage.get("is_cancelled"):
        return answer(PHASE_CANCELLED, "the Goal's primary work item is cancelled")

    if not snapshot.get("team_active_member_count"):
        return answer(PHASE_TEAM_FORMATION, "the project has no active team membership")

    discussion = snapshot.get("discussion")
    current_revision = snapshot.get("current_revision")
    if discussion is None:
        return answer(
            PHASE_TEAM_FORMATION, "a team exists and no discussion has been opened for this Goal"
        )
    if discussion.get("state") == "open":
        return answer(
            PHASE_DELIBERATING,
            f"discussion {discussion['discussion_id']} is open at round "
            f"{discussion.get('current_round')}",
        )
    if discussion.get("state") != "converged" and current_revision is None:
        return answer(
            PHASE_BLOCKED,
            f"the discussion ended {discussion.get('state')!r} "
            f"({discussion.get('stop_reason')!r}) and the Goal has no PlanRevision",
        )
    if current_revision is None:
        return answer(PHASE_PLANNING, "a discussion converged and no PlanRevision exists yet")
    if current_revision.get("status") != "accepted":
        return answer(
            PHASE_BLOCKED,
            f"the current PlanRevision is {current_revision.get('status')!r}, not accepted",
        )

    if snapshot.get("current_graph") is None:
        return answer(
            PHASE_PLAN_ACCEPTED,
            "the current PlanRevision is accepted and has not been materialized",
        )

    units = snapshot.get("current_units") or []
    states = [u.get("state") for u in units]
    if units and all(state == "completed" for state in states):
        return answer(PHASE_COMPLETED, "every unit of the current execution graph is completed")
    finished = sum(1 for state in states if state in ("completed", "failed"))
    if finished:
        return answer(
            PHASE_PARTIALLY_COMPLETED,
            f"{finished} of {len(units)} unit(s) of the current graph reached a terminal state",
        )
    if not any(unit_has_been_routed(u) for u in units):
        return answer(
            PHASE_MATERIALIZED,
            "the graph is materialized and no unit has been routed yet",
        )
    if "dispatched" in states:
        return answer(
            PHASE_DISPATCHED,
            f"{states.count('dispatched')} unit(s) are dispatched to the control stream, which "
            "has no execution consumer",
        )
    assignable = [
        u
        for u in units
        if u.get("state") == "assigned"
        or (u.get("state") == "ready" and not u.get("unavailable_reason"))
    ]
    if assignable:
        return answer(
            PHASE_READY_TO_DISPATCH,
            f"{len(assignable)} unit(s) are ready or assigned and owe a dispatch",
        )
    if any(u.get("state") == "ready" and u.get("unavailable_reason") for u in units):
        return answer(
            PHASE_WAITING_FOR_CAPABILITY,
            "every ready unit carries an unavailable_reason: the team cannot take the work",
        )
    return answer(
        PHASE_BLOCKED,
        "the graph has been scheduled, nothing has finished, and no unit is ready, assigned or "
        "dispatched, so it cannot advance on its own",
    )


def next_ready_work(units: list[dict[str, Any]]) -> dict[str, Any]:
    """What COULD happen next, as data. Reading it dispatches nothing and schedules nothing.

    Four lists rather than one, because "a scheduler pass would dispatch this", "a pass would find
    nobody to give this to", "the transport still owes this a publish" and "this waits on another
    step" are four different operator answers, and flattening them loses the difference.
    """

    def ident(unit: dict[str, Any]) -> dict[str, Any]:
        return {
            "execution_unit_id": str(unit["execution_unit_id"]),
            "step_key": unit["step_key"],
            "work_item_id": str(unit["work_item_id"]),
            "required_capabilities": list(unit.get("required_capabilities") or []),
        }

    return {
        "ready_units": [
            ident(u)
            for u in units
            if u.get("state") in ("ready", "assigned") and not u.get("unavailable_reason")
        ],
        "capability_unavailable_units": [
            {**ident(u), "unavailable_reason": u["unavailable_reason"]}
            for u in units
            if u.get("state") == "ready" and u.get("unavailable_reason")
        ],
        "unpublished_dispatch_units": [
            {
                **ident(u),
                "correlation_id": str((u.get("dispatch") or {}).get("correlation_id") or "")
                or None,
            }
            for u in units
            if unit_dispatch_state(u) == DISPATCH_STATE_RECORDED_UNPUBLISHED
        ],
        "dependency_blocked_units": [
            {
                **ident(u),
                "waiting_on_step_keys": [
                    e["depends_on_step_key"]
                    for e in u.get("depends_on", [])
                    if e.get("state") != "completed"
                ],
            }
            for u in units
            if u.get("state") == "blocked"
        ],
        "note": (
            "a read-only projection of what a scheduler pass would find; AT-M3.6A never calls the "
            "scheduler and never dispatches"
        ),
    }


__all__ = [
    "AUTONOMY_PHASES",
    "BLOCKER_CODES",
    "DISPATCH_STATE_NOT_DISPATCHED",
    "DISPATCH_STATE_RECORDED_UNPUBLISHED",
    "DISPATCH_STATE_TO_CONTROL_STREAM",
    "DISPATCH_TRUTH_NOTE",
    "EXECUTION_MODE_INTERNAL",
    "autonomy_phase",
    "goal_blockers",
    "graph_progress",
    "next_ready_work",
    "unit_blockers",
    "unit_dispatch_state",
    "unit_has_been_routed",
]
