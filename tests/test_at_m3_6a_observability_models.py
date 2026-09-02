"""Step AT-M3.6A -- the derivation rules, tested without a database.

These are the rules a reader will trust without checking: which phase the runtime is in, why it is
in that one, what is blocking it, and what "40% complete" actually counts. They are pure functions
over a snapshot, so they are tested as a decision table rather than through a stack of fixtures --
if the precedence is wrong, that is a wrong answer on a real screen, not a slow test.
"""

from __future__ import annotations

import uuid

from shared.sdk.autonomy_observability import models


def _unit(state: str, **kw) -> dict:
    unit = {
        "execution_unit_id": str(uuid.uuid4()),
        "plan_revision_id": str(uuid.uuid4()),
        "work_item_id": str(uuid.uuid4()),
        "step_key": kw.pop("step_key", "s"),
        "state": state,
        "required_capabilities": ["generate_code"],
        "unavailable_reason": None,
        "dispatch": None,
        "depends_on": [],
        # Routing leaves one of two marks on a unit. Materialization leaves neither, which is what
        # separates "materialized, never scheduled" from every state a scheduling pass produces.
        "routing_decision_id": None,
    }
    unit.update(kw)
    return unit


def _routed(state: str, **kw) -> dict:
    """A unit a scheduling pass has already touched."""
    return _unit(state, routing_decision_id=str(uuid.uuid4()), **kw)


def _snapshot(**kw) -> dict:
    base = {
        "goal": {"goal_id": str(uuid.uuid4())},
        "lineage": None,
        "team_active_member_count": 3,
        "discussion": None,
        "planning_decision": None,
        "current_revision": None,
        "current_graph": None,
        "current_units": [],
    }
    base.update(kw)
    return base


# --- phase precedence -----------------------------------------------------------------------------


def test_a_cancelled_lineage_outranks_every_other_phase():
    """Rule 1. A cancelled Goal that also has dispatched work is CANCELLED, not DISPATCHED."""
    answer = models.autonomy_phase(
        _snapshot(
            lineage={
                "is_cancelled": True,
                "primary_work_item_id": str(uuid.uuid4()),
                "primary_work_item_status": "cancelled",
                "primary_work_item_lifecycle_state": "cancelled",
            },
            discussion={"discussion_id": "d", "state": "converged", "stop_reason": "x"},
            current_revision={"plan_revision_id": "r", "status": "accepted", "revision_number": 1},
            current_graph={"plan_execution_graph_id": "g"},
            current_units=[_unit("dispatched")],
        )
    )
    assert answer["phase"] == models.PHASE_CANCELLED
    assert models.BLOCKER_CANCELLED_LINEAGE in answer["blocker_codes"]


def test_no_team_and_no_discussion_are_both_team_formation_with_different_reasons():
    """Rules 2 and 3 share a phase and must not share an explanation."""
    no_team = models.autonomy_phase(_snapshot(team_active_member_count=0))
    no_discussion = models.autonomy_phase(_snapshot(team_active_member_count=3))
    assert no_team["phase"] == no_discussion["phase"] == models.PHASE_TEAM_FORMATION
    assert no_team["reason"] != no_discussion["reason"]


def test_an_open_discussion_is_deliberating():
    answer = models.autonomy_phase(
        _snapshot(
            discussion={"discussion_id": "d1", "state": "open", "current_round": 2, "stop_reason": None}
        )
    )
    assert answer["phase"] == models.PHASE_DELIBERATING
    assert "d1" in answer["reason"]


def test_an_exhausted_discussion_with_no_plan_is_blocked_and_says_why():
    answer = models.autonomy_phase(
        _snapshot(
            discussion={
                "discussion_id": "d",
                "state": "exhausted",
                "stop_reason": "round_limit_reached",
            }
        )
    )
    assert answer["phase"] == models.PHASE_BLOCKED
    assert models.BLOCKER_DISCUSSION_NOT_CONVERGED in answer["blocker_codes"]


