"""Step AT-M3.3-R1 -- the elapsed-time bound, the exact stop reasons, and exact-revision semantics.

Real PostgreSQL, because none of the three properties under test is provable anywhere else:

* the deadline is an instant the DATABASE computes and every worker reads, so a fake clock would
  be testing the fake;
* a stuck ``started`` reasoning invocation is a row that outlives the process that wrote it, which
  is the entire failure being fixed;
* plan currency is a lineage query, and the guarantee that a stale discussion cannot produce a
  successor is a ``FOR UPDATE`` re-check plus a partial unique index.

Deadlines here are fractions of a second on purpose. The bound is an absolute instant and the
migration forbids inserting one already in the past, so the honest way to test expiry is to let a
very short one actually pass -- not to rewrite the row, which the schema also forbids.
"""

from __future__ import annotations

import asyncio
import uuid

import asyncpg
import pytest

from shared.sdk.agent_deliberation.models import (
    DiscussionBounds,
    DiscussionStateError,
    derive_correlation_id,
)
from shared.sdk.agent_deliberation.service import DiscussionService
from shared.sdk.agent_deliberation.store import DeliberationStore
from shared.sdk.agent_planning.models import StalePlanRevisionError
from shared.sdk.agent_planning.store import PlanningStore
from shared.sdk.agent_reasoning.models import CritiqueArtifact, ProposalArtifact

from tests.test_at_m3_3_deliberation_store import (
    CAPS,
    PLAN,
    ContestingProvider,
    ConvergingProvider,
    _scenario,
    _service,
    _start,
)

#: Long enough that nothing expires by accident on a slow runner, short enough that the whole
#: module stays quick. Every expiry test waits exactly one of these plus a small margin.
SHORT = 0.6
MARGIN = 0.35


async def _wait_past(deadline_seconds: float = SHORT) -> None:
    await asyncio.sleep(deadline_seconds + MARGIN)


class CountingProvider(ConvergingProvider):
    """Records every call, so "no provider ran after the deadline" is checkable, not assumed."""

    name = "test-counting"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def propose(self, request) -> ProposalArtifact:
        self.calls.append("propose")
        return super().propose(request)

    def critique(self, request) -> CritiqueArtifact:
        self.calls.append("critique")
        return super().critique(request)

    def summarize_decision(self, request):
        self.calls.append("summarize_decision")
        return super().summarize_decision(request)


class SlowProvider(ConvergingProvider):
    """Returns successfully, but only after the discussion's deadline has already passed.

    This is the adversarial shape of section 5: the call was legitimately started inside the
    window and legitimately produced an artifact, and by the time it lands the room has closed.
    """

    name = "test-slow"

    def __init__(self, delay: float = SHORT + MARGIN) -> None:
        self.delay = delay

    def _stall(self) -> None:
        import time

        time.sleep(self.delay)

    def propose(self, request) -> ProposalArtifact:
        self._stall()
        return super().propose(request)

    def critique(self, request) -> CritiqueArtifact:
        self._stall()
        return super().critique(request)


async def _bounded(scenario, *, seconds=SHORT, provider=None, key=None, **bounds):
    return await _start(
        scenario,
        provider=provider,
        key=key,
        bounds=DiscussionBounds(timeout_seconds=seconds, **bounds),
    )


def _advance_in_its_own_loop(discussion_id: str, delay: float) -> dict:
    """One advance, in a separate thread with its own event loop and its own connections.

    ``ReasoningService`` calls the provider synchronously, so a provider that stalls would block
    this test's event loop and make "another worker closed it meanwhile" untestable. Running the
    slow worker as a genuinely separate worker is both more honest and the only way the race can
    actually happen.
    """
    return asyncio.run(DiscussionService(provider=SlowProvider(delay=delay)).advance(discussion_id))


async def _sessions_for_goal(store: DeliberationStore, goal_id: str) -> int:
    conn = await store._connect()
    try:
        return await conn.fetchval(
            "SELECT count(*) FROM discussion_sessions WHERE goal_id=$1", uuid.UUID(goal_id)
        )
    finally:
        await conn.close()


# ==================================================================================================
# B1 -- the persisted elapsed-time bound
# ==================================================================================================


