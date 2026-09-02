"""Step AT-M3.5 -- dispatch over an ACTUAL local Redis, against an actual PostgreSQL.

What this file exists to prove is the split the design rests on: the stream is TRANSPORT and
PostgreSQL is STATE. Redis Streams deliver at-least-once, so a consumer can and will see the same
plan-step command twice; what must never happen is two DIFFERENT canonical dispatches for one step,
or a step whose command reached the wire without a durable row behind it.

It also proves the routing is real at the transport layer: the command lands on the SELECTED
agent's own stream, so changing the team changes the destination. A test that only checked "a
message was published somewhere" would pass against a compile-time stream constant.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest

from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from shared.sdk.plan_delegation.service import PlanDelegationService
from shared.sdk.plan_delegation.store import PlanDelegationStore

from tests.plan_delegation_fixtures import AuditRecorder, scenario, units_by_step

#: The isolated destination for the seeded design-review agent. NOT ``stream.design_review``,
#: which ``DesignReviewAgent`` consumes -- publishing there would hand an L3 coordination message
#: to an L4 executor.
DESIGN_REVIEW_DELEGATION_STREAM = "stream.plan_delegation.design-review-agent"

pytestmark = pytest.mark.asyncio


async def _bus_or_skip() -> RedisStreamEventBus:
    bus = RedisStreamEventBus(
        os.environ.get("REDIS_URL", "redis://localhost:6379"),
        socket_connect_timeout=3,
        socket_timeout=3,
    )
    try:
        await bus.client.ping()
    except Exception:
        await bus.close()
        pytest.skip("no reachable local Redis; skipping AT-M3.5 stream test")
    return bus


async def _drain(bus: RedisStreamEventBus, stream: str, group: str) -> list[dict]:
    """Read whatever is pending for a fresh consumer group on this stream."""
    consumer = f"m35-{uuid.uuid4().hex[:8]}"
    events = await bus.consume_events(stream, group, consumer, count=50, block_ms=200)
    return [e["event"] for e in events]


async def _prepared(bus: RedisStreamEventBus):
    """A materialized graph whose root has NOT been dispatched yet, with its group created first.

    The group is created before the dispatch so the very first delivery is visible to it: a
    consumer group created at ``$`` after the fact would not see a message already on the stream,
    and the test would pass for the wrong reason.
    """
    case = await scenario()
    service = PlanDelegationService(event_bus=bus)
    await service.materialize_accepted_plan(
        goal_id=case["goal_id"],
        plan_revision_id=case["plan_revision_id"],
        materialized_by=case["author"],
    )
    group = f"m35-group-{uuid.uuid4().hex[:8]}"
    await bus.ensure_group(DESIGN_REVIEW_DELEGATION_STREAM, group)
    return case, service, group


async def test_the_command_lands_on_the_selected_agents_own_stream():
    bus = await _bus_or_skip()
    try:
        case, service, group = await _prepared(bus)
        await service.schedule_ready_work(plan_revision_id=case["plan_revision_id"])

        events = await _drain(bus, DESIGN_REVIEW_DELEGATION_STREAM, group)
        dispatches = [e for e in events if e.get("event") == "plan_step.dispatched"]
        assert len(dispatches) == 1

        units = await units_by_step(case["store"], case["plan_revision_id"])
        design = units["design"]
        envelope = dispatches[0]
        assert envelope["step_key"] == "design"
        assert envelope["execution_unit_id"] == str(design["execution_unit_id"])
        assert envelope["plan_revision_id"] == case["plan_revision_id"]
        assert envelope["assigned_principal_id"] == str(design["assigned_principal_id"])
    finally:
        await bus.close()


async def test_the_wire_identity_is_the_canonical_dispatchs_own_correlation_id():
    bus = await _bus_or_skip()
    try:
        case, service, group = await _prepared(bus)
        await service.schedule_ready_work(plan_revision_id=case["plan_revision_id"])

        units = await units_by_step(case["store"], case["plan_revision_id"])
        dispatch = await case["store"].get_dispatch(units["design"]["execution_unit_id"])
        envelope = (await _drain(bus, DESIGN_REVIEW_DELEGATION_STREAM, group))[0]

        assert envelope["correlation_id"] == str(dispatch["correlation_id"])
        assert dispatch["published_at"] is not None
    finally:
        await bus.close()


async def test_the_envelope_carries_no_secret_no_transcript_and_no_external_authorization():
    bus = await _bus_or_skip()
    try:
        case, service, group = await _prepared(bus)
        await service.schedule_ready_work(plan_revision_id=case["plan_revision_id"])
        envelope = (await _drain(bus, DESIGN_REVIEW_DELEGATION_STREAM, group))[0]

        for flag in (
            "production_action",
            "production_effect",
            "github_write",
            "argocd_sync",
            "external_notification_send",
            "code_execution",
        ):
            assert envelope[flag] is False, flag
        for forbidden in ("plan", "objective", "steps", "messages", "api_key", "token", "secret"):
            assert forbidden not in envelope, forbidden
    finally:
        await bus.close()


async def test_a_redelivered_command_is_recognisable_as_the_same_dispatch():
    """At-least-once transport. A consumer that crashes before acknowledging re-reads the SAME
    message from its pending entries list, with the same correlation id -- so it can dedupe rather
    than treat it as a second assignment."""
    bus = await _bus_or_skip()
    try:
        case, service, group = await _prepared(bus)
        await service.schedule_ready_work(plan_revision_id=case["plan_revision_id"])

        consumer = "m35-crashy"
        first = await bus.client.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={DESIGN_REVIEW_DELEGATION_STREAM: ">"},
            count=10,
        )
        assert first, "the command should be delivered once"

        # Never acknowledged: the same consumer re-reads its pending entries.
        redelivered = await bus.client.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={DESIGN_REVIEW_DELEGATION_STREAM: "0"},
            count=10,
        )
        import json

        original = json.loads(first[0][1][0][1]["data"])
        again = json.loads(redelivered[0][1][0][1]["data"])
        assert again["correlation_id"] == original["correlation_id"]
        assert again["execution_unit_id"] == original["execution_unit_id"]
    finally:
        await bus.close()


async def test_eight_schedulers_against_real_redis_deliver_one_command_identity():
    """The honest boundary, stated as an assertion rather than a comment.

    Eight schedulers race one ready step. PostgreSQL holds exactly ONE canonical dispatch. The
    stream may carry more than one copy of it -- workers that lost the race read the row before the
    winner stamped ``published_at`` -- and every copy is the SAME command, with the same
    correlation id and the same assignee. That is at-least-once transport over exactly-once state,
    which is what Redis can actually guarantee; claiming more would be claiming something the
    infrastructure does not do.
    """
    bus = await _bus_or_skip()
    try:
        case, service, group = await _prepared(bus)
        await asyncio.gather(
            *(
                PlanDelegationService(event_bus=bus).schedule_ready_work(
                    plan_revision_id=case["plan_revision_id"]
                )
                for _ in range(8)
            )
        )
        events = await _drain(bus, DESIGN_REVIEW_DELEGATION_STREAM, group)
        dispatches = [e for e in events if e.get("event") == "plan_step.dispatched"]
        assert dispatches, "the command should reach the wire at least once"
        assert len({e["correlation_id"] for e in dispatches}) == 1
        assert len({e["execution_unit_id"] for e in dispatches}) == 1
        assert len({e["assigned_principal_id"] for e in dispatches}) == 1

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
    finally:
        await bus.close()


async def test_postgresql_not_redis_is_the_source_of_truth_for_what_was_dispatched():
    """Wiping the stream does not un-dispatch the step, and does not make it dispatchable again."""
    bus = await _bus_or_skip()
    try:
        case, service, group = await _prepared(bus)
        await service.schedule_ready_work(plan_revision_id=case["plan_revision_id"])
        await bus.client.delete(DESIGN_REVIEW_DELEGATION_STREAM)

        units = await units_by_step(case["store"], case["plan_revision_id"])
        assert units["design"]["state"] == "dispatched"

        await bus.ensure_group(DESIGN_REVIEW_DELEGATION_STREAM, group)
        await service.schedule_ready_work(plan_revision_id=case["plan_revision_id"])
        # Already published, so nothing is re-sent: the canonical row says the work was handed over.
        assert await _drain(bus, DESIGN_REVIEW_DELEGATION_STREAM, group) == []
    finally:
        await bus.close()


# --- the delegation namespace is isolated from live agent streams -------------------------------

#: The streams a live StreamAgent or the orchestrator's workflow-event consumer actually reads.
#: Independent Validation 1 found AT-M3.5 publishing onto exactly these.
LEGACY_AGENT_STREAMS = (
    "stream.development",
    "stream.qa",
    "stream.design_review",
    "stream.deployments",
    "stream.requirements",
    "stream.tasks",
    "stream.project_planning",
)


async def _lengths(bus: RedisStreamEventBus, streams) -> dict[str, int]:
    return {stream: int(await bus.client.xlen(stream)) for stream in streams}


async def test_scheduling_places_nothing_on_any_live_agent_input_stream():
    """The remediation's dynamic proof, against a real broker.

    A StreamAgent consuming ``stream.development`` calls ``handle(payload)`` on whatever arrives.
    If one byte of AT-M3.5's delegation reached it, that is AT-M4 execution begun by a stream name.
    Nothing does, and the counters prove it rather than a comment asserting it.
    """
    bus = await _bus_or_skip()
    try:
        case, service, group = await _prepared(bus)
        before = await _lengths(bus, LEGACY_AGENT_STREAMS)

        await service.schedule_ready_work(plan_revision_id=case["plan_revision_id"])
        units = await units_by_step(case["store"], case["plan_revision_id"])
        await service.record_internal_result(
            execution_unit_id=str(units["design"]["execution_unit_id"]), disposition="succeeded"
        )
        await service.schedule_ready_work(plan_revision_id=case["plan_revision_id"])

        assert await _lengths(bus, LEGACY_AGENT_STREAMS) == before

        # And the work really did get dispatched -- to the isolated namespace instead.
        units = await units_by_step(case["store"], case["plan_revision_id"])
        assert units["build"]["state"] == "dispatched"
        dispatch = await case["store"].get_dispatch(units["build"]["execution_unit_id"])
        assert dispatch["target_stream"] == "stream.plan_delegation.development-agent"
        assert int(await bus.client.xlen(dispatch["target_stream"])) >= 1
    finally:
        await bus.close()


async def test_the_delegation_namespace_has_no_consumer_group_of_its_own():
    """AT-M3.5 has no execution consumer by design, so a duplicate delivery has zero effect.

    The only groups on a delegation stream are the disposable ones these tests create; nothing in
    the runtime registers one. The repository-wide static proof is in
    ``test_at_m3_5_transport_isolation.py``; this is the live half.
    """
    bus = await _bus_or_skip()
    try:
        case, service, _ = await _prepared(bus)
        await service.schedule_ready_work(plan_revision_id=case["plan_revision_id"])
        units = await units_by_step(case["store"], case["plan_revision_id"])
        stream = (await case["store"].get_dispatch(units["design"]["execution_unit_id"]))[
            "target_stream"
        ]

        groups = await bus.client.xinfo_groups(stream)
        assert all(str(g["name"]).startswith("m35-group-") for g in groups), groups
    finally:
        await bus.close()


# --- one canonical dispatch success per canonical dispatch --------------------------------------


async def test_eight_publishers_race_and_the_audit_chain_records_one_dispatch_success():
    """Independent Validation 1's fourth defect.

    Several workers may put a copy of the same canonical dispatch on the wire -- that is
    at-least-once transport, and it is allowed. What is not allowed is each of them claiming a
    successful dispatch in the audit chain: the record would then say the team handed one step over
    three times. ``mark_dispatch_published`` is a write-once compare-and-swap and already knows who
    won; the success event now follows that, not the ``XADD``.
    """
    bus = await _bus_or_skip()
    try:
        case, _, group = await _prepared(bus)
        audit = AuditRecorder()
        await asyncio.gather(
            *(
                PlanDelegationService(event_bus=bus, audit_client=audit).schedule_ready_work(
                    plan_revision_id=case["plan_revision_id"]
                )
                for _ in range(8)
            )
        )

        units = await units_by_step(case["store"], case["plan_revision_id"])
        design = units["design"]
        dispatch = await case["store"].get_dispatch(design["execution_unit_id"])

        conn = await case["store"]._connect()
        try:
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM plan_execution_dispatches WHERE execution_unit_id=$1",
                    design["execution_unit_id"],
                )
                == 1
            )
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM agent_routing_decisions WHERE work_item_id=$1",
                    design["work_item_id"],
                )
                == 1
            )
        finally:
            await conn.close()

        successes = audit.of_type("plan_step_dispatched")
        assert len(successes) == 1, successes
        assert successes[0]["artifact_refs"]["correlation_id"] == str(dispatch["correlation_id"])

        # Redis may legitimately hold several copies -- all of one command.
        delivered = [
            e
            for e in await _drain(bus, DESIGN_REVIEW_DELEGATION_STREAM, group)
            if e.get("event") == "plan_step.dispatched"
        ]
        assert delivered
        assert {e["correlation_id"] for e in delivered} == {str(dispatch["correlation_id"])}
        assert {e["execution_unit_id"] for e in delivered} == {str(design["execution_unit_id"])}
    finally:
        await bus.close()


class _PublishThenDie(PlanDelegationStore):
    """A store whose first ``published_at`` stamp never lands.

    Models the second publish crash window: the ``XADD`` succeeded and the process died before the
    compare-and-swap committed. A real crash cannot be staged inside one test process, so the
    single write that would not have survived it is suppressed instead.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.suppressed = False

    async def mark_dispatch_published(self, execution_unit_id, *, conn=None) -> bool:
        if not self.suppressed:
            self.suppressed = True
            return False
        return await super().mark_dispatch_published(execution_unit_id, conn=conn)


