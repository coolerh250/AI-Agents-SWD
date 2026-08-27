"""Step AT-M3.3 -- the discussion runtime against a real PostgreSQL.

Follows the store-test convention of tests/test_at_m2_team_store.py and
tests/test_at_m3_2_planning_store.py: skip when no database is reachable, so the suite stays
runnable on a workstation while still exercising the real asyncpg path wherever migration 039 has
been applied.

These are the assertions an in-memory fake cannot make honestly:

* that eight independent connections racing the SAME next turn produce exactly one canonical turn,
  one message and one reasoning invocation -- the load-bearing property of the whole slice;
* that a discussion resumes in a different process object graph from durable rows alone;
* that a closed discussion cannot be reopened, and that "ran out of rounds" cannot be written as
  "converged", even by a caller holding a raw psql session.
"""

from __future__ import annotations

import asyncio
import uuid

import asyncpg
import pytest

from shared.sdk.agent_deliberation.models import (
    DiscussionBounds,
    DiscussionParticipantError,
    derive_correlation_id,
)
from shared.sdk.agent_deliberation.service import DiscussionService
from shared.sdk.agent_deliberation.store import DeliberationStore
from shared.sdk.agent_planning.store import PlanningStore
from shared.sdk.agent_reasoning.models import (
    CritiqueArtifact,
    DecisionSummaryArtifact,
    ProposalArtifact,
)
from shared.sdk.agent_reasoning.provider import ReasoningProviderError
from shared.sdk.agent_team.service import TeamService
from shared.sdk.agent_team.store import TeamStore

_DB_SKIP = "no reachable PostgreSQL with migration 039 applied; skipping discussion store test"

PLAN = {
    "objective": "deliver the reporting slice",
    "steps": [{"step_id": "s1", "title": "define the contract", "depends_on": []}],
    "constraints": [],
    "acceptance_criteria": ["a reviewer can read one report"],
}

# Three seeded agents whose capabilities do not overlap, so a required-capability list of length
# three seats three distinct principals.
CAPS = ("plan_project", "verify_quality", "review_design")


# --- deterministic test providers -----------------------------------------------------------------


class ConvergingProvider:
    """Deterministic, and unlike the mock provider it raises NO standing concern.

    The shipped mock always declares ``mock_provider_no_live_model`` as a concern, so a mock-mode
    discussion honestly never converges. Convergence still has to be provable, so this provider
    supplies the concern-free critique the real signal needs -- injected explicitly, never
    substituted for a refused provider.
    """

    name = "test-converging"
    mode = "mock"

    def propose(self, request) -> ProposalArtifact:
        return ProposalArtifact(
            summary="start from the report contract",
            rationale_summary="it is the only part the acceptance criteria name",
            recommendation="define the contract first",
        )

    def critique(self, request) -> CritiqueArtifact:
        return CritiqueArtifact(
            summary="the proposal covers the acceptance criteria",
            rationale_summary="checked against the goal",
            concerns=(),
            questions=(),
            recommendation="proceed",
        )

    def summarize_decision(self, request) -> DecisionSummaryArtifact:
        return DecisionSummaryArtifact(
            summary="the team is aligned on starting from the report contract",
            rationale_summary="no concern remained outstanding",
            options_considered=tuple(request.context.get("options_considered") or ("proceed",)),
            selected_option="define the contract first",
        )


class ContestingProvider(ConvergingProvider):
    """Always raises a concern, so the discussion runs to its bound. Mirrors mock-mode behaviour."""

    name = "test-contesting"

    def critique(self, request) -> CritiqueArtifact:
        return CritiqueArtifact(
            summary="the proposal leaves the rollback path open",
            rationale_summary="checked against the goal's constraints",
            concerns=("rollback path undefined",),
            questions=(),
            recommendation="revise",
        )


class FailingProvider:
    name = "test-failing"
    mode = "mock"

    def propose(self, request):
        raise ReasoningProviderError("test_provider_refused:propose")

    def critique(self, request):
        raise ReasoningProviderError("test_provider_refused:critique")

    def summarize_decision(self, request):
        raise ReasoningProviderError("test_provider_refused:summarize_decision")


class AuditRecorder:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def build_audit_event(self, **kw):
        self.events.append(kw)
        return kw

    async def write_audit_event(self, event):
        return "audit-ref"


# --- fixtures -------------------------------------------------------------------------------------


async def _store_or_skip() -> DeliberationStore:
    store = DeliberationStore()
    try:
        conn = await store._connect()
    except Exception:
        pytest.skip(_DB_SKIP)
    try:
        for table in ("discussion_sessions", "discussion_turns", "discussion_participants"):
            if await conn.fetchval("SELECT to_regclass($1)", f"public.{table}") is None:
                pytest.skip(_DB_SKIP)
    finally:
        await conn.close()
    return store