@pytest.mark.asyncio
async def test_the_deadline_is_an_absolute_instant_the_database_computed():
    scenario = await _scenario()
    session = await _bounded(scenario, seconds=120)

    assert session["deadline_at"] is not None
    assert session["deadline_expired"] is False
    # Derived from the DB clock at insert, so it sits ahead of the row's own creation instant by
    # about the configured duration -- not by whatever this test host's clock believes.
    delta = (session["deadline_at"] - session["created_at"]).total_seconds()
    assert 119 < delta < 121


@pytest.mark.asyncio
async def test_the_deadline_survives_a_completely_new_object_graph():
    """A process restart must not lose the bound. It is a column, not a timer."""
    scenario = await _scenario()
    session = await _bounded(scenario, seconds=120)
    discussion_id = str(session["discussion_id"])

    fresh = DiscussionService(store=DeliberationStore(), provider=ConvergingProvider())
    reread = await fresh.get_discussion(discussion_id)
    assert reread["deadline_at"] == session["deadline_at"]
    assert reread["deadline_expired"] is False


@pytest.mark.asyncio
async def test_an_idle_open_discussion_becomes_terminal_when_its_deadline_passes():
    scenario = await _scenario()
    session = await _bounded(scenario)
    discussion_id = str(session["discussion_id"])
    await _wait_past()

    outcome = await DiscussionService(provider=ConvergingProvider()).advance(discussion_id)
    assert outcome["advanced"] is True
    assert outcome["session"]["state"] == "exhausted"
    assert outcome["session"]["stop_reason"] == "timeout_reached"
    # Nothing was said, so nothing is recorded as having been said.
    assert outcome["session"]["turns_taken"] == 0
    assert outcome["session"]["result_message_id"] is None


@pytest.mark.asyncio
async def test_no_provider_is_invoked_after_the_deadline():
    scenario = await _scenario()
    session = await _bounded(scenario)
    await _wait_past()

    provider = CountingProvider()
    await DiscussionService(provider=provider).run(str(session["discussion_id"]))
    assert provider.calls == []


@pytest.mark.asyncio
async def test_the_terminal_timeout_is_a_no_op_however_many_times_it_is_retried():
    scenario = await _scenario()
    session = await _bounded(scenario)
    discussion_id = str(session["discussion_id"])
    await _wait_past()

    service = DiscussionService(provider=ConvergingProvider())
    first = await service.advance(discussion_id)
    settled = await service.get_discussion(discussion_id)
    for _ in range(4):
        again = await service.advance(discussion_id)
        assert again["advanced"] is False
        assert again["session"]["stop_reason"] == "timeout_reached"
    assert await service.get_discussion(discussion_id) == settled
    assert first["session"]["closed_at"] == settled["closed_at"]


# --- the Validation-1 reproduction ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_stuck_started_invocation_can_no_longer_hold_a_discussion_open_forever():
    """The exact Validation-1 failure: turn claimed, invocation STARTED, worker gone.

    No counter on this discussion can ever move again -- counters advance only when a worker
    advances them, and the worker that owned this turn is dead. Before the deadline bound existed
    the discussion stayed ``open`` permanently. Now the wall clock ends it, and the forensic
    evidence of the abandoned call is left exactly where AT-M3.1 put it.
    """
    scenario = await _scenario()
    session = await _bounded(scenario, seconds=SHORT)
    discussion_id = str(session["discussion_id"])
    participants = await _service().get_participants(discussion_id)
    correlation_id = derive_correlation_id(discussion_id, 1, 0)

    store = scenario["store"]
    conn = await store._connect()
    try:
        await conn.execute(
            """
            INSERT INTO discussion_turns
              (discussion_id, round_index, seat_index, speaker_principal_id, addressed_team,
               intent, reasoning_verb, correlation_id, status)
            VALUES ($1,1,0,$2,true,'proposal','propose',$3,'claimed')
            """,
            uuid.UUID(discussion_id),
            participants[0]["principal_id"],
            uuid.UUID(correlation_id),
        )
        invocation_id = await conn.fetchval(
            """
            INSERT INTO reasoning_invocations
              (project_id, thread_id, requested_by_principal_id, reasoning_verb,
               requested_provider_name, provider_mode, round_number, status, correlation_id)
            VALUES ($1,$2,$3,'propose','mock','mock',1,'started',$4)
            RETURNING invocation_id
            """,
            uuid.UUID(scenario["project_id"]),
            session["thread_id"],
            participants[0]["principal_id"],
            uuid.UUID(correlation_id),
        )
    finally:
        await conn.close()

    # Before the deadline the honest answer is still "someone else is resolving this".
    holding = await DiscussionService(provider=ConvergingProvider()).advance(discussion_id)
    assert holding["advanced"] is False
    assert holding["session"]["state"] == "open"

    await _wait_past()

    fresh = DiscussionService(store=DeliberationStore(), provider=CountingProvider())
    for _ in range(5):
        await fresh.advance(discussion_id)
    final = await fresh.get_discussion(discussion_id)
    assert final["state"] == "exhausted"
    assert final["stop_reason"] == "timeout_reached"

    conn = await store._connect()
    try:
        # The abandoned invocation is preserved, not deleted and not re-run.
        row = await conn.fetchrow(
            "SELECT status, completed_at FROM reasoning_invocations WHERE invocation_id=$1",
            invocation_id,
        )
        assert row["status"] == "started" and row["completed_at"] is None
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM reasoning_invocations WHERE correlation_id=$1",
                uuid.UUID(correlation_id),
            )
            == 1
        )
        # And no message was invented to stand in for the reply that never arrived.
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM team_messages WHERE thread_id=$1", session["thread_id"]
            )
            == 0
        )
    finally:
        await conn.close()


