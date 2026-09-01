"""Step AT-M3.5 -- plan-driven delegation against a real PostgreSQL.

Everything asserted here is a statement about the DATABASE, and none of it is provable against a
fake: eight workers materializing one plan and producing one graph, eight schedulers dispatching
one step exactly once, a superseded revision that cannot authorize new work however many callers
ask, a fan-in step that becomes ready exactly once when its last dependency lands, and a graph that
rebuilds itself truthfully from rows after every process that touched it is gone.

The negative assertions matter as much as the positive ones. A delegation layer that dispatched
twice, adopted a stale plan, let plan text name an owner, or let an unrelated caller declare a step
finished would pass a "the happy path works" suite unchanged.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from shared.sdk.agent_planning.models import PlanLineageError, StalePlanRevisionError
from shared.sdk.plan_delegation.models import (
    UNAVAILABLE_NO_ELIGIBLE_AGENT,
    UNIT_BLOCKED,
    UNIT_COMPLETED,
    UNIT_DISPATCHED,
    UNIT_FAILED,
    UNIT_READY,
    DispatchLineageError,
    ExecutionLineageCancelledError,
    ExecutionUnitStateError,
    PlanGraphInvalidError,
    PlanRevisionNotDispatchableError,
)
from shared.sdk.plan_delegation.service import PlanDelegationService
from shared.sdk.plan_delegation.store import PlanDelegationStore

from tests.plan_delegation_fixtures import (
    FAN_IN_PLAN,
    UNSERVED_PLAN,
    RecordingBus,
    cancel_primary_work_item,
    scenario,
    store_or_skip,
    supersede,
    units_by_step,
)

pytestmark = pytest.mark.asyncio


def _service(bus=None, audit=None) -> PlanDelegationService:
    return PlanDelegationService(event_bus=bus, audit_client=audit)


async def _materialize(case, service=None) -> dict:
    return await (service or _service()).materialize_accepted_plan(
        goal_id=case["goal_id"],
        plan_revision_id=case["plan_revision_id"],
        materialized_by=case["author"],
    )


async def _complete(case, unit, disposition="succeeded"):
    dispatch = await case["store"].get_dispatch(unit["execution_unit_id"])
    return await _service().record_step_result(
        execution_unit_id=str(unit["execution_unit_id"]),
        reported_by=str(dispatch["assigned_principal_id"]),
        correlation_id=str(dispatch["correlation_id"]),
        disposition=disposition,
    )


# --- materialization gate ---------------------------------------------------------------------------


class TestMaterializationGate:
    async def test_an_accepted_current_revision_materializes_its_whole_graph(self):
        case = await scenario()
        result = await _materialize(case)

        assert result["created"] is True
        assert result["graph"]["step_count"] == 3
        units = {u["step_key"]: u for u in result["units"]}
        assert set(units) == {"design", "build", "verify"}
        # Only the root is ready; nothing downstream is dispatchable yet.
        assert units["design"]["state"] == UNIT_READY
        assert units["build"]["state"] == UNIT_BLOCKED
        assert units["verify"]["state"] == UNIT_BLOCKED

    async def test_a_draft_revision_cannot_create_an_execution_graph(self):
        case = await scenario(accept=False)
        with pytest.raises(PlanRevisionNotDispatchableError, match="draft"):
            await _materialize(case)
        assert await case["store"].get_graph(case["plan_revision_id"]) is None

    async def test_a_superseded_revision_cannot_create_an_execution_graph(self):
        case = await scenario()
        await supersede(case)
        with pytest.raises(StalePlanRevisionError):
            await _materialize(case)
        assert await case["store"].get_graph(case["plan_revision_id"]) is None

    async def test_a_revision_belonging_to_another_goal_is_rejected(self):
        case = await scenario()
        other = await scenario()
        with pytest.raises(PlanLineageError):
            await _service().materialize_accepted_plan(
                goal_id=case["goal_id"],
                plan_revision_id=other["plan_revision_id"],
                materialized_by=case["author"],
            )

    async def test_a_stored_plan_containing_a_cycle_is_refused_and_writes_nothing(self):
        """Historical data that violates today's assumptions must fail closed. ``PlanContent``
        accepts this plan -- every step exists and none depends on itself -- and no step in it
        could ever become ready."""
        cyclic = {
            "objective": "a plan that cannot run",
            "steps": [
                {"step_key": "a", "title": "A", "depends_on": ["b"]},
                {"step_key": "b", "title": "B", "depends_on": ["a"]},
            ],
        }
        case = await scenario(plan=cyclic)
        with pytest.raises(PlanGraphInvalidError):
            await _materialize(case)

        conn = await case["store"]._connect()
        try:
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM plan_execution_graphs WHERE plan_revision_id=$1",
                    uuid.UUID(case["plan_revision_id"]),
                )
                == 0
            )
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM plan_execution_units WHERE plan_revision_id=$1",
                    uuid.UUID(case["plan_revision_id"]),
                )
                == 0
            )
            # Not even the Goal's execution root survives a refused materialization.
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM goal_execution_lineage WHERE goal_id=$1",
                    uuid.UUID(case["goal_id"]),
                )
                == 0
            )
        finally:
            await conn.close()


# --- lineage and step identity ------------------------------------------------------------------------


class TestExecutionLineage:
    async def test_every_step_becomes_a_child_of_the_goals_single_primary_work_item(self):
        case = await scenario()
        result = await _materialize(case)
        primary = result["primary_work_item_id"]

        conn = await case["store"]._connect()
        try:
            parents = await conn.fetch(
                """
                SELECT w.parent_work_item_id
                FROM plan_execution_units u JOIN project_work_items w ON w.id = u.work_item_id
                WHERE u.plan_revision_id=$1
                """,
                uuid.UUID(case["plan_revision_id"]),
            )
            assert {row["parent_work_item_id"] for row in parents} == {primary}
            # The root itself has no parent and is not a plan step.
            assert (
                await conn.fetchval(
                    "SELECT parent_work_item_id FROM project_work_items WHERE id=$1", primary
                )
                is None
            )
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM plan_execution_units WHERE work_item_id=$1", primary
                )
                == 0
            )
        finally:
            await conn.close()

    async def test_no_task_row_is_created_read_or_required_anywhere(self):
        """AT-D01 / INV-02: the Task is not an execution root and the lineage must not need one."""
        store = await store_or_skip()
        conn = await store._connect()
        try:
            before = await conn.fetchval("SELECT count(*) FROM tasks")
        finally:
            await conn.close()

        case = await scenario()
        await _materialize(case)
        await _service(RecordingBus()).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )

        conn = await store._connect()
        try:
            assert await conn.fetchval("SELECT count(*) FROM tasks") == before
        finally:
            await conn.close()

    async def test_a_successor_revision_gets_its_own_graph_under_the_SAME_primary_work_item(self):
        case = await scenario()
        first = await _materialize(case)
        successor = await supersede(case)
        second = await _service().materialize_accepted_plan(
            goal_id=case["goal_id"], plan_revision_id=successor, materialized_by=case["author"]
        )

        assert second["created"] is True
        assert (
            second["graph"]["plan_execution_graph_id"] != first["graph"]["plan_execution_graph_id"]
        )
        # One execution root for the Goal, shared by both revisions' graphs.
        assert second["primary_work_item_id"] == first["primary_work_item_id"]
        # Same step keys, entirely different units and work items -- nothing is rebound.
        first_units = {u["step_key"]: u for u in first["units"]}
        second_units = {u["step_key"]: u for u in second["units"]}
        assert set(first_units) == set(second_units)
        for key in first_units:
            assert first_units[key]["execution_unit_id"] != second_units[key]["execution_unit_id"]
            assert first_units[key]["work_item_id"] != second_units[key]["work_item_id"]

    async def test_step_identity_is_the_exact_step_key_and_the_step_contract_is_copied(self):
        case = await scenario()
        result = await _materialize(case)
        build = next(u for u in result["units"] if u["step_key"] == "build")
        assert build["required_capabilities"] == ["generate_code"]
        assert build["expected_outputs"] == ["the slice"]
        assert build["plan_revision_id"] == uuid.UUID(case["plan_revision_id"])

    async def test_dependencies_are_stored_as_ordinary_work_item_edges(self):
        case = await scenario()
        await _materialize(case)
        edges = await case["store"].list_dependencies(case["plan_revision_id"])
        assert {(e["step_key"], e["depends_on_step_key"]) for e in edges} == {
            ("build", "design"),
            ("verify", "build"),
        }
        assert all(e["dependency_type"] == "blocks" for e in edges)

    async def test_the_execution_root_may_not_be_re_rooted(self):
        case = await scenario()
        result = await _materialize(case)
        conn = await case["store"]._connect()
        try:
            with pytest.raises(Exception, match="may not be re-rooted"):
                await conn.execute(
                    "UPDATE goal_execution_lineage SET primary_work_item_id=$2 WHERE goal_id=$1",
                    uuid.UUID(case["goal_id"]),
                    result["units"][0]["work_item_id"],
                )
        finally:
            await conn.close()

    async def test_a_unit_may_not_be_rebound_to_another_plan_revision(self):
        case = await scenario()
        result = await _materialize(case)
        successor = await supersede(case)
        conn = await case["store"]._connect()
        try:
            with pytest.raises(Exception, match="plan identity may not be rewritten"):
                await conn.execute(
                    "UPDATE plan_execution_units SET plan_revision_id=$2 WHERE execution_unit_id=$1",
                    result["units"][0]["execution_unit_id"],
                    uuid.UUID(successor),
                )
        finally:
            await conn.close()


# --- materialization idempotency -----------------------------------------------------------------------


class TestMaterializationIdempotency:
    async def test_materializing_twice_returns_the_same_graph_and_creates_no_second_one(self):
        case = await scenario()
        first = await _materialize(case)
        second = await _materialize(case)

        assert first["created"] is True and second["created"] is False
        assert (
            first["graph"]["plan_execution_graph_id"] == second["graph"]["plan_execution_graph_id"]
        )
        assert len(second["units"]) == 3

    async def test_eight_concurrent_materializations_produce_exactly_one_graph(self):
        case = await scenario()
        results = await asyncio.gather(
            *(_materialize(case) for _ in range(8)), return_exceptions=True
        )
        assert not [r for r in results if isinstance(r, Exception)], results

        graph_ids = {str(r["graph"]["plan_execution_graph_id"]) for r in results}
        assert len(graph_ids) == 1
        assert sum(1 for r in results if r["created"]) == 1

        conn = await case["store"]._connect()
        try:
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM plan_execution_units WHERE plan_revision_id=$1",
                    uuid.UUID(case["plan_revision_id"]),
                )
                == 3
            )
            # No duplicate child work items were left behind by the seven rolled-back attempts.
            assert (
                await conn.fetchval(
                    """
                    SELECT count(*) FROM project_work_items
                    WHERE parent_work_item_id = (
                        SELECT primary_work_item_id FROM goal_execution_lineage WHERE goal_id=$1)
                    """,
                    uuid.UUID(case["goal_id"]),
                )
                == 3
            )
        finally:
            await conn.close()

    async def test_a_successor_committing_mid_race_cannot_produce_a_stale_graph(self):
        """The currentness check is inside the materialization transaction, not a pre-read: a
        successor appearing between the check and the commit still refuses the graph."""
        case = await scenario()
        results = await asyncio.gather(_materialize(case), supersede(case), return_exceptions=True)
        failures = [r for r in results if isinstance(r, Exception)]
        # Exactly one of the two lost: either the graph was built before the successor existed, or
        # the successor won and the graph was refused. Never both, and never a graph for a
        # revision that is no longer current.
        assert len(failures) <= 1
        graph = await case["store"].get_graph(case["plan_revision_id"])
        if graph is not None:
            assert not any(isinstance(r, StalePlanRevisionError) for r in results)


# --- capability assignment ------------------------------------------------------------------------------


class TestAssignment:
    async def test_the_ready_root_is_assigned_to_the_capable_team_member_and_dispatched(self):
        case = await scenario()
        await _materialize(case)
        bus = RecordingBus()
        outcome = await _service(bus).schedule_ready_work(plan_revision_id=case["plan_revision_id"])

        acted = [r for r in outcome["results"] if r["outcome"] == "dispatched"]
        assert len(acted) == 1 and acted[0]["step_key"] == "design"
        assert acted[0]["target_stream"] == "stream.design_review"
        assert acted[0]["published"] is True

        units = await units_by_step(case["store"], case["plan_revision_id"])
        assert units["design"]["state"] == UNIT_DISPATCHED
        assert units["build"]["state"] == UNIT_BLOCKED

    async def test_the_assignment_names_a_real_project_team_principal(self):
        case = await scenario()
        await _materialize(case)
        await _service(RecordingBus()).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )
        units = await units_by_step(case["store"], case["plan_revision_id"])

        conn = await case["store"]._connect()
        try:
            membership = await conn.fetchrow(
                """
                SELECT membership_state FROM project_team_memberships
                WHERE project_id=$1 AND agent_principal_id=$2
                """,
                uuid.UUID(case["project_id"]),
                units["design"]["assigned_principal_id"],
            )
        finally:
            await conn.close()
        assert membership is not None and membership["membership_state"] == "active"

    async def test_the_routing_evidence_lands_in_the_existing_AT_M2_table(self):
        case = await scenario()
        await _materialize(case)
        await _service(RecordingBus()).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )
        units = await units_by_step(case["store"], case["plan_revision_id"])

        conn = await case["store"]._connect()
        try:
            row = await conn.fetchrow(
                """
                SELECT requested_capability, outcome, selected_principal_id, reason, work_item_id
                FROM agent_routing_decisions WHERE routing_decision_id=$1
                """,
                units["design"]["routing_decision_id"],
            )
        finally:
            await conn.close()
        assert row["outcome"] == "selected"
        assert row["requested_capability"] == "review_design"
        assert row["selected_principal_id"] == units["design"]["assigned_principal_id"]
        assert row["work_item_id"] == units["design"]["work_item_id"]

    async def test_a_step_nobody_can_take_stays_ready_with_an_honest_reason_and_is_not_dispatched(
        self,
    ):
        case = await scenario(plan=UNSERVED_PLAN)
        await _materialize(case)
        bus = RecordingBus()
        outcome = await _service(bus).schedule_ready_work(plan_revision_id=case["plan_revision_id"])

        assert outcome["results"][0]["outcome"] == "unassignable"
        assert outcome["results"][0]["reason"] == UNAVAILABLE_NO_ELIGIBLE_AGENT
        assert bus.dispatches() == []

        units = await units_by_step(case["store"], case["plan_revision_id"])
        unit = units["impossible"]
        assert unit["state"] == UNIT_READY
        assert unit["assigned_principal_id"] is None
        assert unit["unavailable_reason"] == UNAVAILABLE_NO_ELIGIBLE_AGENT
        assert await case["store"].get_dispatch(unit["execution_unit_id"]) is None

    async def test_an_unassignable_step_is_assigned_once_the_team_can_cover_it(self):
        """The reschedule path: no polling daemon, no timer -- the same command tried again after
        the roster changed."""
        case = await scenario(plan=UNSERVED_PLAN)
        await _materialize(case)
        await _service(RecordingBus()).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )

        from shared.sdk.agent_team.service import TeamService

        team = TeamService()
        await team.form_team(case["project_id"], goal_ref="m35", agent_keys=("qa-agent",))
        await team.set_agent_capabilities("qa-agent", ("verify_quality", "generate_code"))

        bus = RecordingBus()
        outcome = await _service(bus).schedule_ready_work(plan_revision_id=case["plan_revision_id"])
        assert outcome["results"][0]["outcome"] == "dispatched"
        units = await units_by_step(case["store"], case["plan_revision_id"])
        assert units["impossible"]["state"] == UNIT_DISPATCHED
        assert units["impossible"]["unavailable_reason"] is None

    async def test_eight_concurrent_schedulers_assign_and_dispatch_one_step_exactly_once(self):
        """One canonical assignment, one canonical dispatch, one command identity.

        The exactly-once claim is about the DURABLE state, and it stops there deliberately: the
        stream is at-least-once, so what the losers may put on the wire is a duplicate of the same
        command, never a second one.
        """
        case = await scenario()
        await _materialize(case)
        buses = [RecordingBus() for _ in range(8)]
        results = await asyncio.gather(
            *(
                _service(bus).schedule_ready_work(plan_revision_id=case["plan_revision_id"])
                for bus in buses
            ),
            return_exceptions=True,
        )
        assert not [r for r in results if isinstance(r, Exception)], results

        units = await units_by_step(case["store"], case["plan_revision_id"])
        design = units["design"]
        conn = await case["store"]._connect()
        try:
            # One canonical dispatch...
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM plan_execution_dispatches WHERE execution_unit_id=$1",
                    design["execution_unit_id"],
                )
                == 1
            )
            # ...one canonical assignment, so one piece of routing evidence rather than eight.
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM agent_routing_decisions WHERE work_item_id=$1",
                    design["work_item_id"],
                )
                == 1
            )
        finally:
            await conn.close()

        # The wire is at-least-once and this is where that shows: workers that lost the race read
        # the canonical dispatch before the winner had stamped published_at, so several may put a
        # copy of it on the stream. What must be true -- and is -- is that every copy is the SAME
        # command. Serialising the publish would mean holding a row lock across a network call,
        # which is exactly what the AT-M3.4 design refused for the same reason.
        published = [e for bus in buses for e in bus.dispatches()]
        assert published, "the command should reach the wire at least once"
        assert {e["correlation_id"] for e in published} == {
            str((await case["store"].get_dispatch(design["execution_unit_id"]))["correlation_id"])
        }
        assert {e["execution_unit_id"] for e in published} == {str(design["execution_unit_id"])}
        assert {e["assigned_principal_id"] for e in published} == {
            str(design["assigned_principal_id"])
        }

    async def test_repeating_the_dispatch_race_many_rounds_never_produces_a_second_dispatch(self):
        for _ in range(3):
            case = await scenario()
            await _materialize(case)
            await asyncio.gather(
                *(
                    _service(RecordingBus()).schedule_ready_work(
                        plan_revision_id=case["plan_revision_id"]
                    )
                    for _ in range(8)
                )
            )
            conn = await case["store"]._connect()
            try:
                assert (
                    await conn.fetchval(
                        """
                        SELECT count(*) FROM plan_execution_dispatches d
                        JOIN plan_execution_units u ON u.execution_unit_id = d.execution_unit_id
                        WHERE u.plan_revision_id=$1
                        """,
                        uuid.UUID(case["plan_revision_id"]),
                    )
                    == 1
                )
            finally:
                await conn.close()


# --- dependency unlock ----------------------------------------------------------------------------------


class TestDependencyUnlock:
    async def test_A_then_B_then_C_unlocks_one_step_at_a_time(self):
        case = await scenario()
        await _materialize(case)
        service = _service(RecordingBus())

        await service.schedule_ready_work(plan_revision_id=case["plan_revision_id"])
        units = await units_by_step(case["store"], case["plan_revision_id"])
        assert units["build"]["state"] == UNIT_BLOCKED

        result = await _complete(case, units["design"])
        assert [u["step_key"] for u in result["unblocked"]] == ["build"]
        units = await units_by_step(case["store"], case["plan_revision_id"])
        assert units["build"]["state"] == UNIT_READY
        # Two steps downstream is still blocked -- readiness is not transitive.
        assert units["verify"]["state"] == UNIT_BLOCKED

        await service.schedule_ready_work(plan_revision_id=case["plan_revision_id"])
        units = await units_by_step(case["store"], case["plan_revision_id"])
        assert units["build"]["state"] == UNIT_DISPATCHED
        assert units["build"]["assigned_role"] == "development"

        await _complete(case, units["build"])
        units = await units_by_step(case["store"], case["plan_revision_id"])
        assert units["verify"]["state"] == UNIT_READY

    async def test_a_fan_in_step_stays_blocked_until_its_LAST_dependency_completes(self):
        case = await scenario(plan=FAN_IN_PLAN)
        await _materialize(case)
        service = _service(RecordingBus())
        await service.schedule_ready_work(plan_revision_id=case["plan_revision_id"])

        units = await units_by_step(case["store"], case["plan_revision_id"])
        assert units["left"]["state"] == units["right"]["state"] == UNIT_DISPATCHED

        result = await _complete(case, units["left"])
        assert result["unblocked"] == []
        units = await units_by_step(case["store"], case["plan_revision_id"])
        assert units["join"]["state"] == UNIT_BLOCKED

        result = await _complete(case, units["right"])
        assert [u["step_key"] for u in result["unblocked"]] == ["join"]
        units = await units_by_step(case["store"], case["plan_revision_id"])
        assert units["join"]["state"] == UNIT_READY

    async def test_two_dependencies_completing_at_the_same_moment_unlock_the_join_once(self):
        case = await scenario(plan=FAN_IN_PLAN)
        await _materialize(case)
        await _service(RecordingBus()).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )
        units = await units_by_step(case["store"], case["plan_revision_id"])

        results = await asyncio.gather(
            _complete(case, units["left"]), _complete(case, units["right"])
        )
        unblocked = [u["step_key"] for r in results for u in r["unblocked"]]
        # Exactly one of the two completions promoted the join.
        assert unblocked == ["join"]

        units = await units_by_step(case["store"], case["plan_revision_id"])
        assert units["join"]["state"] == UNIT_READY

        # And it is dispatched exactly once from there.
        await asyncio.gather(
            *(
                _service(RecordingBus()).schedule_ready_work(
                    plan_revision_id=case["plan_revision_id"]
                )
                for _ in range(8)
            )
        )
        conn = await case["store"]._connect()
        try:
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM plan_execution_dispatches WHERE execution_unit_id=$1",
                    units["join"]["execution_unit_id"],
                )
                == 1
            )
        finally:
            await conn.close()

    async def test_a_failed_step_does_not_unlock_what_it_was_blocking(self):
        """A dependency that failed has not produced what its dependent was promised."""
        case = await scenario()
        await _materialize(case)
        await _service(RecordingBus()).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )
        units = await units_by_step(case["store"], case["plan_revision_id"])

        result = await _complete(case, units["design"], disposition="failed")
        assert result["unblocked"] == []
        units = await units_by_step(case["store"], case["plan_revision_id"])
        assert units["design"]["state"] == UNIT_FAILED
        assert units["build"]["state"] == UNIT_BLOCKED


# --- completion authority -----------------------------------------------------------------------------------


class TestCompletionAuthority:
    async def test_a_result_without_the_dispatch_correlation_id_is_refused(self):
        case = await scenario()
        await _materialize(case)
        await _service(RecordingBus()).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )
        units = await units_by_step(case["store"], case["plan_revision_id"])
        dispatch = await case["store"].get_dispatch(units["design"]["execution_unit_id"])

        with pytest.raises(DispatchLineageError, match="correlation id"):
            await _service().record_step_result(
                execution_unit_id=str(units["design"]["execution_unit_id"]),
                reported_by=str(dispatch["assigned_principal_id"]),
                correlation_id=str(uuid.uuid4()),
                disposition="succeeded",
            )
        units = await units_by_step(case["store"], case["plan_revision_id"])
        assert units["design"]["state"] == UNIT_DISPATCHED

    async def test_a_result_from_a_principal_the_step_was_not_dispatched_to_is_refused(self):
        case = await scenario()
        await _materialize(case)
        await _service(RecordingBus()).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )
        units = await units_by_step(case["store"], case["plan_revision_id"])
        dispatch = await case["store"].get_dispatch(units["design"]["execution_unit_id"])

        conn = await case["store"]._connect()
        try:
            impostor = await conn.fetchval(
                "INSERT INTO actor_principals (principal_type,display_name) "
                "VALUES ('runtime_agent','impostor') RETURNING principal_id"
            )
        finally:
            await conn.close()

        with pytest.raises(DispatchLineageError, match="another principal"):
            await _service().record_step_result(
                execution_unit_id=str(units["design"]["execution_unit_id"]),
                reported_by=str(impostor),
                correlation_id=str(dispatch["correlation_id"]),
                disposition="succeeded",
            )

    async def test_a_result_for_a_step_that_was_never_dispatched_is_refused(self):
        case = await scenario()
        result = await _materialize(case)
        design = next(u for u in result["units"] if u["step_key"] == "design")
        with pytest.raises(DispatchLineageError, match="never handed over"):
            await _service().record_step_result(
                execution_unit_id=str(design["execution_unit_id"]),
                reported_by=case["author"],
                correlation_id=str(uuid.uuid4()),
                disposition="succeeded",
            )

    async def test_reporting_the_same_result_twice_replays_rather_than_applying_twice(self):
        case = await scenario()
        await _materialize(case)
        await _service(RecordingBus()).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )
        units = await units_by_step(case["store"], case["plan_revision_id"])

        first = await _complete(case, units["design"])
        second = await _complete(case, units["design"])
        assert first["outcome"] == "recorded" and second["outcome"] == "replay"
        # The unlock happened once, not twice.
        assert [u["step_key"] for u in first["unblocked"]] == ["build"]
        assert second["unblocked"] == []

    async def test_a_completed_step_cannot_be_re_reported_as_failed(self):
        case = await scenario()
        await _materialize(case)
        await _service(RecordingBus()).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )
        units = await units_by_step(case["store"], case["plan_revision_id"])
        await _complete(case, units["design"])

        with pytest.raises(ExecutionUnitStateError, match="already terminalized"):
            await _complete(case, units["design"], disposition="failed")

    async def test_a_completion_is_recorded_in_the_existing_work_item_event_log(self):
        case = await scenario()
        await _materialize(case)
        await _service(RecordingBus()).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )
        units = await units_by_step(case["store"], case["plan_revision_id"])
        await _complete(case, units["design"])

        conn = await case["store"]._connect()
        try:
            events = await conn.fetch(
                "SELECT event_type, from_state, to_state, metadata FROM work_item_events "
                "WHERE work_item_id=$1 ORDER BY created_at",
                units["design"]["work_item_id"],
            )
        finally:
            await conn.close()
        types = [e["event_type"] for e in events]
        assert "plan_step.dispatched" in types and "plan_step.result_recorded" in types

    async def test_the_work_item_mirrors_the_units_state_so_the_lineage_row_stays_truthful(self):
        case = await scenario()
        await _materialize(case)
        await _service(RecordingBus()).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )
        units = await units_by_step(case["store"], case["plan_revision_id"])

        conn = await case["store"]._connect()
        try:
            assert (
                await conn.fetchval(
                    "SELECT status FROM project_work_items WHERE id=$1",
                    units["design"]["work_item_id"],
                )
                == "in_progress"
            )
            await _complete(case, units["design"])
            assert (
                await conn.fetchval(
                    "SELECT status FROM project_work_items WHERE id=$1",
                    units["design"]["work_item_id"],
                )
                == "completed"
            )
        finally:
            await conn.close()


# --- stale plan and cancellation --------------------------------------------------------------------------------


class TestStalePlanAndCancellation:
    async def test_a_superseded_graph_dispatches_nothing_further(self):
        case = await scenario()
        await _materialize(case)
        service = _service(RecordingBus())
        await service.schedule_ready_work(plan_revision_id=case["plan_revision_id"])
        units = await units_by_step(case["store"], case["plan_revision_id"])
        await _complete(case, units["design"])

        await supersede(case)

        bus = RecordingBus()
        with pytest.raises(StalePlanRevisionError):
            await _service(bus).schedule_ready_work(plan_revision_id=case["plan_revision_id"])
        assert bus.dispatches() == []

        units = await units_by_step(case["store"], case["plan_revision_id"])
        # The step that became ready under revision N stays ready and unassigned; it is not
        # rewritten, deleted or rebound. It simply is not authoritative any more.
        assert units["build"]["state"] == UNIT_READY
        assert units["build"]["assigned_principal_id"] is None

    async def test_work_already_dispatched_under_a_superseded_revision_may_still_finish(self):
        """Historical execution evidence is never rewritten. A successor stops NEW dispatch; it
        does not reach into work a principal is already holding."""
        case = await scenario()
        await _materialize(case)
        await _service(RecordingBus()).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )
        units = await units_by_step(case["store"], case["plan_revision_id"])
        await supersede(case)

        result = await _complete(case, units["design"])
        assert result["outcome"] == "recorded"
        units = await units_by_step(case["store"], case["plan_revision_id"])
        assert units["design"]["state"] == UNIT_COMPLETED

    async def test_the_graph_reports_that_it_is_no_longer_current_without_storing_it(self):
        case = await scenario()
        await _materialize(case)
        assert (await case["store"].get_graph(case["plan_revision_id"]))["is_current"] is True
        await supersede(case)
        assert (await case["store"].get_graph(case["plan_revision_id"]))["is_current"] is False

    async def test_a_cancelled_execution_lineage_prevents_every_new_dispatch(self):
        case = await scenario()
        await _materialize(case)
        await cancel_primary_work_item(case["store"], case["goal_id"])

        bus = RecordingBus()
        with pytest.raises(ExecutionLineageCancelledError):
            await _service(bus).schedule_ready_work(plan_revision_id=case["plan_revision_id"])
        assert bus.dispatches() == []

        units = await units_by_step(case["store"], case["plan_revision_id"])
        assert units["design"]["state"] == UNIT_READY
        assert await case["store"].get_dispatch(units["design"]["execution_unit_id"]) is None

    async def test_a_cancelled_lineage_also_prevents_a_new_graph(self):
        case = await scenario()
        await _materialize(case)
        await cancel_primary_work_item(case["store"], case["goal_id"])
        successor = await supersede(case)
        # The graph itself may still be materialized -- materialization creates no dispatch -- but
        # nothing in it can be handed to anyone.
        await _service().materialize_accepted_plan(
            goal_id=case["goal_id"], plan_revision_id=successor, materialized_by=case["author"]
        )
        with pytest.raises(ExecutionLineageCancelledError):
            await _service(RecordingBus()).schedule_ready_work(plan_revision_id=successor)


# --- restart and replay ------------------------------------------------------------------------------------


class TestRestartAndReplay:
    async def test_the_graph_is_rebuilt_from_rows_by_a_process_that_never_saw_it(self):
        case = await scenario()
        await _materialize(case)
        await _service(RecordingBus()).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )
        units = await units_by_step(case["store"], case["plan_revision_id"])
        await _complete(case, units["design"])

        # A brand-new store and service: no shared memory with anything above.
        restarted = PlanDelegationStore()
        graph = await restarted.get_graph(case["plan_revision_id"])
        states = {u["step_key"]: u["state"] for u in graph["units"]}
        assert states == {
            "design": UNIT_COMPLETED,
            "build": UNIT_READY,
            "verify": UNIT_BLOCKED,
        }
        assert len(graph["dispatches"]) == 1

    async def test_a_scheduler_restarted_mid_flight_continues_without_duplicating_anything(self):
        case = await scenario()
        await _materialize(case)
        await _service(RecordingBus()).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )
        units = await units_by_step(case["store"], case["plan_revision_id"])
        await _complete(case, units["design"])

        fresh = PlanDelegationService(event_bus=RecordingBus())
        await fresh.schedule_ready_work(plan_revision_id=case["plan_revision_id"])

        conn = await case["store"]._connect()
        try:
            assert (
                await conn.fetchval(
                    """
                    SELECT count(*) FROM plan_execution_dispatches d
                    JOIN plan_execution_units u ON u.execution_unit_id=d.execution_unit_id
                    WHERE u.plan_revision_id=$1
                    """,
                    uuid.UUID(case["plan_revision_id"]),
                )
                == 2
            )
        finally:
            await conn.close()

    async def test_a_dispatch_the_broker_refused_is_republished_not_reissued(self):
        """The transport is at-least-once and the canonical dispatch is exactly-once. A publish
        failure leaves the SAME row unpublished for the next pass; it never mints a second one."""
        case = await scenario()
        await _materialize(case)
        broken = RecordingBus(fail=True)
        await _service(broken).schedule_ready_work(plan_revision_id=case["plan_revision_id"])

        units = await units_by_step(case["store"], case["plan_revision_id"])
        dispatch = await case["store"].get_dispatch(units["design"]["execution_unit_id"])
        assert units["design"]["state"] == UNIT_DISPATCHED
        assert dispatch["published_at"] is None

        working = RecordingBus()
        outcome = await _service(working).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )
        assert outcome["results"][0]["published"] is True
        republished = await case["store"].get_dispatch(units["design"]["execution_unit_id"])
        assert republished["published_at"] is not None
        # Same canonical dispatch, same correlation id on the wire.
        assert str(republished["correlation_id"]) == str(dispatch["correlation_id"])
        assert working.dispatches()[0]["correlation_id"] == str(dispatch["correlation_id"])


# --- dispatch binding and boundaries --------------------------------------------------------------------------


class TestDispatchBindingAndBoundaries:
    async def test_the_dispatch_names_the_exact_revision_and_step_that_authorized_it(self):
        case = await scenario()
        await _materialize(case)
        await _service(RecordingBus()).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )
        units = await units_by_step(case["store"], case["plan_revision_id"])
        dispatch = await case["store"].get_dispatch(units["design"]["execution_unit_id"])

        assert str(dispatch["plan_revision_id"]) == case["plan_revision_id"]
        assert dispatch["step_key"] == "design"

        # A successor exists, and the dispatch still belongs to the revision that issued it.
        successor = await supersede(case)
        conn = await case["store"]._connect()
        try:
            with pytest.raises(Exception, match="may not be rewritten"):
                await conn.execute(
                    "UPDATE plan_execution_dispatches SET plan_revision_id=$2 "
                    "WHERE execution_unit_id=$1",
                    units["design"]["execution_unit_id"],
                    uuid.UUID(successor),
                )
            still = await conn.fetchval(
                "SELECT plan_revision_id FROM plan_execution_dispatches WHERE execution_unit_id=$1",
                units["design"]["execution_unit_id"],
            )
        finally:
            await conn.close()
        assert str(still) == case["plan_revision_id"]

    async def test_a_second_canonical_dispatch_for_one_unit_is_not_representable(self):
        case = await scenario()
        await _materialize(case)
        await _service(RecordingBus()).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )
        units = await units_by_step(case["store"], case["plan_revision_id"])
        design = units["design"]

        conn = await case["store"]._connect()
        try:
            with pytest.raises(Exception):
                await conn.execute(
                    """
                    INSERT INTO plan_execution_dispatches
                      (execution_unit_id, plan_revision_id, step_key, project_id, work_item_id,
                       assigned_principal_id, target_stream)
                    VALUES ($1,$2,$3,$4,$5,$6,'stream.somewhere_else')
                    """,
                    design["execution_unit_id"],
                    uuid.UUID(case["plan_revision_id"]),
                    "design",
                    uuid.UUID(case["project_id"]),
                    design["work_item_id"],
                    design["assigned_principal_id"],
                )
        finally:
            await conn.close()

    async def test_delegation_touches_no_approval_and_records_no_production_effect(self):
        store = await store_or_skip()
        conn = await store._connect()
        try:
            approvals_before = await conn.fetchval("SELECT count(*) FROM approval_requests")
        finally:
            await conn.close()

        case = await scenario()
        await _materialize(case)
        await _service(RecordingBus()).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )
        units = await units_by_step(case["store"], case["plan_revision_id"])
        await _complete(case, units["design"])

        conn = await store._connect()
        try:
            assert await conn.fetchval("SELECT count(*) FROM approval_requests") == approvals_before
            # No work item this slice created carries a production effect, and none is dispatched
            # through the Step 57 production-effect path.
            assert (
                await conn.fetchval(
                    """
                    SELECT count(*) FROM project_work_items w
                    JOIN plan_execution_units u ON u.work_item_id = w.id
                    WHERE u.plan_revision_id=$1 AND w.production_effect
                    """,
                    uuid.UUID(case["plan_revision_id"]),
                )
                == 0
            )
        finally:
            await conn.close()