async def _scenario(*, agent_keys=("project-planner-agent", "qa-agent", "design-review-agent")):
    """A project with a real team, a Goal, and a current PlanRevision."""
    store = await _store_or_skip()
    conn = await store._connect()
    try:
        project_id = str(
            await conn.fetchval(
                "INSERT INTO projects (title) VALUES ($1) RETURNING id",
                f"m33-{uuid.uuid4().hex[:8]}",
            )
        )
        opener = str(
            await conn.fetchval(
                "INSERT INTO actor_principals (principal_type,display_name) "
                "VALUES ('human',$1) RETURNING principal_id",
                f"m33-opener-{uuid.uuid4().hex[:6]}",
            )
        )
    finally:
        await conn.close()

    await TeamService().form_team(project_id, goal_ref="m33", agent_keys=agent_keys)

    planning = PlanningStore()
    goal = await planning.create_goal(
        {
            "project_id": project_id,
            "statement": "deliver a reporting slice a reviewer can read",
            "acceptance_criteria": ["a reviewer can read one report"],
            "constraints": ["non-production only"],
            "created_by": opener,
        }
    )
    revision = await planning.create_initial_revision(
        {"goal_id": str(goal["goal_id"]), "created_by": opener, "plan": PLAN}
    )
    return {
        "store": store,
        "project_id": project_id,
        "opened_by": opener,
        "goal_id": str(goal["goal_id"]),
        "plan_revision_id": str(revision["plan_revision_id"]),
    }


def _service(provider=None, audit=None) -> DiscussionService:
    return DiscussionService(provider=provider, audit_client=audit)


async def _start(scenario, *, provider=None, audit=None, caps=CAPS, bounds=None, key=None):
    return await _service(provider, audit).start_discussion(
        project_id=scenario["project_id"],
        goal_id=scenario["goal_id"],
        topic="what is the smallest slice that satisfies the goal?",
        opened_by=scenario["opened_by"],
        required_capabilities=caps,
        bounds=bounds,
        idempotency_key=key,
    )


# --- creation, binding, thread reuse ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_discussion_binds_to_its_project_goal_and_current_plan_revision():
    scenario = await _scenario()
    session = await _start(scenario)

    assert str(session["project_id"]) == scenario["project_id"]
    assert str(session["goal_id"]) == scenario["goal_id"]
    # Resolved from lineage, not supplied by the caller.
    assert str(session["plan_revision_id"]) == scenario["plan_revision_id"]
    assert session["state"] == "open" and session["stop_reason"] is None


@pytest.mark.asyncio
async def test_the_discussion_reuses_a_conversation_thread_rather_than_a_new_hierarchy():
    scenario = await _scenario()
    session = await _start(scenario)
    conn = await scenario["store"]._connect()
    try:
        thread = await conn.fetchrow(
            "SELECT project_id, goal_ref, thread_type, state FROM conversation_threads "
            "WHERE thread_id=$1",
            session["thread_id"],
        )
        # Exactly one discussion per thread, enforced by the schema.
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM discussion_sessions WHERE thread_id=$1", session["thread_id"]
            )
            == 1
        )
    finally:
        await conn.close()
    assert str(thread["project_id"]) == scenario["project_id"]
    assert thread["goal_ref"] == scenario["goal_id"]
    assert thread["thread_type"] == "planning"


@pytest.mark.asyncio
async def test_a_revision_from_another_goal_is_rejected():
    scenario = await _scenario()
    other = await _scenario()
    with pytest.raises(Exception):
        await _service().start_discussion(
            project_id=scenario["project_id"],
            goal_id=scenario["goal_id"],
            topic="t",
            opened_by=scenario["opened_by"],
            required_capabilities=CAPS,
            plan_revision_id=other["plan_revision_id"],
        )


@pytest.mark.asyncio
async def test_a_goal_from_another_project_is_rejected():
    scenario = await _scenario()
    other = await _scenario()
    with pytest.raises(Exception):
        await _service().start_discussion(
            project_id=scenario["project_id"],
            goal_id=other["goal_id"],
            topic="t",
            opened_by=scenario["opened_by"],
            required_capabilities=CAPS,
        )


# --- participants -----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_participants_come_from_the_project_team_and_carry_their_capability_match():
    scenario = await _scenario()
    session = await _start(scenario)
    service = _service()
    participants = await service.get_participants(session["discussion_id"])

    assert len(participants) == 3
    assert [p["seat_index"] for p in participants] == [0, 1, 2]
    roster = {m["agent_principal_id"] for m in await TeamStore().list_team(scenario["project_id"])}
    for participant in participants:
        assert str(participant["principal_id"]) in {str(r) for r in roster}
        assert participant["matched_capabilities"], "the capability match must be explicit"
        assert set(participant["matched_capabilities"]) <= set(CAPS)
        assert participant["selection_reason"]