# --- the late provider return --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_provider_returning_after_the_deadline_cannot_write_a_message():
    """Started inside the window, landed outside it. The artifact is real; the room has closed."""
    scenario = await _scenario()
    session = await _bounded(scenario, seconds=SHORT)
    discussion_id = str(session["discussion_id"])

    outcome = await DiscussionService(provider=SlowProvider()).advance(discussion_id)
    assert outcome["session"]["state"] == "exhausted"
    assert outcome["session"]["stop_reason"] == "timeout_reached"
    assert "not posted" in outcome["detail"]

    conn = await scenario["store"]._connect()
    try:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM team_messages WHERE thread_id=$1", session["thread_id"]
            )
            == 0
        )
        turn = await conn.fetchrow(
            "SELECT status, message_id, reasoning_invocation_id FROM discussion_turns "
            "WHERE discussion_id=$1",
            uuid.UUID(discussion_id),
        )
        assert turn["status"] == "failed" and turn["message_id"] is None
        # The call really happened, and the record of it stays -- it is the evidence that a
        # provider was paid for a reply the discussion then declined to use.
        assert turn["reasoning_invocation_id"] is not None
        assert (
            await conn.fetchval(
                "SELECT status FROM reasoning_invocations WHERE invocation_id=$1",
                turn["reasoning_invocation_id"],
            )
            == "succeeded"
        )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_a_late_return_cannot_turn_an_expired_discussion_into_a_convergence():
    scenario = await _scenario()
    session = await _bounded(scenario, seconds=SHORT, max_rounds=1)
    discussion_id = str(session["discussion_id"])

    await DiscussionService(provider=SlowProvider()).run(discussion_id)
    final = await _service().get_discussion(discussion_id)
    assert final["state"] == "exhausted"
    assert final["stop_reason"] == "timeout_reached"
    assert final["result_message_id"] is None
    assert final["state"] != "converged"


@pytest.mark.asyncio
async def test_a_message_cannot_be_added_to_a_discussion_that_already_closed():
    """Another worker closed it while this one was reasoning. Same rule, different closer."""
    scenario = await _scenario()
    session = await _bounded(scenario, seconds=120)
    discussion_id = str(session["discussion_id"])

    task = asyncio.create_task(asyncio.to_thread(_advance_in_its_own_loop, discussion_id, 0.8))
    await asyncio.sleep(0.25)
    await _service().cancel(discussion_id)
    outcome = await task

    assert outcome["advanced"] is False
    assert outcome["session"]["stop_reason"] == "cancelled"
    conn = await scenario["store"]._connect()
    try:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM team_messages WHERE thread_id=$1", session["thread_id"]
            )
            == 0
        )
    finally:
        await conn.close()


# --- the database is the clock, and the guard ------------------------------------------------------


@pytest.mark.asyncio
async def test_a_timeout_cannot_be_recorded_before_the_deadline_actually_passes():
    """A worker with a fast clock cannot expire a discussion early: the DB re-checks the write."""
    scenario = await _scenario()
    session = await _bounded(scenario, seconds=120)

    refused = await scenario["store"].close_session(
        session["discussion_id"], stop_reason="timeout_reached"
    )
    assert refused is None
    assert (await _service().get_discussion(str(session["discussion_id"])))["state"] == "open"