def test_a_provider_failure_is_reasoning_failed_not_a_generic_non_convergence():
    """The canonical stop_reason decides the blocker code; it is not flattened to one label."""
    answer = models.autonomy_phase(
        _snapshot(
            discussion={
                "discussion_id": "d",
                "state": "failed",
                "stop_reason": "reasoning_provider_failure",
            }
        )
    )
    assert models.BLOCKER_REASONING_FAILED in answer["blocker_codes"]
    blocker = next(b for b in models.goal_blockers(
        _snapshot(discussion={"discussion_id": "d", "state": "failed",
                              "stop_reason": "reasoning_provider_failure"})
    ) if b["code"] == models.BLOCKER_REASONING_FAILED)
    # The stored value travels with the blocker rather than being replaced by the code.
    assert blocker["canonical_reason"] == "reasoning_provider_failure"


def test_an_unseatable_team_is_planner_unavailable():
    for stop_reason in (
        "participant_unavailable",
        "insufficient_participants",
        "insufficient_capability_coverage",
    ):
        answer = models.autonomy_phase(
            _snapshot(
                discussion={"discussion_id": "d", "state": "failed", "stop_reason": stop_reason}
            )
        )
        assert models.BLOCKER_PLANNER_UNAVAILABLE in answer["blocker_codes"], stop_reason


def test_a_converged_discussion_with_no_revision_is_planning():
    answer = models.autonomy_phase(
        _snapshot(
            discussion={
                "discussion_id": "d",
                "state": "converged",
                "stop_reason": "convergence_reached",
            }
        )
    )
    assert answer["phase"] == models.PHASE_PLANNING


def test_a_draft_current_revision_is_blocked_not_plan_accepted():
    """Rule 7. "The Goal has a plan" and "the team accepted a plan" are different facts."""
    answer = models.autonomy_phase(
        _snapshot(
            discussion={"discussion_id": "d", "state": "converged", "stop_reason": "convergence_reached"},
            current_revision={"plan_revision_id": "r", "status": "draft", "revision_number": 1},
        )
    )
    assert answer["phase"] == models.PHASE_BLOCKED
    assert models.BLOCKER_PLAN_NOT_ACCEPTED in answer["blocker_codes"]


def test_an_accepted_unmaterialized_plan_is_plan_accepted_with_a_materialization_blocker():
    snapshot = _snapshot(
        discussion={"discussion_id": "d", "state": "converged", "stop_reason": "convergence_reached"},
        current_revision={"plan_revision_id": "r", "status": "accepted", "revision_number": 1},
    )
    answer = models.autonomy_phase(snapshot)
    assert answer["phase"] == models.PHASE_PLAN_ACCEPTED
    assert models.BLOCKER_MATERIALIZATION_NOT_STARTED in answer["blocker_codes"]
    # No canonical column says "not materialized" -- the absence of a row is the evidence, and the
    # blocker says so rather than inventing a stored reason.
    blocker = next(
        b for b in models.goal_blockers(snapshot)
        if b["code"] == models.BLOCKER_MATERIALIZATION_NOT_STARTED
    )
    assert blocker["canonical_reason"] is None


def _graph_snapshot(units: list[dict]) -> dict:
    return _snapshot(
        discussion={"discussion_id": "d", "state": "converged", "stop_reason": "convergence_reached"},
        current_revision={"plan_revision_id": "r", "status": "accepted", "revision_number": 1},
        current_graph={"plan_execution_graph_id": "g"},
        current_units=units,
    )


def test_a_materialized_but_unscheduled_graph_is_materialized():
    """Rule 11. No unit carries routing evidence, so no scheduling pass has touched this graph.

    MATERIALIZED deliberately does NOT mean "every unit is blocked": a validated plan is a DAG, so
    it always has a root, and materialization leaves that root ``ready``. The distinguishing fact is
    the absence of routing, not the presence of blocking.
    """
    answer = models.autonomy_phase(
        _graph_snapshot([_unit("ready", step_key="a"), _unit("blocked", step_key="b")])
    )
    assert answer["phase"] == models.PHASE_MATERIALIZED