@pytest.mark.asyncio
async def test_one_agent_covering_two_capabilities_takes_one_seat_and_both_capabilities():
    scenario = await _scenario(agent_keys=("requirement-agent", "qa-agent"))
    session = await _start(
        scenario, caps=("analyze_requirements", "clarify_requirements", "verify_quality")
    )
    participants = await _service().get_participants(session["discussion_id"])
    # requirement-agent declares both requirement capabilities; it is seated once.
    assert len(participants) == 2
    requirement = next(p for p in participants if p["agent_key"] == "requirement-agent")
    assert set(requirement["matched_capabilities"]) == {
        "analyze_requirements",
        "clarify_requirements",
    }


@pytest.mark.asyncio
async def test_an_uncovered_capability_fails_closed_with_a_durable_terminal_record():
    scenario = await _scenario(agent_keys=("qa-agent", "design-review-agent"))
    session = await _start(scenario, caps=("verify_quality", "review_design", "generate_code"))

    assert session["state"] == "failed"
    assert session["stop_reason"] == "insufficient_capability_coverage"
    # The request left evidence rather than evaporating.
    assert await _service().get_discussion(session["discussion_id"]) is not None


@pytest.mark.asyncio
async def test_a_single_viable_participant_is_not_a_discussion():
    scenario = await _scenario(agent_keys=("qa-agent",))
    session = await _start(scenario, caps=("verify_quality",))
    assert session["state"] == "failed"
    assert session["stop_reason"] == "insufficient_capability_coverage"


@pytest.mark.asyncio
async def test_a_production_effect_capability_is_never_seated():
    scenario = await _scenario()
    session = await _start(scenario, caps=("plan_project", "verify_quality", "deploy_production"))
    # The router refers it to the human approval boundary; the discussion does not route around it.
    assert session["state"] == "failed"
    assert session["stop_reason"] == "insufficient_capability_coverage"


@pytest.mark.asyncio
async def test_a_discussion_must_name_the_capabilities_it_needs():
    scenario = await _scenario()
    with pytest.raises(DiscussionParticipantError):
        await _service().start_discussion(
            project_id=scenario["project_id"],
            goal_id=scenario["goal_id"],
            topic="t",
            opened_by=scenario["opened_by"],
            required_capabilities=(),
        )


@pytest.mark.asyncio
async def test_a_participant_that_leaves_mid_discussion_stops_the_discussion():
    scenario = await _scenario()
    session = await _start(scenario, provider=ContestingProvider())
    service = _service(ContestingProvider())
    await service.advance(session["discussion_id"])  # seat 0 proposes

    participants = await service.get_participants(session["discussion_id"])
    conn = await scenario["store"]._connect()
    try:
        await conn.execute(
            "UPDATE project_team_memberships SET membership_state='paused' "
            "WHERE project_id=$1 AND agent_principal_id=$2",
            uuid.UUID(scenario["project_id"]),
            participants[1]["principal_id"],
        )
    finally:
        await conn.close()

    outcome = await service.advance(session["discussion_id"])
    assert outcome["session"]["state"] == "failed"
    assert outcome["session"]["stop_reason"] == "participant_unavailable"


# --- bounded deliberation ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_contested_discussion_ends_at_its_round_limit_and_is_never_called_consensus():
    scenario = await _scenario()
    session = await _start(
        scenario, provider=ContestingProvider(), bounds=DiscussionBounds(max_rounds=2)
    )
    service = _service(ContestingProvider())
    final = await service.run(session["discussion_id"])

    assert final["session"]["state"] == "exhausted"
    assert final["session"]["stop_reason"] == "round_limit_reached"
    assert final["session"]["state"] != "converged"
    assert final["session"]["result_message_id"] is None, "exhaustion produces no M3.4 result"
    assert final["session"]["current_round"] == 2


@pytest.mark.asyncio
async def test_the_shipped_mock_provider_never_fabricates_consensus():
    # The default provider declares a standing concern on every critique, so a mock-mode
    # discussion is honestly unresolved. Running out of rounds is the correct outcome.
    scenario = await _scenario()
    session = await _start(scenario, bounds=DiscussionBounds(max_rounds=2))
    final = await _service().run(session["discussion_id"])
    assert final["session"]["state"] == "exhausted"
    assert final["session"]["stop_reason"] == "round_limit_reached"


@pytest.mark.asyncio
async def test_the_message_budget_stops_the_discussion():
    scenario = await _scenario()
    session = await _start(
        scenario,
        provider=ContestingProvider(),
        bounds=DiscussionBounds(max_rounds=5, max_messages=2),
    )
    final = await _service(ContestingProvider()).run(session["discussion_id"])
    assert final["session"]["state"] == "exhausted"
    assert final["session"]["stop_reason"] == "message_limit_reached"
    assert final["session"]["messages_posted"] <= 2