@pytest.mark.asyncio
async def test_the_deadline_cannot_be_pushed_out_after_the_discussion_opened():
    scenario = await _scenario()
    session = await _bounded(scenario, seconds=SHORT)
    conn = await scenario["store"]._connect()
    try:
        with pytest.raises(asyncpg.exceptions.RestrictViolationError):
            await conn.execute(
                "UPDATE discussion_sessions SET deadline_at = deadline_at + interval '1 hour' "
                "WHERE discussion_id=$1",
                session["discussion_id"],
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_a_terminal_timeout_cannot_be_rewritten_by_raw_sql():
    scenario = await _scenario()
    session = await _bounded(scenario)
    discussion_id = session["discussion_id"]
    await _wait_past()
    await DiscussionService(provider=ConvergingProvider()).advance(str(discussion_id))

    conn = await scenario["store"]._connect()
    try:
        for sql in (
            "UPDATE discussion_sessions SET state='open', stop_reason=NULL WHERE discussion_id=$1",
            "UPDATE discussion_sessions SET stop_reason='round_limit_reached' "
            "WHERE discussion_id=$1",
            "UPDATE discussion_sessions SET closed_at=NULL WHERE discussion_id=$1",
        ):
            with pytest.raises(asyncpg.exceptions.RestrictViolationError):
                await conn.execute(sql, discussion_id)
        # And "the team agreed, at the deadline" is unrepresentable rather than merely unwritten.
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await conn.execute(
                "INSERT INTO discussion_sessions (project_id, goal_id, thread_id, opened_by, "
                "topic, max_rounds, max_messages, max_invocations, max_turns_per_participant, "
                "deadline_at, state, stop_reason, idempotency_key) "
                "SELECT project_id, goal_id, thread_id, opened_by, topic, max_rounds, "
                "max_messages, max_invocations, max_turns_per_participant, "
                "now() + interval '1 hour', 'converged', 'timeout_reached', $2 "
                "FROM discussion_sessions WHERE discussion_id=$1",
                discussion_id,
                f"probe-{uuid.uuid4().hex}",
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("attempt", [1, 2])
async def test_many_workers_observing_the_same_expiry_produce_one_terminal_transition(attempt):
    scenario = await _scenario()
    session = await _bounded(scenario)
    discussion_id = str(session["discussion_id"])
    await _wait_past()

    async def worker():
        try:
            return await DiscussionService(
                store=DeliberationStore(), provider=CountingProvider()
            ).advance(discussion_id)
        except Exception as exc:  # surfaced as a failure below, never swallowed
            return exc

    results = await asyncio.gather(*(worker() for _ in range(8)))
    assert not [r for r in results if isinstance(r, Exception)]
    assert len([r for r in results if r["advanced"]]) == 1
    assert all(r["session"]["state"] == "exhausted" for r in results)
    assert all(r["session"]["stop_reason"] == "timeout_reached" for r in results)

    conn = await scenario["store"]._connect()
    try:
        # One terminal transition means one closed_at, and no duplicate terminal evidence.
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM discussion_turns WHERE discussion_id=$1",
                uuid.UUID(discussion_id),
            )
            == 0
        )
    finally:
        await conn.close()


# ==================================================================================================
# B2 -- one bound, one reason
# ==================================================================================================


@pytest.mark.asyncio
async def test_the_five_bounds_are_reported_separately_and_never_under_one_anothers_names():
    """Each bound driven to exhaustion on its own, with the other four left wide open."""
    cases = [
        (DiscussionBounds(max_rounds=1, timeout_seconds=120), "round_limit_reached"),
        (DiscussionBounds(max_messages=2, timeout_seconds=120), "message_limit_reached"),
        (DiscussionBounds(max_invocations=2, timeout_seconds=120), "invocation_limit_reached"),
        (
            DiscussionBounds(max_rounds=5, max_turns_per_participant=1, timeout_seconds=120),
            "participant_turn_limit_reached",
        ),
    ]
    for bounds, expected in cases:
        scenario = await _scenario()
        session = await _start(scenario, provider=ContestingProvider(), bounds=bounds)
        final = await _service(ContestingProvider()).run(str(session["discussion_id"]))
        assert final["session"]["state"] == "exhausted", expected
        assert final["session"]["stop_reason"] == expected, (
            f"expected {expected}, got {final['session']['stop_reason']}"
        )

    scenario = await _scenario()
    session = await _bounded(scenario, seconds=SHORT, max_rounds=20)
    await _wait_past()
    final = await _service(ContestingProvider()).run(str(session["discussion_id"]))
    assert final["session"]["stop_reason"] == "timeout_reached"