async def test_a_crash_between_the_publish_and_the_stamp_still_audits_exactly_one_success():
    bus = await _bus_or_skip()
    try:
        case, _, group = await _prepared(bus)
        audit = AuditRecorder()

        crashed = PlanDelegationService(store=_PublishThenDie(), event_bus=bus, audit_client=audit)
        await crashed.schedule_ready_work(plan_revision_id=case["plan_revision_id"])

        units = await units_by_step(case["store"], case["plan_revision_id"])
        dispatch = await case["store"].get_dispatch(units["design"]["execution_unit_id"])
        # The command reached the wire; the canonical state does not yet know it did.
        assert dispatch["published_at"] is None
        assert audit.of_type("plan_step_dispatched") == []

        # Restart. The same canonical dispatch is republished -- never reissued.
        await PlanDelegationService(event_bus=bus, audit_client=audit).schedule_ready_work(
            plan_revision_id=case["plan_revision_id"]
        )
        settled = await case["store"].get_dispatch(units["design"]["execution_unit_id"])
        assert settled["published_at"] is not None
        assert str(settled["correlation_id"]) == str(dispatch["correlation_id"])

        successes = audit.of_type("plan_step_dispatched")
        assert len(successes) == 1

        delivered = [
            e
            for e in await _drain(bus, DESIGN_REVIEW_DELEGATION_STREAM, group)
            if e.get("event") == "plan_step.dispatched"
        ]
        assert len(delivered) == 2, "the duplicate delivery this window causes is expected"
        assert {e["correlation_id"] for e in delivered} == {str(dispatch["correlation_id"])}

        conn = await case["store"]._connect()
        try:
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM plan_execution_dispatches WHERE execution_unit_id=$1",
                    units["design"]["execution_unit_id"],
                )
                == 1
            )
        finally:
            await conn.close()
    finally:
        await bus.close()