@pytest.mark.asyncio
async def test_the_reasoning_invocation_budget_stops_the_discussion():
    scenario = await _scenario()
    session = await _start(
        scenario,
        provider=ContestingProvider(),
        bounds=DiscussionBounds(max_rounds=5, max_messages=50, max_invocations=2),
    )
    final = await _service(ContestingProvider()).run(session["discussion_id"])
    assert final["session"]["state"] == "exhausted"
    assert final["session"]["stop_reason"] == "invocation_limit_reached"
    assert final["session"]["invocations_started"] <= 2


@pytest.mark.asyncio
async def test_the_per_participant_turn_cap_is_enforced():
    scenario = await _scenario()
    session = await _start(
        scenario,
        provider=ContestingProvider(),
        bounds=DiscussionBounds(max_rounds=5, max_turns_per_participant=1),
    )
    final = await _service(ContestingProvider()).run(session["discussion_id"])
    assert final["session"]["is_terminal"] if "is_terminal" in final["session"] else True
    assert final["session"]["state"] == "exhausted"
    participants = await _service().get_participants(session["discussion_id"])
    assert all(p["turns_taken"] <= 1 for p in participants)


@pytest.mark.asyncio
async def test_bounds_cannot_be_raised_after_the_discussion_opened():
    scenario = await _scenario()
    session = await _start(scenario, bounds=DiscussionBounds(max_rounds=2))
    conn = await scenario["store"]._connect()
    try:
        with pytest.raises(asyncpg.exceptions.RestrictViolationError):
            await conn.execute(
                "UPDATE discussion_sessions SET max_rounds=20 WHERE discussion_id=$1",
                session["discussion_id"],
            )
    finally:
        await conn.close()


# --- turn model ---------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_turns_are_addressed_and_recorded_as_team_messages():
    scenario = await _scenario()
    session = await _start(scenario, provider=ContestingProvider())
    service = _service(ContestingProvider())
    for _ in range(3):
        await service.advance(session["discussion_id"])

    turns = await service.get_turns(session["discussion_id"])
    messages = await service.get_messages(session["discussion_id"])
    participants = await service.get_participants(session["discussion_id"])

    assert [t["seat_index"] for t in turns] == [0, 1, 2]
    assert len(messages) == 3

    opener = turns[0]
    assert opener["addressed_team"] is True and opener["addressed_principal_id"] is None
    assert opener["intent"] == "proposal"
    for turn in turns[1:]:
        assert turn["addressed_team"] is False
        assert str(turn["addressed_principal_id"]) == str(participants[0]["principal_id"])
        assert turn["intent"] == "challenge"

    by_id = {str(m["message_id"]): m for m in messages}
    assert by_id[str(opener["message_id"])]["message_type"] == "proposal"
    assert by_id[str(turns[1]["message_id"])]["message_type"] == "challenge"
    assert by_id[str(turns[1]["message_id"])]["recipient_principal_id"] is not None


@pytest.mark.asyncio
async def test_every_turn_correlates_to_one_reasoning_invocation_at_its_own_slot():
    scenario = await _scenario()
    session = await _start(scenario, provider=ContestingProvider())
    service = _service(ContestingProvider())
    await service.advance(session["discussion_id"])
    await service.advance(session["discussion_id"])

    turns = await service.get_turns(session["discussion_id"])
    conn = await scenario["store"]._connect()
    try:
        for turn in turns:
            expected = derive_correlation_id(
                str(session["discussion_id"]), turn["round_index"], turn["seat_index"]
            )
            assert str(turn["correlation_id"]) == expected
            row = await conn.fetchrow(
                "SELECT correlation_id, provider_mode, status, thread_id "
                "FROM reasoning_invocations WHERE invocation_id=$1",
                turn["reasoning_invocation_id"],
            )
            assert row is not None
            assert str(row["correlation_id"]) == expected
            assert row["status"] == "succeeded"
            assert str(row["thread_id"]) == str(session["thread_id"])
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_a_recorded_turn_cannot_be_rewritten():
    scenario = await _scenario()
    session = await _start(scenario, provider=ContestingProvider())
    await _service(ContestingProvider()).advance(session["discussion_id"])
    turn = (await _service().get_turns(session["discussion_id"]))[0]

    conn = await scenario["store"]._connect()
    try:
        for column, value in (("intent", "support"), ("status", "failed")):
            with pytest.raises(asyncpg.exceptions.RestrictViolationError):
                await conn.execute(
                    f"UPDATE discussion_turns SET {column}=$2 WHERE turn_id=$1",
                    turn["turn_id"],
                    value,
                )
        with pytest.raises(asyncpg.exceptions.RestrictViolationError):
            await conn.execute(
                "UPDATE discussion_turns SET seat_index=9 WHERE turn_id=$1", turn["turn_id"]
            )
    finally:
        await conn.close()


