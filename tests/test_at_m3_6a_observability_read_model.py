"""Step AT-M3.6A -- the read surface against a real PostgreSQL, in every state a team can be in.

What is asserted here is not "the endpoint returns 200". It is that the answer is TRUE in states
where a plausible read model would quietly lie: a superseded plan presented as current, a staged
control-plane message presented as executing work, a mocked completion presented as an agent's,
another Project's unit appearing under this Goal, or historical progress folded into the current
plan's percentage. None of those is provable against a fake, because each is a statement about what
PostgreSQL contains and how it was joined.

Scenario letters map to the slice contract's own list: A no plan, B accepted not materialized,
C blocked+ready, D capability unavailable, E assigned+dispatched, F internal completion,
G dependency progression, H superseded with historical work, I cancelled, J non-convergence,
K planless/partial.
"""

from __future__ import annotations

import pytest

from shared.sdk.autonomy_observability import models
from shared.sdk.autonomy_observability.service import (
    AutonomyObservabilityService,
    EntityNotFound,
    GoalNotFound,
)

from tests.autonomy_observability_fixtures import (
    TWO_STEP_PLAN,
    UNSERVED_PLAN,
    ContestingProvider,
    DirectAuditClient,
    cancel_lineage,
    complete_step,
    goal_only,
    materialized,
    read_store_or_skip,
    scheduled,
    supersede_with,
    units_by_step,
    with_accepted_plan,
    with_discussion,
)


def _service() -> AutonomyObservabilityService:
    return AutonomyObservabilityService()


# --- K / A / B: the partial states that must not be 500s ------------------------------------------


@pytest.mark.asyncio
async def test_k_a_goal_with_a_team_and_nothing_else_reads_truthfully():
    """Scenario K. No discussion, no plan, no graph -- and none of that is an error."""
    await read_store_or_skip()
    case = await goal_only()

    overview = await _service().goal_overview(case["goal_id"])

    assert overview["goal"]["goal_id"] == case["goal_id"]
    assert overview["current_discussion"] is None
    assert overview["current_plan_revision"] is None
    assert overview["current_execution_graph"] is None
    assert overview["execution_lineage"] is None
    assert overview["autonomy_phase"]["phase"] == models.PHASE_TEAM_FORMATION
    assert overview["team"]["active_member_count"] >= 3
    # "No graph" is not "a graph with nothing done".
    assert overview["progress"]["total_units"] == 0
    assert overview["progress"]["completion_percent"] is None


@pytest.mark.asyncio
async def test_a_a_goal_with_a_discussion_and_no_plan_shows_the_deliberation():
    """Scenario A. The team has talked; nothing has been decided into a plan yet."""
    case = await with_discussion()

    overview = await _service().goal_overview(case["goal_id"])
    discussion = overview["current_discussion"]

    assert discussion["discussion_id"] == case["discussion_id"]
    assert discussion["state"] == "converged"
    assert discussion["stop_reason"] == "convergence_reached"
    # Seats in speaking order, each with the capabilities it was selected for and the router's
    # own reason -- the collaboration evidence, not a participant count.
    assert [p["seat_index"] for p in discussion["participants"]] == [0, 1, 2]
    assert all(p["matched_capabilities"] for p in discussion["participants"])
    assert all(p["selection_reason"] for p in discussion["participants"])
    assert discussion["result_message_id"] is not None
    assert overview["current_plan_revision"] is None
    assert overview["autonomy_phase"]["phase"] == models.PHASE_PLANNING


@pytest.mark.asyncio
async def test_j_a_discussion_that_never_converged_is_blocked_with_its_canonical_stop_reason():
    """Scenario J. The honest "the team did not agree" state, reported rather than smoothed over."""
    case = await with_discussion(provider=ContestingProvider(), converge=False)

    overview = await _service().goal_overview(case["goal_id"])

    assert overview["current_discussion"]["state"] == "exhausted"
    assert overview["autonomy_phase"]["phase"] == models.PHASE_BLOCKED
    blocker = next(
        b for b in overview["blockers"] if b["code"] == models.BLOCKER_DISCUSSION_NOT_CONVERGED
    )
    assert blocker["canonical_reason"] == overview["current_discussion"]["stop_reason"]
    assert blocker["entity_id"] == case["discussion_id"]