@pytest.mark.asyncio
async def test_a_covered_but_too_small_team_is_a_participant_failure_not_a_coverage_failure():
    covered = await _scenario(agent_keys=("qa-agent",))
    session = await _start(covered, caps=("verify_quality",))
    assert session["stop_reason"] == "insufficient_participants"

    uncovered = await _scenario(agent_keys=("qa-agent", "design-review-agent"))
    session = await _start(uncovered, caps=("verify_quality", "review_design", "generate_code"))
    assert session["stop_reason"] == "insufficient_capability_coverage"


@pytest.mark.asyncio
async def test_the_wall_clock_outranks_a_count_bound_that_became_true_at_the_same_moment():
    """Precedence, proven rather than declared: both conditions hold, the timeout is recorded."""
    scenario = await _scenario()
    session = await _bounded(scenario, seconds=SHORT, max_rounds=1, max_messages=1)
    await _wait_past()

    final = await _service(ContestingProvider()).run(str(session["discussion_id"]))
    assert final["session"]["stop_reason"] == "timeout_reached"


# ==================================================================================================
# D1 -- exact-revision discussion semantics
# ==================================================================================================


async def _supersede(scenario, predecessor_id: str) -> str:
    planning = PlanningStore()
    successor = await planning.create_successor_revision(
        {
            "goal_id": scenario["goal_id"],
            "expected_current_revision_id": predecessor_id,
            "created_by": scenario["opened_by"],
            "reason": "team_decision",
            "plan": {**PLAN, "objective": "deliver the reporting slice, narrowed"},
        }
    )
    return str(successor["plan_revision_id"])


@pytest.mark.asyncio
async def test_a_default_start_binds_the_current_revision_and_reads_as_current():
    scenario = await _scenario()
    session = await _start(scenario)
    service = _service()

    assert str(session["plan_revision_id"]) == scenario["plan_revision_id"]
    currency = await service.plan_currency(session)
    assert currency["plan_revision_is_current"] is True
    assert currency["current_plan_revision_id"] == scenario["plan_revision_id"]


@pytest.mark.asyncio
async def test_opening_against_an_already_superseded_revision_is_refused_and_leaves_nothing():
    scenario = await _scenario()
    stale = scenario["plan_revision_id"]
    await _supersede(scenario, stale)

    conn = await scenario["store"]._connect()
    try:
        threads_before = await conn.fetchval(
            "SELECT count(*) FROM conversation_threads WHERE project_id=$1",
            uuid.UUID(scenario["project_id"]),
        )
    finally:
        await conn.close()

    with pytest.raises(DiscussionStateError) as exc:
        await _service().start_discussion(
            project_id=scenario["project_id"],
            goal_id=scenario["goal_id"],
            topic="should we still do it this way?",
            opened_by=scenario["opened_by"],
            required_capabilities=CAPS,
            plan_revision_id=stale,
        )
    assert "superseded" in str(exc.value)

    # Transactional in the strongest sense: the refusal happens before anything is written, so
    # there is no discussion row, no participant and no orphan thread to clean up.
    assert await _sessions_for_goal(scenario["store"], scenario["goal_id"]) == 0
    conn = await scenario["store"]._connect()
    try:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM conversation_threads WHERE project_id=$1",
                uuid.UUID(scenario["project_id"]),
            )
            == threads_before
        )
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM discussion_participants dp "
                "JOIN discussion_sessions ds USING (discussion_id) WHERE ds.goal_id=$1",
                uuid.UUID(scenario["goal_id"]),
            )
            == 0
        )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_the_default_path_still_resolves_the_current_revision_after_a_supersession():
    scenario = await _scenario()
    successor = await _supersede(scenario, scenario["plan_revision_id"])
    session = await _start(scenario)
    assert str(session["plan_revision_id"]) == successor