# --- reasoning failure -------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_refused_provider_stops_the_discussion_and_invents_no_message():
    scenario = await _scenario()
    session = await _start(scenario, provider=FailingProvider())
    outcome = await _service(FailingProvider()).advance(session["discussion_id"])

    assert outcome["session"]["state"] == "failed"
    assert outcome["session"]["stop_reason"] == "reasoning_provider_failure"
    assert await _service().get_messages(session["discussion_id"]) == []
    turns = await _service().get_turns(session["discussion_id"])
    assert [t["status"] for t in turns] == ["failed"]
    assert turns[0]["message_id"] is None


@pytest.mark.asyncio
async def test_a_failed_discussion_records_the_failed_reasoning_invocation():
    scenario = await _scenario()
    session = await _start(scenario, provider=FailingProvider())
    await _service(FailingProvider()).advance(session["discussion_id"])
    turn = (await _service().get_turns(session["discussion_id"]))[0]

    conn = await scenario["store"]._connect()
    try:
        row = await conn.fetchrow(
            "SELECT status, failure_category FROM reasoning_invocations WHERE invocation_id=$1",
            turn["reasoning_invocation_id"],
        )
    finally:
        await conn.close()
    assert row["status"] == "failed"
    assert row["failure_category"] is not None


# --- convergence ---------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_discussion_with_nothing_outstanding_converges_and_leaves_an_m34_result():
    scenario = await _scenario()
    session = await _start(scenario, provider=ConvergingProvider())
    final = await _service(ConvergingProvider()).run(session["discussion_id"])

    assert final["session"]["state"] == "converged"
    assert final["session"]["stop_reason"] == "convergence_reached"
    assert final["session"]["result_message_id"] is not None
    # It converged in round 1, well inside the bound -- convergence is not exhaustion.
    assert final["session"]["current_round"] == 1

    messages = await _service().get_messages(session["discussion_id"])
    result = next(
        m for m in messages if str(m["message_id"]) == str(final["session"]["result_message_id"])
    )
    assert result["message_type"] == "message", "the summary is not a decision_summary"
    assert result["artifact_refs"]["intent"] == "convergence_summary"


@pytest.mark.asyncio
async def test_convergence_records_no_team_decision_and_touches_no_plan_revision():
    scenario = await _scenario()
    session = await _start(scenario, provider=ConvergingProvider())
    before = await PlanningStore().get_revision(scenario["plan_revision_id"])
    await _service(ConvergingProvider()).run(session["discussion_id"])
    after = await PlanningStore().get_revision(scenario["plan_revision_id"])

    conn = await scenario["store"]._connect()
    try:
        decisions = await conn.fetchval(
            "SELECT count(*) FROM team_decisions WHERE project_id=$1",
            uuid.UUID(scenario["project_id"]),
        )
        revisions = await conn.fetchval(
            "SELECT count(*) FROM plan_revisions WHERE goal_id=$1",
            uuid.UUID(scenario["goal_id"]),
        )
    finally:
        await conn.close()

    assert decisions == 0, "M3.3 records no TeamDecision -- that is M3.4"
    assert revisions == 1, "M3.3 creates no successor PlanRevision"
    assert before == after, "the revision under discussion is not modified by discussing it"


@pytest.mark.asyncio
async def test_a_terminal_discussion_cannot_be_reopened_or_relabelled():
    scenario = await _scenario()
    session = await _start(scenario, provider=ConvergingProvider())
    final = await _service(ConvergingProvider()).run(session["discussion_id"])
    discussion_id = final["session"]["discussion_id"]

    conn = await scenario["store"]._connect()
    try:
        for sql, args in (
            (
                "UPDATE discussion_sessions SET state='open', stop_reason=NULL WHERE discussion_id=$1",
                (),
            ),
            ("UPDATE discussion_sessions SET turns_taken=99 WHERE discussion_id=$1", ()),
        ):
            with pytest.raises(asyncpg.exceptions.RestrictViolationError):
                await conn.execute(sql, discussion_id, *args)
        # And the state/reason pairing itself is unrepresentable, not merely unwritten.
        with pytest.raises(asyncpg.exceptions.CheckViolationError):
            await conn.execute(
                "INSERT INTO discussion_sessions (project_id, goal_id, thread_id, opened_by, "
                "topic, max_rounds, max_messages, max_invocations, max_turns_per_participant, "
                "state, stop_reason, idempotency_key) "
                "SELECT project_id, goal_id, thread_id, opened_by, topic, max_rounds, "
                "max_messages, max_invocations, max_turns_per_participant, 'converged', "
                "'round_limit_reached', $2 FROM discussion_sessions WHERE discussion_id=$1",
                discussion_id,
                f"probe-{uuid.uuid4().hex}",
            )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_advancing_a_terminal_discussion_changes_nothing():
    scenario = await _scenario()
    session = await _start(scenario, provider=ConvergingProvider())
    service = _service(ConvergingProvider())
    await service.run(session["discussion_id"])
    before = await service.get_discussion(session["discussion_id"])

    outcome = await service.advance(session["discussion_id"])
    assert outcome["advanced"] is False
    assert await service.get_discussion(session["discussion_id"]) == before