@pytest.mark.asyncio
async def test_b_an_accepted_plan_with_no_graph_is_plan_accepted_and_names_the_team_decision():
    """Scenario B. The lineage from discussion to TeamDecision to accepted plan, unbroken."""
    case = await with_accepted_plan()

    overview = await _service().goal_overview(case["goal_id"])

    revision = overview["current_plan_revision"]
    assert revision["plan_revision_id"] == case["plan_revision_id"]
    assert revision["is_accepted"] is True and revision["is_current"] is True
    assert revision["is_materialized"] is False
    # The plan's own structured steps travel with it, so a client never parses prose for shape.
    assert isinstance(revision["plan"], dict) and revision["plan"]["steps"]

    decision = overview["current_planning_decision"]
    assert decision["planning_decision_id"] == case["planning_decision_id"]
    assert decision["discussion_id"] == case["discussion_id"]
    assert decision["team_decision"]["team_decision_id"] == case["team_decision_id"]
    assert decision["team_decision"]["selected_option"]
    assert decision["resulting_plan_revision_id"] == case["plan_revision_id"]

    assert overview["autonomy_phase"]["phase"] == models.PHASE_PLAN_ACCEPTED
    assert models.BLOCKER_MATERIALIZATION_NOT_STARTED in overview["autonomy_phase"]["blocker_codes"]


# --- C / G: the graph, its topology and its progression -------------------------------------------


@pytest.mark.asyncio
async def test_c_a_materialized_graph_reports_blocked_and_ready_units_with_real_topology():
    """Scenario C. Dependencies as identifiers, both directions, from the durable DAG."""
    case = await materialized()

    graph = await _service().execution_graph(case["plan_revision_id"])
    by_step = {u["step_key"]: u for u in graph["units"]}

    assert graph["is_current"] is True and graph["lineage_status"] == "CURRENT"
    assert set(by_step) == {"design", "build", "verify"}
    assert by_step["design"]["state"] == "ready"
    assert by_step["build"]["state"] == "blocked"

    # Topology in stable identifiers, so a DAG can be drawn without reading plan text.
    assert [d["step_key"] for d in by_step["build"]["depends_on"]] == ["design"]
    assert [u["step_key"] for u in by_step["design"]["unlocks"]] == ["build"]
    assert by_step["build"]["depends_on"][0]["execution_unit_id"] == (
        by_step["design"]["execution_unit_id"]
    )
    assert by_step["design"]["depends_on"] == []

    # Materialized and never scheduled: no unit carries routing evidence yet.
    assert all(u["has_routing_decision"] is False for u in graph["units"])
    assert graph["progress"]["total_units"] == 3
    assert graph["progress"]["completion_percent"] == 0.0


@pytest.mark.asyncio
async def test_g_completing_a_step_unlocks_its_dependent_and_moves_the_derived_progress():
    """Scenario G. A -> B progression, observed only through canonical state."""
    case = await scheduled()
    await complete_step(case, "design")

    overview = await _service().goal_overview(case["goal_id"])
    by_step = {u["step_key"]: u for u in overview["current_units"]}

    assert by_step["design"]["state"] == "completed"
    assert by_step["build"]["state"] == "ready"
    assert by_step["verify"]["state"] == "blocked"
    assert overview["progress"]["completed"] == 1
    assert overview["progress"]["completion_percent"] == round(100 / 3, 1)
    assert overview["autonomy_phase"]["phase"] == models.PHASE_PARTIALLY_COMPLETED
    # What could happen next, as data. Reading it dispatched nothing.
    assert [u["step_key"] for u in overview["next_work"]["ready_units"]] == ["build"]
    assert [u["step_key"] for u in overview["next_work"]["dependency_blocked_units"]] == ["verify"]