@pytest.mark.asyncio
async def test_a_successor_appearing_mid_discussion_neither_terminates_nor_rebinds_it():
    scenario = await _scenario()
    session = await _start(scenario, provider=ContestingProvider())
    discussion_id = str(session["discussion_id"])
    service = _service(ContestingProvider())
    await service.advance(discussion_id)

    successor = await _supersede(scenario, scenario["plan_revision_id"])

    mid = await service.get_discussion(discussion_id)
    assert mid["state"] == "open", "a legitimate replan must not kill an in-flight deliberation"
    assert str(mid["plan_revision_id"]) == scenario["plan_revision_id"], "the binding never moves"
    assert mid["stop_reason"] is None

    currency = await service.plan_currency(mid)
    assert currency["plan_revision_is_current"] is False
    assert currency["current_plan_revision_id"] == successor

    # It keeps going, under its own bounds, and ends for one of its own reasons -- never for a
    # staleness reason, because no such terminal state exists.
    final = await service.run(discussion_id)
    assert final["session"]["state"] == "exhausted"
    assert final["session"]["stop_reason"] == "round_limit_reached"


@pytest.mark.asyncio
async def test_a_restarted_service_resumes_against_the_original_revision():
    scenario = await _scenario()
    session = await _start(scenario, provider=ContestingProvider())
    discussion_id = str(session["discussion_id"])
    first = _service(ContestingProvider())
    await first.advance(discussion_id)
    await _supersede(scenario, scenario["plan_revision_id"])
    del first

    fresh = DiscussionService(store=DeliberationStore(), provider=ContestingProvider())
    resumed = await fresh.get_discussion(discussion_id)
    assert str(resumed["plan_revision_id"]) == scenario["plan_revision_id"]
    assert resumed["current_round"] == 1

    outcome = await fresh.advance(discussion_id)
    assert outcome["advanced"] is True
    assert outcome["turn"]["seat_index"] == 1
    final = await fresh.run(discussion_id)
    assert final["session"]["state"] == "exhausted"


@pytest.mark.asyncio
async def test_a_discussion_can_converge_honestly_about_a_revision_that_is_no_longer_current():
    scenario = await _scenario()
    session = await _start(scenario, provider=ConvergingProvider(), bounds=DiscussionBounds())
    discussion_id = str(session["discussion_id"])
    service = _service(ConvergingProvider())
    await service.advance(discussion_id)
    await _supersede(scenario, scenario["plan_revision_id"])

    final = await service.run(discussion_id)
    assert final["session"]["state"] == "converged"
    assert final["session"]["stop_reason"] == "convergence_reached"
    assert final["session"]["result_message_id"] is not None
    # True about revision N, and the read surface says plainly that N is not the current plan.
    assert (await service.plan_currency(final["session"]))["plan_revision_is_current"] is False


@pytest.mark.asyncio
async def test_a_stale_convergence_cannot_produce_a_successor_through_the_m3_2_cas():
    """The M3.4 precondition, proven today against the M3.2 primitive M3.4 must use."""
    scenario = await _scenario()
    session = await _start(scenario, provider=ConvergingProvider())
    discussion_id = str(session["discussion_id"])
    final = await _service(ConvergingProvider()).run(discussion_id)
    assert final["session"]["state"] == "converged"

    planning = PlanningStore()
    before = await planning.get_revision(scenario["plan_revision_id"])
    real_successor = await _supersede(scenario, scenario["plan_revision_id"])

    with pytest.raises(StalePlanRevisionError):
        await planning.create_successor_revision(
            {
                "goal_id": scenario["goal_id"],
                "expected_current_revision_id": str(final["session"]["plan_revision_id"]),
                "created_by": scenario["opened_by"],
                "reason": "team_decision",
                "trace_ref": str(final["session"]["result_message_id"]),
                "plan": PLAN,
            }
        )

    revisions = await planning.list_revisions(scenario["goal_id"])
    assert [str(r["plan_revision_id"]) for r in revisions] == [
        scenario["plan_revision_id"],
        real_successor,
    ]
    # And the historical revision the discussion was about is untouched, byte for byte.
    assert await planning.get_revision(scenario["plan_revision_id"]) == before