@pytest.mark.asyncio
async def test_a_cancelled_discussion_is_cancelled_not_converged():
    scenario = await _scenario()
    session = await _start(scenario, provider=ContestingProvider())
    cancelled = await _service().cancel(session["discussion_id"])
    assert cancelled["state"] == "cancelled"
    assert cancelled["stop_reason"] == "cancelled"
    assert cancelled["result_message_id"] is None
    # Cancelling twice is a no-op, not a second closure.
    assert await _service().cancel(session["discussion_id"]) is None


# --- idempotency, retry, concurrency -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_duplicate_start_returns_the_same_discussion():
    scenario = await _scenario()
    first = await _start(scenario)
    second = await _start(scenario)
    assert str(first["discussion_id"]) == str(second["discussion_id"])

    conn = await scenario["store"]._connect()
    try:
        sessions = await conn.fetchval(
            "SELECT count(*) FROM discussion_sessions WHERE goal_id=$1",
            uuid.UUID(scenario["goal_id"]),
        )
        # And no orphan thread was left behind by the losing attempt.
        threads = await conn.fetchval(
            "SELECT count(*) FROM conversation_threads WHERE goal_ref=$1", scenario["goal_id"]
        )
    finally:
        await conn.close()
    assert sessions == 1
    assert threads == 1


@pytest.mark.asyncio
async def test_concurrent_duplicate_starts_produce_exactly_one_discussion():
    scenario = await _scenario()
    results = await asyncio.gather(
        *(_start(scenario, key="fixed-key") for _ in range(8)), return_exceptions=True
    )
    ok = [r for r in results if not isinstance(r, Exception)]
    assert len(ok) == 8
    assert len({str(r["discussion_id"]) for r in ok}) == 1


@pytest.mark.asyncio
async def test_repeating_advance_after_a_recorded_turn_does_not_repeat_the_turn():
    scenario = await _scenario()
    session = await _start(scenario, provider=ContestingProvider())
    service = _service(ContestingProvider())
    first = await service.advance(session["discussion_id"])
    assert first["advanced"] is True

    # The next advance legitimately moves to the NEXT seat; the first seat is never spoken twice.
    await service.advance(session["discussion_id"])
    turns = await service.get_turns(session["discussion_id"])
    slots = [(t["round_index"], t["seat_index"]) for t in turns]
    assert len(slots) == len(set(slots))
    assert slots == [(1, 0), (1, 1)]


@pytest.mark.parametrize("attempt", range(3))
@pytest.mark.asyncio
async def test_eight_workers_racing_the_same_turn_produce_exactly_one_reply(attempt):
    """The load-bearing property of AT-M3.3.

    Eight independent services, each with its own connections, advance the same discussion at the
    same time. Exactly one turn, one message and one reasoning invocation may become canonical.
    """
    scenario = await _scenario()
    session = await _start(scenario, provider=ContestingProvider())
    discussion_id = str(session["discussion_id"])

    async def worker():
        try:
            return await DiscussionService(provider=ContestingProvider()).advance(discussion_id)
        except Exception as exc:  # a lost race must never surface as an exception
            return exc

    for expected_seat in (0, 1, 2):
        results = await asyncio.gather(*(worker() for _ in range(8)))
        errors = [r for r in results if isinstance(r, Exception)]
        advanced = [r for r in results if not isinstance(r, Exception) and r["advanced"]]

        assert not errors, [type(e).__name__ for e in errors]
        assert len(advanced) == 1, f"seat {expected_seat}: {len(advanced)} workers advanced"

        turns = await _service().get_turns(discussion_id)
        slots = [(t["round_index"], t["seat_index"]) for t in turns]
        assert len(slots) == len(set(slots)), "a slot was taken twice"
        assert len(turns) == expected_seat + 1

        messages = await _service().get_messages(discussion_id)
        assert len(messages) == expected_seat + 1, "a duplicate reply was posted"

    conn = await scenario["store"]._connect()
    try:
        invocations = await conn.fetchval(
            "SELECT count(*) FROM reasoning_invocations WHERE thread_id=$1",
            session["thread_id"],
        )
    finally:
        await conn.close()
    assert invocations == 3, "one reasoning invocation per canonical turn, no more"