@pytest.mark.asyncio
async def test_f_an_internal_completion_is_never_labelled_a_real_agent_execution():
    """Scenario F. The load-bearing product truth: AT-M4 does not exist, so nothing here ran."""
    case = await scheduled()
    await complete_step(case, "design")

    unit = (await units_by_step(case))["design"]
    view = await _service().execution_unit(str(unit["execution_unit_id"]))

    assert view["state"] == "completed" and view["disposition"] == "succeeded"
    assert view["execution_mode"] == "internal_control_plane_simulation"
    overview = await _service().goal_overview(case["goal_id"])
    assert overview["progress"]["execution_mode"] == "internal_control_plane_simulation"
    # Nothing anywhere in the payload claims execution.
    blob = repr(view).lower()
    assert "real agent execution" not in blob
    assert "executing" not in blob


@pytest.mark.asyncio
async def test_j_a_failed_unit_is_terminal_and_does_not_unlock_what_it_was_blocking():
    """Scenario J, unit half. Only 'completed' satisfies a dependency -- failure is not progress.

    A dependent unlocked by a failed predecessor would be dispatched against outputs that do not
    exist, so the read surface has to show the dependent still blocked and say what it waits on.
    """
    case = await scheduled()
    await complete_step(case, "design", disposition="failed")

    overview = await _service().goal_overview(case["goal_id"])
    by_step = {u["step_key"]: u for u in overview["current_units"]}

    assert by_step["design"]["state"] == "failed"
    assert by_step["design"]["disposition"] == "failed"
    assert by_step["design"]["completed_at"] is not None
    # A failure is still an internal control-plane outcome, not an agent's.
    assert by_step["design"]["execution_mode"] == "internal_control_plane_simulation"

    assert by_step["build"]["state"] == "blocked"
    blocker = next(
        b for b in by_step["build"]["blockers"] if b["code"] == models.BLOCKER_DEPENDENCY_BLOCKED
    )
    assert blocker["evidence"]["waiting_on_step_keys"] == ["design"]

    # Nothing completed, so the current plan is 0% -- a failed step is not partial credit.
    assert overview["progress"]["failed"] == 1
    assert overview["progress"]["completed"] == 0
    assert overview["progress"]["completion_percent"] == 0.0
    assert overview["autonomy_phase"]["phase"] == models.PHASE_PARTIALLY_COMPLETED
    assert "terminal state" in overview["autonomy_phase"]["reason"]


@pytest.mark.asyncio
async def test_a_graph_whose_remaining_work_waits_on_a_failure_is_blocked_not_in_flight():
    """The whole graph has stalled: nothing is ready, assigned or dispatched, and work remains."""
    case = await scheduled(plan=TWO_STEP_PLAN)
    await complete_step(case, "design", disposition="failed")

    overview = await _service().goal_overview(case["goal_id"])
    states = {u["step_key"]: u["state"] for u in overview["current_units"]}

    assert states == {"design": "failed", "build": "blocked"}
    # PARTIALLY_COMPLETED wins on precedence -- something reached a terminal state -- and the
    # dependency blocker is reported alongside it rather than being hidden by the phase.
    assert overview["autonomy_phase"]["phase"] == models.PHASE_PARTIALLY_COMPLETED
    assert models.BLOCKER_DEPENDENCY_BLOCKED in overview["autonomy_phase"]["blocker_codes"]
    assert overview["next_work"]["ready_units"] == []


# --- D: capability unavailability and the approval boundary ----------------------------------------


@pytest.mark.asyncio
async def test_d_a_step_no_one_can_take_is_ready_unassigned_with_an_explainable_reason():
    """Scenario D. The team is what is missing, and the routing evidence says which capability."""
    case = await scheduled(plan=UNSERVED_PLAN)

    overview = await _service().goal_overview(case["goal_id"])
    unit = overview["current_units"][0]

    assert unit["state"] == "ready" and unit["assignment"]["assigned_principal_id"] is None
    assert unit["unavailable_reason"] == models.BLOCKER_CAPABILITY_UNAVAILABLE
    assert overview["autonomy_phase"]["phase"] == models.PHASE_WAITING_FOR_CAPABILITY

    blocker = next(
        b for b in overview["blockers"] if b["code"] == models.BLOCKER_CAPABILITY_UNAVAILABLE
    )
    assert blocker["canonical_reason"] == "capability_unavailable"
    assert blocker["evidence"]["required_capabilities"] == unit["required_capabilities"]

    # "Why was nobody selected" is answerable from the recorded AT-M2 evidence alone.
    routing = unit["routing"]
    assert routing["outcome"] == "no_eligible_agent"
    assert routing["candidates_considered"], "the eligible set must survive with the decision"
    assert any(c["rejected_because"] for c in routing["candidates_considered"])
    assert routing["preferred_role_is_a_filter"] is False


