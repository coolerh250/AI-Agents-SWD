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

from tests.plan_delegation_fixtures import scenario, units_by_step

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
    await bus.ensure_group("stream.design_review", group)
    return case, service, group


async def test_the_command_lands_on_the_selected_agents_own_stream():
    bus = await _bus_or_skip()
    try:
        case, service, group = await _prepared(bus)
        await service.schedule_ready_work(plan_revision_id=case["plan_revision_id"])

        events = await _drain(bus, "stream.design_review", group)
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
        envelope = (await _drain(bus, "stream.design_review", group))[0]

        assert envelope["correlation_id"] == str(dispatch["correlation_id"])
        assert dispatch["published_at"] is not None
    finally:
        await bus.close()


async def test_the_envelope_carries_no_secret_no_transcript_and_no_external_authorization():
    bus = await _bus_or_skip()
    try:
        case, service, group = await _prepared(bus)
        await service.schedule_ready_work(plan_revision_id=case["plan_revision_id"])
        envelope = (await _drain(bus, "stream.design_review", group))[0]

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
            streams={"stream.design_review": ">"},
            count=10,
        )
        assert first, "the command should be delivered once"

        # Never acknowledged: the same consumer re-reads its pending entries.
        redelivered = await bus.client.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={"stream.design_review": "0"},
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
        events = await _drain(bus, "stream.design_review", group)
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
        await bus.client.delete("stream.design_review")

        units = await units_by_step(case["store"], case["plan_revision_id"])
        assert units["design"]["state"] == "dispatched"

        await bus.ensure_group("stream.design_review", group)
        await service.schedule_ready_work(plan_revision_id=case["plan_revision_id"])
        # Already published, so nothing is re-sent: the canonical row says the work was handed over.
        assert await _drain(bus, "stream.design_review", group) == []
    finally:
        await bus.close()