@pytest.mark.asyncio
async def test_the_same_cas_succeeds_while_the_discussion_s_revision_is_still_current():
    """The control: the precondition refuses stale input, it does not refuse everything."""
    scenario = await _scenario()
    session = await _start(scenario, provider=ConvergingProvider())
    final = await _service(ConvergingProvider()).run(str(session["discussion_id"]))
    assert final["session"]["state"] == "converged"

    planning = PlanningStore()
    successor = await planning.create_successor_revision(
        {
            "goal_id": scenario["goal_id"],
            "expected_current_revision_id": str(final["session"]["plan_revision_id"]),
            "created_by": scenario["opened_by"],
            "reason": "team_decision",
            "trace_ref": str(final["session"]["result_message_id"]),
            "plan": PLAN,
        }
    )
    assert str(successor["supersedes_revision_id"]) == scenario["plan_revision_id"]
    assert (await _service().plan_currency(final["session"]))["plan_revision_is_current"] is False


@pytest.mark.asyncio
async def test_two_consumers_racing_the_same_current_revision_produce_exactly_one_successor():
    scenario = await _scenario()
    planning = PlanningStore()

    async def consume(tag: str):
        try:
            return await planning.create_successor_revision(
                {
                    "goal_id": scenario["goal_id"],
                    "expected_current_revision_id": scenario["plan_revision_id"],
                    "created_by": scenario["opened_by"],
                    "reason": "team_decision",
                    "plan": {**PLAN, "objective": tag},
                }
            )
        except StalePlanRevisionError as exc:
            return exc

    results = await asyncio.gather(*(consume(f"c{i}") for i in range(4)))
    winners = [r for r in results if not isinstance(r, Exception)]
    losers = [r for r in results if isinstance(r, StalePlanRevisionError)]
    assert len(winners) == 1
    assert len(losers) == 3
    assert len(await planning.list_revisions(scenario["goal_id"])) == 2


@pytest.mark.asyncio
async def test_a_discussion_bound_to_no_revision_is_current_only_while_the_goal_has_no_plan():
    """Deciding what the FIRST plan should be is itself a discussion, and it can go stale too."""
    store = await _scenario()  # reuse the fixture only for its store/project scaffolding
    conn = await store["store"]._connect()
    try:
        opener = str(
            await conn.fetchval(
                "INSERT INTO actor_principals (principal_type,display_name) VALUES ('human',$1) "
                "RETURNING principal_id",
                f"m33-noplan-{uuid.uuid4().hex[:6]}",
            )
        )
    finally:
        await conn.close()

    planning = PlanningStore()
    goal = await planning.create_goal(
        {
            "project_id": store["project_id"],
            "statement": "a goal with no plan",
            "created_by": opener,
        }
    )
    goal_id = str(goal["goal_id"])

    session = await _service().start_discussion(
        project_id=store["project_id"],
        goal_id=goal_id,
        topic="what should the first plan be?",
        opened_by=opener,
        required_capabilities=CAPS,
    )
    assert session["plan_revision_id"] is None
    service = _service()
    assert (await service.plan_currency(session))["plan_revision_is_current"] is True

    await planning.create_initial_revision({"goal_id": goal_id, "created_by": opener, "plan": PLAN})
    currency = await service.plan_currency(await service.get_discussion(session["discussion_id"]))
    assert currency["plan_revision_is_current"] is False
    assert currency["current_plan_revision_id"] is not None


@pytest.mark.asyncio
async def test_currency_is_derived_and_stored_nowhere():
    scenario = await _scenario()
    conn = await scenario["store"]._connect()
    try:
        columns = [
            r["column_name"]
            for r in await conn.fetch(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='discussion_sessions'"
            )
        ]
    finally:
        await conn.close()
    for forbidden in ("stale", "is_current", "current_plan", "plan_current", "superseded"):
        assert not any(forbidden in c for c in columns), forbidden
    assert "plan_revision_id" in columns


@pytest.mark.asyncio
async def test_none_of_these_paths_writes_a_team_decision():
    """M3.3 discusses. Staleness, timeouts and convergence alike record no decision."""
    scenario = await _scenario()
    session = await _start(scenario, provider=ConvergingProvider())
    await _service(ConvergingProvider()).run(str(session["discussion_id"]))
    await _supersede(scenario, scenario["plan_revision_id"])

    expired = await _bounded(scenario, seconds=SHORT, key=f"expired-{uuid.uuid4().hex}")
    await _wait_past()
    await DiscussionService(provider=ConvergingProvider()).advance(str(expired["discussion_id"]))

    conn = await scenario["store"]._connect()
    try:
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM team_decisions WHERE project_id=$1",
                uuid.UUID(scenario["project_id"]),
            )
            == 0
        )
    finally:
        await conn.close()