@pytest.mark.asyncio
async def test_the_human_approval_boundary_is_reported_and_never_invented():
    """A step nobody can take is not an approval. The boundary is read, and it stays empty."""
    case = await scheduled(plan=UNSERVED_PLAN)
    unit = (await _service().goal_overview(case["goal_id"]))["current_units"][0]

    assert unit["human_approval"]["referred"] is False
    # AT-M3.5 creates no approval record, so the honest answer is None rather than a fabricated
    # approval state that no canonical row supports.
    assert unit["human_approval"]["approval_record"] is None


# --- E: assignment and dispatch truth --------------------------------------------------------------


@pytest.mark.asyncio
async def test_e_a_dispatched_step_shows_its_canonical_dispatch_and_refuses_to_call_it_execution():
    """Scenario E. published_at is transport, not evidence of work."""
    case = await scheduled()

    graph = await _service().execution_graph(case["plan_revision_id"])
    unit = next(u for u in graph["units"] if u["step_key"] == "design")

    assert unit["state"] == "dispatched"
    assert unit["assignment"]["assigned_principal_id"] is not None
    assert unit["assignment"]["assigned_agent_key"] == "design-review-agent"
    assert unit["routing"]["outcome"] == "selected" and unit["routing"]["reason"]

    dispatch = unit["dispatch"]
    assert dispatch["published_at"] is not None
    # The isolated delegation namespace, never the agent's own live input stream.
    assert dispatch["target_stream"].startswith("stream.plan_delegation.")
    assert dispatch["plan_revision_id"] == case["plan_revision_id"]
    assert dispatch["step_key"] == "design"

    assert unit["dispatch_state"] == models.DISPATCH_STATE_TO_CONTROL_STREAM
    assert unit["dispatch_state"] != "EXECUTING"
    # The caveat travels with the row, so a UI cannot render "dispatched" as "running" by omission.
    assert unit["dispatch_truth"] == models.DISPATCH_TRUTH_NOTE
    assert "neither is evidence that work executed" in unit["dispatch_truth"]


@pytest.mark.asyncio
async def test_the_selected_stream_and_the_transport_stream_are_reported_as_the_two_facts_they_are():
    """AT-M2 decided WHO and recorded its stream; AT-M3.5 staged the message somewhere isolated."""
    case = await scheduled()
    unit = next(
        u
        for u in (await _service().execution_graph(case["plan_revision_id"]))["units"]
        if u["step_key"] == "design"
    )
    assert unit["routing"]["selected_stream"] == "stream.design_review"
    assert unit["dispatch"]["target_stream"] == "stream.plan_delegation.design-review-agent"


# --- H: the superseded plan and its historical work -----------------------------------------------


@pytest.mark.asyncio
async def test_h_a_superseded_revisions_completed_work_stays_visible_and_stays_historical():
    """Scenario H. The single most important thing this read surface must not get wrong."""
    case = await scheduled()
    await complete_step(case, "design")
    historical_revision = case["plan_revision_id"]
    successor = await supersede_with(case)

    overview = await _service().goal_overview(case["goal_id"])

    # The current plan is the successor, and it has materialized nothing.
    assert overview["current_plan_revision"]["plan_revision_id"] == successor
    assert overview["current_execution_graph"] is None
    # The current plan's progress is ZERO. The predecessor's completed step is real, and counting
    # it here would make a replanned Goal look further along than its current plan is.
    assert overview["progress"]["total_units"] == 0
    assert overview["progress"]["completion_percent"] is None

    # The historical graph is preserved, labelled, and carries its own counts.
    historical = overview["historical_execution_graphs"]
    assert [h["plan_revision_id"] for h in historical] == [historical_revision]
    assert historical[0]["is_current"] is False
    assert historical[0]["state_counts"]["completed"] == 1
    assert historical[0]["published_dispatch_rows"] >= 1