@pytest.mark.asyncio
async def test_concurrent_workers_never_skip_or_reorder_a_round():
    scenario = await _scenario()
    session = await _start(
        scenario, provider=ContestingProvider(), bounds=DiscussionBounds(max_rounds=2)
    )
    discussion_id = str(session["discussion_id"])

    for _ in range(12):
        await asyncio.gather(
            *(
                DiscussionService(provider=ContestingProvider()).advance(discussion_id)
                for _ in range(6)
            )
        )
        if (await _service().get_discussion(discussion_id))["state"] != "open":
            break

    final = await _service().get_discussion(discussion_id)
    turns = await _service().get_turns(discussion_id)
    slots = sorted((t["round_index"], t["seat_index"]) for t in turns)
    assert slots == [(1, 0), (1, 1), (1, 2), (2, 0), (2, 1), (2, 2)]
    assert final["state"] == "exhausted"
    assert final["stop_reason"] == "round_limit_reached"


# --- resume ---------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_discussion_resumes_from_durable_state_alone():
    scenario = await _scenario()
    session = await _start(
        scenario, provider=ContestingProvider(), bounds=DiscussionBounds(max_rounds=2)
    )
    discussion_id = str(session["discussion_id"])

    first_process = _service(ContestingProvider())
    await first_process.advance(discussion_id)
    await first_process.advance(discussion_id)
    mid = await first_process.get_discussion(discussion_id)
    assert mid["state"] == "open"
    del first_process  # every object graph the first "process" held is gone

    # A brand-new service, new store, new connections: nothing carried over but the rows.
    resumed = DiscussionService(
        store=DeliberationStore(),
        team_store=TeamStore(),
        planning_store=PlanningStore(),
        provider=ContestingProvider(),
    )
    outcome = await resumed.advance(discussion_id)
    assert outcome["advanced"] is True
    assert outcome["turn"]["seat_index"] == 2, "resumed at the correct next seat"
    assert outcome["turn"]["round_index"] == 1

    final = await resumed.run(discussion_id)
    assert final["session"]["state"] == "exhausted"
    turns = await resumed.get_turns(discussion_id)
    assert sorted((t["round_index"], t["seat_index"]) for t in turns) == [
        (1, 0),
        (1, 1),
        (1, 2),
        (2, 0),
        (2, 1),
        (2, 2),
    ]


@pytest.mark.asyncio
async def test_a_turn_claimed_but_never_reasoned_is_safely_taken_over():
    # The crash-before-the-provider case: nothing was consumed, so a new process may take the slot.
    scenario = await _scenario()
    session = await _start(scenario, provider=ContestingProvider())
    discussion_id = str(session["discussion_id"])
    participants = await _service().get_participants(discussion_id)

    owned, _ = await scenario["store"].claim_turn(
        {
            "discussion_id": discussion_id,
            "round_index": 1,
            "seat_index": 0,
            "speaker_principal_id": participants[0]["principal_id"],
            "addressed_team": True,
            "intent": "proposal",
            "reasoning_verb": "propose",
            "correlation_id": derive_correlation_id(discussion_id, 1, 0),
        }
    )
    assert owned is True

    outcome = await _service(ContestingProvider()).advance(discussion_id)
    assert outcome["advanced"] is True
    assert outcome["turn"]["status"] == "recorded"
    assert len(await _service().get_turns(discussion_id)) == 1


@pytest.mark.asyncio
async def test_a_turn_whose_reasoning_finished_without_a_message_fails_closed():
    # The crash-after-the-provider case. AT-M3.1 persists metadata and never artifact content, so
    # nothing can be reconstructed and re-invoking would be a second provider call for one turn.
    scenario = await _scenario()
    session = await _start(scenario, provider=ContestingProvider())
    discussion_id = str(session["discussion_id"])
    participants = await _service().get_participants(discussion_id)
    correlation = derive_correlation_id(discussion_id, 1, 0)

    await scenario["store"].claim_turn(
        {
            "discussion_id": discussion_id,
            "round_index": 1,
            "seat_index": 0,
            "speaker_principal_id": participants[0]["principal_id"],
            "addressed_team": True,
            "intent": "proposal",
            "reasoning_verb": "propose",
            "correlation_id": correlation,
        }
    )
    conn = await scenario["store"]._connect()
    try:
        await conn.execute(
            "INSERT INTO reasoning_invocations (project_id, thread_id, reasoning_verb, "
            "requested_provider_name, provider_mode, status, correlation_id, started_at, "
            "completed_at) VALUES ($1,$2,'propose','mock','mock','succeeded',$3,now(),now())",
            uuid.UUID(scenario["project_id"]),
            session["thread_id"],
            uuid.UUID(correlation),
        )
    finally:
        await conn.close()

    outcome = await _service(ContestingProvider()).advance(discussion_id)
    assert outcome["session"]["state"] == "failed"
    assert outcome["session"]["stop_reason"] == "reasoning_provider_failure"
    assert await _service().get_messages(discussion_id) == []