def test_the_scheduled_graph_phases_follow_the_documented_order():
    cases = [
        ([_routed("ready", unavailable_reason="capability_unavailable")],
         models.PHASE_WAITING_FOR_CAPABILITY),
        ([_routed("assigned")], models.PHASE_READY_TO_DISPATCH),
        ([_routed("dispatched", dispatch={"published_at": "t", "correlation_id": "c"})],
         models.PHASE_DISPATCHED),
        ([_routed("completed"), _routed("ready", step_key="b")],
         models.PHASE_PARTIALLY_COMPLETED),
        ([_routed("completed")], models.PHASE_COMPLETED),
    ]
    for units, expected in cases:
        assert models.autonomy_phase(_graph_snapshot(units))["phase"] == expected, expected


def test_one_dispatchable_unit_outranks_a_capability_unavailable_sibling():
    """Ambiguity is reported, not hidden: the phase says work can move, the blocker says one cannot."""
    answer = models.autonomy_phase(
        _graph_snapshot(
            [
                _routed("assigned", step_key="a"),
                _routed("ready", step_key="b", unavailable_reason="capability_unavailable"),
            ]
        )
    )
    assert answer["phase"] == models.PHASE_READY_TO_DISPATCH
    assert models.BLOCKER_CAPABILITY_UNAVAILABLE in answer["blocker_codes"]


def test_a_scheduled_graph_that_cannot_advance_falls_through_to_blocked():
    """Rule 15. Every remaining unit waits on a cancelled dependency -- nothing will ever move."""
    answer = models.autonomy_phase(
        _graph_snapshot(
            [
                _routed("cancelled", step_key="a"),
                _routed(
                    "blocked",
                    step_key="b",
                    depends_on=[{"depends_on_step_key": "a", "state": "cancelled"}],
                ),
            ]
        )
    )
    assert answer["phase"] == models.PHASE_BLOCKED
    assert models.BLOCKER_DEPENDENCY_BLOCKED in answer["blocker_codes"]


def test_every_phase_and_blocker_returned_is_in_the_declared_vocabulary():
    """A label outside the closed set is a contract break a consumer cannot switch on."""
    snapshots = [
        _snapshot(team_active_member_count=0),
        _graph_snapshot([_routed("ready"), _routed("blocked", step_key="b")]),
        _snapshot(
            lineage={
                "is_cancelled": True,
                "primary_work_item_id": "w",
                "primary_work_item_status": "cancelled",
                "primary_work_item_lifecycle_state": "cancelled",
            }
        ),
    ]
    for snapshot in snapshots:
        answer = models.autonomy_phase(snapshot)
        assert answer["phase"] in models.AUTONOMY_PHASES
        assert set(answer["blocker_codes"]) <= models.BLOCKER_CODES
        assert answer["is_derived"] is True


# --- progress -------------------------------------------------------------------------------------


def test_a_dispatched_unit_counts_as_zero_percent_complete():
    """The load-bearing one. A staged command is not finished work, at any percentage."""
    progress = models.graph_progress(
        [
            _unit("dispatched", step_key="a", dispatch={"published_at": "t", "correlation_id": "c"}),
            _unit("dispatched", step_key="b", dispatch={"published_at": "t", "correlation_id": "c"}),
        ]
    )
    assert progress["dispatched"] == 2
    assert progress["completed"] == 0
    assert progress["completion_percent"] == 0.0


def test_the_completion_formula_is_stated_and_matches_the_number():
    progress = models.graph_progress(
        [_unit("completed"), _unit("completed", step_key="b"), _unit("ready", step_key="c")]
    )
    assert progress["completion_percent"] == round(100 * 2 / 3, 1)
    assert progress["completion_percent_formula"] == "round(100 * completed / total_units, 1)"


def test_an_empty_graph_reports_no_percentage_rather_than_zero():
    """"No graph" and "a graph with nothing done" are different facts and must read differently."""
    assert models.graph_progress([])["completion_percent"] is None


def test_unavailable_is_a_subset_of_ready_and_the_state_counts_still_sum():
    units = [
        _unit("ready", step_key="a"),
        _unit("ready", step_key="b", unavailable_reason="capability_unavailable"),
        _unit("blocked", step_key="c"),
    ]
    progress = models.graph_progress(units)
    assert progress["ready"] == 2 and progress["unavailable"] == 1
    states = ("blocked", "ready", "assigned", "dispatched", "completed", "failed", "cancelled")
    assert sum(progress[s] for s in states) == progress["total_units"] == 3