@pytest.mark.asyncio
async def test_h_the_historical_graph_is_still_fully_readable_and_marked_superseded():
    case = await scheduled()
    await complete_step(case, "design")
    historical_revision = case["plan_revision_id"]
    await supersede_with(case)

    graph = await _service().execution_graph(historical_revision)

    assert graph["is_current"] is False
    assert graph["lineage_status"] == "HISTORICAL_SUPERSEDED"
    assert graph["superseded_by_revision_id"] == case["plan_revision_id"]
    by_step = {u["step_key"]: u for u in graph["units"]}
    # Work that finished under N stays finished, with its dispatch bound to N forever.
    assert by_step["design"]["state"] == "completed"
    assert by_step["design"]["dispatch"]["plan_revision_id"] == historical_revision
    assert by_step["design"]["blockers"] == []
    # Unfinished work under a superseded revision is honestly blocked by the supersession.
    assert models.BLOCKER_STALE_PLAN in [b["code"] for b in by_step["build"]["blockers"]]


@pytest.mark.asyncio
async def test_h_revision_history_shows_every_revision_and_what_each_one_dispatched():
    case = await scheduled()
    await complete_step(case, "design")
    historical_revision = case["plan_revision_id"]
    successor = await supersede_with(case)

    history = await _service().plan_revision_history(case["goal_id"])

    ids = [r["plan_revision_id"] for r in history["revisions"]]
    # Revision 1 (the deliberated one), revision 2 (the executable one), revision 3 (the successor).
    assert historical_revision in ids and successor in ids
    assert ids[-1] == successor
    assert history["ordering"] == "revision_number ASC"
    assert [r["is_current"] for r in history["revisions"]].count(True) == 1

    executed = next(r for r in history["revisions"] if r["plan_revision_id"] == historical_revision)
    assert executed["execution"]["state_counts"]["completed"] == 1
    assert executed["execution"]["canonical_dispatch_rows"] >= 1
    assert executed["execution"]["execution_mode"] == "internal_control_plane_simulation"
    # A revision that materialized nothing says so rather than reporting zeros as if it had.
    assert next(r for r in history["revisions"] if r["plan_revision_id"] == successor)[
        "execution"
    ] is None


# --- I: cancellation --------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_i_a_cancelled_lineage_is_reported_from_the_existing_work_item_status():
    """Scenario I. One cancellation model, read -- not a second one invented for observability."""
    case = await scheduled()
    await cancel_lineage(case)

    overview = await _service().goal_overview(case["goal_id"])

    assert overview["execution_lineage"]["is_cancelled"] is True
    assert overview["execution_lineage"]["primary_work_item_status"] == "cancelled"
    assert overview["autonomy_phase"]["phase"] == models.PHASE_CANCELLED
    blocker = next(
        b for b in overview["blockers"] if b["code"] == models.BLOCKER_CANCELLED_LINEAGE
    )
    assert blocker["canonical_reason"] == "cancelled"
    assert blocker["entity_id"] == overview["execution_lineage"]["primary_work_item_id"]


# --- cross-entity invariants ------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_unit_graph_or_dispatch_from_another_project_can_appear_under_this_goal():
    """Two independent Goals, built identically. Neither may leak a single row into the other."""
    a = await scheduled()
    b = await scheduled()

    overview = await _service().goal_overview(a["goal_id"])
    b_units = {str(u["execution_unit_id"]) for u in (await units_by_step(b)).values()}

    assert overview["goal"]["project_id"] == a["project_id"]
    for unit in overview["current_units"]:
        assert unit["goal_id"] == a["goal_id"]
        assert unit["project_id"] == a["project_id"]
        assert unit["plan_revision_id"] == a["plan_revision_id"]
        assert unit["execution_unit_id"] not in b_units
        # Topology never reaches across a revision boundary either.
        for edge in unit["depends_on"] + unit["unlocks"]:
            assert edge["execution_unit_id"] not in b_units
    # An assigned principal must be a member of THIS Goal's project team. A runtime agent
    # principal is deliberately shared across projects -- `design-review-agent` is one identity
    # serving many teams -- so the invariant is membership in this project, not exclusivity of the
    # principal, and asserting exclusivity would be asserting the wrong thing.
    members = {m["principal_id"] for m in overview["team"]["members"]}
    for unit in overview["current_units"]:
        principal = unit["assignment"]["assigned_principal_id"]
        if principal:
            assert principal in members

    other = await _service().goal_overview(b["goal_id"])
    assert other["current_execution_graph"]["plan_execution_graph_id"] != (
        overview["current_execution_graph"]["plan_execution_graph_id"]
    )
    assert other["execution_lineage"]["primary_work_item_id"] != (
        overview["execution_lineage"]["primary_work_item_id"]
    )