# --- storage prohibition and audit safety ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_at_m3_3_column_can_hold_hidden_reasoning():
    store = await _store_or_skip()
    conn = await store._connect()
    try:
        columns = await conn.fetch(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_name IN ('discussion_sessions','discussion_participants','discussion_turns')"
        )
    finally:
        await conn.close()
    forbidden = (
        "chain_of_thought",
        "hidden_reasoning",
        "scratchpad",
        "raw_prompt",
        "system_prompt",
        "prompt",
        "completion",
        "token_trace",
        "reasoning_tokens",
        "secret",
        "credential",
        "api_key",
    )
    names = [f"{c['table_name']}.{c['column_name']}" for c in columns]
    assert names
    for name in names:
        assert not any(marker in name.lower() for marker in forbidden), name


@pytest.mark.asyncio
async def test_nothing_a_discussion_persists_carries_a_forbidden_marker():
    scenario = await _scenario()
    session = await _start(scenario, provider=ConvergingProvider())
    await _service(ConvergingProvider()).run(session["discussion_id"])

    messages = await _service().get_messages(session["discussion_id"])
    blob = str(messages).lower()
    for marker in ("chain_of_thought", "raw_prompt", "system_prompt", "scratchpad", "api_key"):
        assert marker not in blob


@pytest.mark.asyncio
async def test_audit_events_carry_identifiers_and_dispositions_only():
    scenario = await _scenario()
    recorder = AuditRecorder()
    session = await _start(scenario, provider=ConvergingProvider(), audit=recorder)
    await DiscussionService(provider=ConvergingProvider(), audit_client=recorder).run(
        session["discussion_id"]
    )

    kinds = {e["decision_type"] for e in recorder.events}
    assert "discussion_opened" in kinds
    assert "discussion_turn_recorded" in kinds
    assert "discussion_closed" in kinds

    messages = await _service().get_messages(session["discussion_id"])
    bodies = [m["summary"] for m in messages]
    blob = str(recorder.events)
    for body in bodies:
        assert body not in blob, "a message body reached an audit event"
    for marker in ("chain_of_thought", "raw_prompt", "scratchpad", "rationale_summary"):
        assert marker not in blob.lower()


@pytest.mark.asyncio
async def test_the_discussion_writes_no_reasoning_context_anywhere():
    scenario = await _scenario()
    session = await _start(scenario, provider=ConvergingProvider())
    await _service(ConvergingProvider()).run(session["discussion_id"])
    conn = await scenario["store"]._connect()
    try:
        # reasoning_invocations is metadata only; the goal statement never appears in it.
        rows = await conn.fetch(
            "SELECT * FROM reasoning_invocations WHERE thread_id=$1", session["thread_id"]
        )
    finally:
        await conn.close()
    assert rows
    blob = str([dict(r) for r in rows]).lower()
    assert "deliver a reporting slice" not in blob
    assert "acceptance criteria" not in blob


@pytest.mark.parametrize("attempt", range(3))
@pytest.mark.asyncio
async def test_only_the_worker_that_actually_closed_the_discussion_reports_advancing(attempt):
    """``advanced`` must mean "I changed something", including at the closure step.

    Closure is a conditional write, so of several workers reaching the terminal condition together
    exactly one performs it. Reporting True for all of them would make the flag useless for
    deciding whether anything happened -- which is precisely what a caller polling this uses it for.
    """
    scenario = await _scenario()
    session = await _start(
        scenario, provider=ContestingProvider(), bounds=DiscussionBounds(max_rounds=1)
    )
    discussion_id = str(session["discussion_id"])

    async def worker():
        return await DiscussionService(provider=ContestingProvider()).advance(discussion_id)

    closures = 0
    for _ in range(8):
        results = await asyncio.gather(*(worker() for _ in range(8)))
        advanced = [r for r in results if r["advanced"]]
        assert len(advanced) <= 1, f"{len(advanced)} workers claimed the same step"
        if (await _service().get_discussion(discussion_id))["state"] != "open":
            closures = len([r for r in results if r["advanced"]])
            break

    assert closures == 1, "exactly one worker closes the discussion"
    final = await _service().get_discussion(discussion_id)
    assert final["state"] == "exhausted" and final["stop_reason"] == "round_limit_reached"
    # Every worker sees the real terminal state, whether or not it was the one that wrote it.
    losers = await asyncio.gather(*(worker() for _ in range(4)))
    assert all(r["advanced"] is False for r in losers)
    assert all(r["session"]["stop_reason"] == "round_limit_reached" for r in losers)