def test_progress_always_states_the_execution_mode():
    """A percentage without this field invites "60% of the work is done by real agents"."""
    assert (
        models.graph_progress([_unit("completed")])["execution_mode"]
        == models.EXECUTION_MODE_INTERNAL
        == "internal_control_plane_simulation"
    )


# --- dispatch truth -------------------------------------------------------------------------------


def test_the_three_dispatch_states_never_include_executing():
    assert models.unit_dispatch_state(_unit("ready")) == models.DISPATCH_STATE_NOT_DISPATCHED
    assert (
        models.unit_dispatch_state(_unit("dispatched", dispatch={"published_at": None}))
        == models.DISPATCH_STATE_RECORDED_UNPUBLISHED
    )
    assert (
        models.unit_dispatch_state(_unit("dispatched", dispatch={"published_at": "t"}))
        == models.DISPATCH_STATE_TO_CONTROL_STREAM
    )
    for state in (
        models.DISPATCH_STATE_NOT_DISPATCHED,
        models.DISPATCH_STATE_RECORDED_UNPUBLISHED,
        models.DISPATCH_STATE_TO_CONTROL_STREAM,
    ):
        assert "EXECUT" not in state.upper().replace("EXECUTION_UNIT", "")


def test_an_unpublished_canonical_dispatch_is_reported_as_a_blocker():
    blockers = models.unit_blockers(
        _unit("dispatched", dispatch={"published_at": None, "correlation_id": "c"}),
        plan_is_current=True,
    )
    assert [b["code"] for b in blockers] == [models.BLOCKER_DISPATCH_UNPUBLISHED]


def test_a_stale_plans_unfinished_unit_carries_a_stale_plan_blocker_and_its_finished_one_does_not():
    """Semantic B: work already done under revision N stays valid; new work is not authorized."""
    unfinished = models.unit_blockers(_unit("ready"), plan_is_current=False)
    finished = models.unit_blockers(_unit("completed"), plan_is_current=False)
    assert models.BLOCKER_STALE_PLAN in [b["code"] for b in unfinished]
    assert models.BLOCKER_STALE_PLAN not in [b["code"] for b in finished]


def test_requires_human_approval_is_reported_with_the_canonical_word():
    """The blocker code IS `unavailable_reason`, so a reader is never comparing a translation."""
    blockers = models.unit_blockers(
        _unit("ready", unavailable_reason="requires_human_approval"), plan_is_current=True
    )
    blocker = next(b for b in blockers if b["code"] == models.BLOCKER_REQUIRES_HUMAN_APPROVAL)
    assert blocker["canonical_reason"] == "requires_human_approval"


# --- next work ------------------------------------------------------------------------------------


def test_next_work_separates_the_four_answers_it_could_give():
    units = [
        _unit("ready", step_key="a"),
        _unit("ready", step_key="b", unavailable_reason="capability_unavailable"),
        _unit("dispatched", step_key="c", dispatch={"published_at": None, "correlation_id": "c1"}),
        _unit("blocked", step_key="d", depends_on=[{"depends_on_step_key": "a", "state": "ready"}]),
    ]
    answer = models.next_ready_work(units)
    assert [u["step_key"] for u in answer["ready_units"]] == ["a"]
    assert [u["step_key"] for u in answer["capability_unavailable_units"]] == ["b"]
    assert [u["step_key"] for u in answer["unpublished_dispatch_units"]] == ["c"]
    assert answer["dependency_blocked_units"][0]["waiting_on_step_keys"] == ["a"]


def test_the_same_snapshot_always_derives_the_same_answer():
    """Derived state has to be a function of its input, or two operators see two runtimes."""
    snapshot = _graph_snapshot([_routed("ready", step_key="a"), _routed("blocked", step_key="b")])
    assert models.autonomy_phase(snapshot) == models.autonomy_phase(snapshot)
    assert models.goal_blockers(snapshot) == models.goal_blockers(snapshot)