@pytest.mark.asyncio
async def test_a_team_decision_is_only_reported_for_the_discussion_that_produced_it():
    a = await with_accepted_plan()
    b = await with_accepted_plan()

    overview = await _service().goal_overview(a["goal_id"])
    decision = overview["current_planning_decision"]

    assert decision["discussion_id"] == a["discussion_id"] != b["discussion_id"]
    assert decision["team_decision"]["team_decision_id"] == a["team_decision_id"]
    assert decision["resulting_plan_revision_id"] == a["plan_revision_id"]


@pytest.mark.asyncio
async def test_every_cross_entity_link_is_a_real_identifier_and_never_a_title_match():
    """No join in this surface may be made by title, description or agent display name."""
    case = await scheduled()
    overview = await _service().goal_overview(case["goal_id"])
    unit = next(u for u in overview["current_units"] if u["step_key"] == "design")

    import uuid as _uuid

    for value in (
        overview["goal"]["goal_id"],
        overview["goal"]["project_id"],
        overview["execution_lineage"]["primary_work_item_id"],
        overview["current_plan_revision"]["plan_revision_id"],
        overview["current_execution_graph"]["plan_execution_graph_id"],
        unit["execution_unit_id"],
        unit["work_item_id"],
        unit["assignment"]["assigned_principal_id"],
        unit["routing"]["routing_decision_id"],
        unit["dispatch"]["correlation_id"],
    ):
        _uuid.UUID(str(value))


# --- unknown identifiers ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_unknown_identifier_is_a_lookup_failure_and_not_a_server_fault():
    await read_store_or_skip()
    import uuid as _uuid

    service = _service()
    with pytest.raises(GoalNotFound):
        await service.goal_overview(str(_uuid.uuid4()))
    with pytest.raises(EntityNotFound):
        await service.execution_graph(str(_uuid.uuid4()))
    with pytest.raises(EntityNotFound):
        await service.execution_unit(str(_uuid.uuid4()))
    with pytest.raises(EntityNotFound):
        await service.discussion_reasoning(str(_uuid.uuid4()))


# --- reasoning safety -------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reasoning_metadata_is_exposed_and_the_artifact_body_is_not():
    """Operational metadata answers "did the model run and how"; the artifact is business state."""
    case = await with_accepted_plan()

    reasoning = await _service().discussion_reasoning(case["discussion_id"])

    assert reasoning["total"] >= 3
    verbs = {i["reasoning_verb"] for i in reasoning["invocations"]}
    assert {"propose", "critique"} <= verbs
    for invocation in reasoning["invocations"]:
        assert invocation["provider_mode"] in ("mock", "disabled")
        assert invocation["status"] in ("started", "succeeded", "failed")
        assert invocation["artifact_body_exposed"] is False
        # The type name is metadata; the object is read through TeamMessage / PlanRevision.
        assert "artifact" not in {k for k in invocation if k not in
                                  ("artifact_type", "artifact_body_exposed")}
    # Scanned over the invocation payloads only. The endpoint's own disclosure sentence names the
    # things it does not expose, and a scan that flagged its own denial would be checking prose.
    # Asserted over the KEYS of each invocation rather than by scanning text: a substring scan
    # trips over `DecisionSummaryArtifact` and would pass for the wrong reason. What must be absent
    # is the field, not the letters.
    forbidden = {
        "artifact",
        "prompt",
        "completion",
        "raw_completion",
        "scratchpad",
        "chain_of_thought",
        "system_instruction",
        "rationale_summary",
        "messages",
        "context",
    }
    for invocation in reasoning["invocations"]:
        assert not (set(invocation) & forbidden), set(invocation) & forbidden


@pytest.mark.asyncio
async def test_a_succeeded_invocation_reports_its_artifact_type_and_its_turn_context():
    case = await with_accepted_plan()
    reasoning = await _service().discussion_reasoning(case["discussion_id"])

    proposal = next(i for i in reasoning["invocations"] if i["reasoning_verb"] == "propose")
    assert proposal["status"] == "succeeded"
    assert proposal["artifact_type"] == "ProposalArtifact"
    assert proposal["attempt"] >= 1
    # Replay context: which slot the attempt belonged to and which message carried its result.
    assert proposal["turn"]["round_index"] >= 1
    assert proposal["turn"]["message_id"] is not None


# --- timeline ----------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_timeline_correlates_every_stage_from_discussion_to_dispatch():
    """The delegation audit events carry no goal_id -- the probe set is what finds them."""
    audit = DirectAuditClient()
    case = await scheduled(audit=audit)

    timeline = await _service().goal_timeline(case["goal_id"], limit=200)
    types = [e["decision_type"] for e in timeline["entries"]]

    for expected in (
        "discussion_opened",
        "discussion_turn_recorded",
        "discussion_closed",
        "planning_decision_recorded",
        "plan_graph_materialized",
        "plan_step_assigned",
        "plan_step_dispatched",
    ):
        assert expected in types, expected
    assert timeline["ordering"] == "created_at ASC, audit_id ASC"
    assert "evidence" in timeline["authority"]
    # Every entry resolves to this Goal's own lineage or contributes no cross-entity claim at all.
    assert all(e["reference_scope_verified"] for e in timeline["entries"])
    assert all(e["goal_id"] == case["goal_id"] for e in timeline["entries"])


@pytest.mark.asyncio
async def test_the_timeline_reports_only_events_that_were_actually_written():
    """No event is synthesised from current state, so a gap in the record stays a gap."""
    case = await scheduled(audit=None)

    timeline = await _service().goal_timeline(case["goal_id"])

    # The lineage genuinely exists and is fully readable, and no audit sink was wired.
    assert timeline["total"] == 0 and timeline["entries"] == []
    overview = await _service().goal_overview(case["goal_id"])
    assert overview["current_execution_graph"] is not None


@pytest.mark.asyncio
async def test_one_goals_timeline_never_contains_another_goals_events():
    audit = DirectAuditClient()
    a = await scheduled(audit=audit)
    b = await scheduled(audit=audit)

    a_timeline = await _service().goal_timeline(a["goal_id"], limit=200)
    b_ids = {a["plan_revision_id"] for a in [b]} | {b["discussion_id"]}

    for entry in a_timeline["entries"]:
        assert entry["plan_revision_id"] not in b_ids
        assert entry["discussion_id"] not in b_ids


# --- pagination ---------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_collection_is_bounded_and_pages_deterministically():
    audit = DirectAuditClient()
    case = await scheduled(audit=audit)

    first = await _service().execution_graph(case["plan_revision_id"], limit=1, offset=0)
    second = await _service().execution_graph(case["plan_revision_id"], limit=1, offset=1)
    assert first["total_units"] == 3 and first["has_more"] is True
    assert len(first["units"]) == 1 and len(second["units"]) == 1
    assert first["units"][0]["step_key"] != second["units"][0]["step_key"]
    # Deterministic order: the same page twice is the same page.
    again = await _service().execution_graph(case["plan_revision_id"], limit=1, offset=0)
    assert again["units"][0]["execution_unit_id"] == first["units"][0]["execution_unit_id"]

    timeline = await _service().goal_timeline(case["goal_id"], limit=2)
    assert len(timeline["entries"]) <= 2 and timeline["has_more"] is True
    page2 = await _service().goal_timeline(case["goal_id"], limit=2, offset=2)
    assert {e["audit_id"] for e in timeline["entries"]} & {
        e["audit_id"] for e in page2["entries"]
    } == set()


@pytest.mark.asyncio
async def test_an_absurd_limit_is_capped_rather_than_honoured():
    """No caller can turn a bounded read into "return every event ever" by asking nicely."""
    case = await with_accepted_plan()
    timeline = await _service().goal_timeline(case["goal_id"], limit=10_000)
    assert timeline["limit"] == 500
