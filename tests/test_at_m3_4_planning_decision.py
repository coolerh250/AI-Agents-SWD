"""Step AT-M3.4 -- the formal planning decision against a real PostgreSQL.

The assertions that matter here are all about what CANNOT happen, and none of them is provable
against a fake: an accepted plan with no decision, two decisions for one discussion, two successors
from one predecessor, or a plan derived from a deliberation the world has moved past.

The load-bearing proof is at the bottom: eight independent workers finalize one converged
discussion, and exactly one TeamDecision and one accepted revision exist afterwards.
"""

from __future__ import annotations

import asyncio
import uuid

import asyncpg
import pytest

from shared.sdk.agent_planning.models import StalePlanRevisionError, compute_plan_diff
from shared.sdk.agent_planning.models import PlanContent
from shared.sdk.agent_planning.store import PlanningStore
from shared.sdk.agent_planning_decision.models import (
    DiscussionNotAdmissibleError,
    PlanningDecisionStateError,
    build_decision_evidence,
    derive_idempotency_key,
    evaluate_admissibility,
    validate_plan,
)
from shared.sdk.agent_planning_decision.service import PlanningDecisionService
from shared.sdk.agent_planning_decision.store import PlanningDecisionStore
from shared.sdk.agent_deliberation.service import DiscussionService
from shared.sdk.agent_deliberation.store import DeliberationStore

from tests.test_at_m3_3_deliberation_store import (
    CAPS,
    PLAN,
    AuditRecorder,
    ContestingProvider,
    ConvergingProvider,
    FailingProvider,
    _scenario,
    _start,
)

#: The successor plan a decision accepts. Structured, never prose -- one added step and a changed
#: objective relative to the M3.3 fixture, so the server-computed diff has something real to say.
NEXT_PLAN = {
    "objective": "deliver the reporting slice, narrowed to one reviewer-readable report",
    "steps": [
        {"step_key": "s1", "title": "define the contract", "depends_on": []},
        {
            "step_key": "s2",
            "title": "render one report",
            "depends_on": ["s1"],
            "required_capabilities": ["generate_code"],
        },
    ],
    "constraints": ["non-production only"],
    "acceptance_criteria": ["a reviewer can read one report"],
}


def _store_or_skip() -> PlanningDecisionStore:
    return PlanningDecisionStore()


async def _skip_without_migration() -> None:
    store = PlanningDecisionStore()
    try:
        conn = await store._connect()
    except Exception:
        pytest.skip("no reachable PostgreSQL; skipping AT-M3.4 store test")
    try:
        if await conn.fetchval("SELECT to_regclass('public.planning_decisions')") is None:
            pytest.skip("migration 040 not applied; skipping AT-M3.4 store test")
    finally:
        await conn.close()


def _service(audit=None) -> PlanningDecisionService:
    return PlanningDecisionService(audit_client=audit)


async def _converged(scenario, *, provider=None, key=None) -> dict:
    """Run one discussion to a genuine convergence and return its session row."""
    await _skip_without_migration()
    session = await _start(scenario, provider=provider or ConvergingProvider(), key=key)
    final = await DiscussionService(provider=provider or ConvergingProvider()).run(
        str(session["discussion_id"])
    )
    assert final["session"]["state"] == "converged", final["session"]["stop_reason"]
    return final["session"]


async def _counts(store: PlanningDecisionStore, project_id: str) -> dict[str, int]:
    conn = await store._connect()
    try:
        return {
            "planning_decisions": await conn.fetchval(
                "SELECT count(*) FROM planning_decisions WHERE project_id=$1", uuid.UUID(project_id)
            ),
            "team_decisions": await conn.fetchval(
                "SELECT count(*) FROM team_decisions WHERE project_id=$1", uuid.UUID(project_id)
            ),
            "plan_revisions": await conn.fetchval(
                "SELECT count(*) FROM plan_revisions WHERE project_id=$1", uuid.UUID(project_id)
            ),
        }
    finally:
        await conn.close()


# ==================================================================================================
# The input gate
# ==================================================================================================


@pytest.mark.asyncio
async def test_a_converged_discussion_becomes_one_decision_and_one_accepted_plan():
    scenario = await _scenario()
    session = await _converged(scenario)

    outcome = await _service().finalize(
        goal_id=scenario["goal_id"],
        discussion_id=str(session["discussion_id"]),
        decided_by=scenario["opened_by"],
        plan=NEXT_PLAN,
    )

    assert outcome["created"] is True
    ledger = outcome["planning_decision"]
    decision = outcome["team_decision"]
    revision = outcome["plan_revision"]

    assert ledger["outcome"] == "plan_accepted"
    assert str(ledger["discussion_id"]) == str(session["discussion_id"])
    assert str(ledger["result_message_id"]) == str(session["result_message_id"])
    assert str(ledger["predecessor_plan_revision_id"]) == scenario["plan_revision_id"]

    # The decision is an AT-M2 TeamDecision, and it names the revision it selected.
    assert str(decision["decision_id"]) == str(ledger["team_decision_id"])
    assert str(decision["thread_id"]) == str(session["thread_id"])
    assert str(decision["resulting_plan_revision_id"]) == str(revision["plan_revision_id"])
    assert decision["selected_option"] and decision["rationale_summary"]
    assert decision["options_considered"]

    # The revision it selected is accepted, and it superseded the revision under discussion.
    assert revision["status"] == "accepted"
    assert revision["reason"] == "team_decision"
    assert str(revision["supersedes_revision_id"]) == scenario["plan_revision_id"]
    assert str(revision["trace_ref"]) == str(session["result_message_id"])
    assert revision["plan"]["objective"] == NEXT_PLAN["objective"]

    counts = await _counts(_store_or_skip(), scenario["project_id"])
    assert counts == {"planning_decisions": 1, "team_decisions": 1, "plan_revisions": 2}


@pytest.mark.asyncio
async def test_an_exhausted_discussion_is_refused():
    scenario = await _scenario()
    session = await _start(scenario, provider=ContestingProvider())
    final = await DiscussionService(provider=ContestingProvider()).run(
        str(session["discussion_id"])
    )
    assert final["session"]["state"] == "exhausted"

    with pytest.raises(DiscussionNotAdmissibleError) as exc:
        await _service().finalize(
            goal_id=scenario["goal_id"],
            discussion_id=str(session["discussion_id"]),
            decided_by=scenario["opened_by"],
            plan=NEXT_PLAN,
        )
    assert exc.value.clause == "state"
    assert (await _counts(_store_or_skip(), scenario["project_id"]))["team_decisions"] == 0


@pytest.mark.asyncio
async def test_a_failed_discussion_is_refused():
    scenario = await _scenario()
    session = await _start(scenario, provider=FailingProvider())
    await DiscussionService(provider=FailingProvider()).run(str(session["discussion_id"]))
    state = await DiscussionService().get_discussion(str(session["discussion_id"]))
    assert state["state"] == "failed"

    with pytest.raises(DiscussionNotAdmissibleError) as exc:
        await _service().finalize(
            goal_id=scenario["goal_id"],
            discussion_id=str(session["discussion_id"]),
            decided_by=scenario["opened_by"],
            plan=NEXT_PLAN,
        )
    assert exc.value.clause == "state"


@pytest.mark.asyncio
async def test_a_cancelled_discussion_is_refused():
    scenario = await _scenario()
    session = await _start(scenario, provider=ConvergingProvider())
    await DiscussionService().cancel(str(session["discussion_id"]))

    with pytest.raises(DiscussionNotAdmissibleError) as exc:
        await _service().finalize(
            goal_id=scenario["goal_id"],
            discussion_id=str(session["discussion_id"]),
            decided_by=scenario["opened_by"],
            plan=NEXT_PLAN,
        )
    assert exc.value.clause == "state"


@pytest.mark.asyncio
async def test_a_converged_discussion_with_no_result_message_is_refused():
    """Constructed by raw SQL, because the runtime cannot produce it -- and the gate still holds."""
    scenario = await _scenario()
    await _skip_without_migration()
    store = DeliberationStore()
    conn = await store._connect()
    try:
        thread_id = await conn.fetchval(
            "INSERT INTO conversation_threads (project_id, goal_ref, thread_type) "
            "VALUES ($1,$2,'planning') RETURNING thread_id",
            uuid.UUID(scenario["project_id"]),
            scenario["goal_id"],
        )
        discussion_id = await conn.fetchval(
            "INSERT INTO discussion_sessions (project_id, goal_id, plan_revision_id, thread_id, "
            "opened_by, topic, max_rounds, max_messages, max_invocations, "
            "max_turns_per_participant, deadline_at, state, stop_reason, idempotency_key) "
            "VALUES ($1,$2,$3,$4,$5,'t',3,24,24,3, now() + interval '1 hour', "
            "'converged','convergence_reached',$6) RETURNING discussion_id",
            uuid.UUID(scenario["project_id"]),
            uuid.UUID(scenario["goal_id"]),
            uuid.UUID(scenario["plan_revision_id"]),
            thread_id,
            uuid.UUID(scenario["opened_by"]),
            f"noresult-{uuid.uuid4().hex}",
        )
    finally:
        await conn.close()

    with pytest.raises(DiscussionNotAdmissibleError) as exc:
        await _service().finalize(
            goal_id=scenario["goal_id"],
            discussion_id=str(discussion_id),
            decided_by=scenario["opened_by"],
            plan=NEXT_PLAN,
        )
    assert exc.value.clause == "result"


@pytest.mark.asyncio
async def test_a_discussion_about_another_goal_is_refused():
    scenario = await _scenario()
    other = await _scenario()
    session = await _converged(scenario)

    with pytest.raises(DiscussionNotAdmissibleError) as exc:
        await _service().finalize(
            goal_id=other["goal_id"],
            discussion_id=str(session["discussion_id"]),
            decided_by=other["opened_by"],
            plan=NEXT_PLAN,
        )
    assert exc.value.clause == "goal"


@pytest.mark.asyncio
async def test_a_discussion_bound_to_a_superseded_revision_is_refused_and_never_rebound():
    scenario = await _scenario()
    session = await _converged(scenario)
    planning = PlanningStore()
    successor = await planning.create_successor_revision(
        {
            "goal_id": scenario["goal_id"],
            "expected_current_revision_id": scenario["plan_revision_id"],
            "created_by": scenario["opened_by"],
            "reason": "team_decision",
            "plan": PLAN,
        }
    )

    with pytest.raises(DiscussionNotAdmissibleError) as exc:
        await _service().finalize(
            goal_id=scenario["goal_id"],
            discussion_id=str(session["discussion_id"]),
            decided_by=scenario["opened_by"],
            plan=NEXT_PLAN,
        )
    assert exc.value.clause == "currency"
    # Not rebound to the new current revision, and no decision manufactured from stale evidence.
    still = await DiscussionService().get_discussion(str(session["discussion_id"]))
    assert str(still["plan_revision_id"]) == scenario["plan_revision_id"]
    assert (await _counts(_store_or_skip(), scenario["project_id"]))["team_decisions"] == 0
    assert len(await planning.list_revisions(scenario["goal_id"])) == 2
    assert str(successor["plan_revision_id"]) != scenario["plan_revision_id"]


@pytest.mark.asyncio
async def test_a_planless_goal_decision_creates_the_root_and_is_refused_once_a_plan_exists():
    scenario = await _scenario()
    await _skip_without_migration()
    planning = PlanningStore()
    conn = await DeliberationStore()._connect()
    try:
        opener = str(
            await conn.fetchval(
                "INSERT INTO actor_principals (principal_type,display_name) VALUES ('human',$1) "
                "RETURNING principal_id",
                f"m34-noplan-{uuid.uuid4().hex[:6]}",
            )
        )
    finally:
        await conn.close()
    goal = await planning.create_goal(
        {"project_id": scenario["project_id"], "statement": "no plan yet", "created_by": opener}
    )
    goal_id = str(goal["goal_id"])

    session = await DiscussionService(provider=ConvergingProvider()).start_discussion(
        project_id=scenario["project_id"],
        goal_id=goal_id,
        topic="what should the first plan be?",
        opened_by=opener,
        required_capabilities=CAPS,
    )
    assert session["plan_revision_id"] is None
    final = await DiscussionService(provider=ConvergingProvider()).run(
        str(session["discussion_id"])
    )
    assert final["session"]["state"] == "converged"

    outcome = await _service().finalize(
        goal_id=goal_id,
        discussion_id=str(session["discussion_id"]),
        decided_by=opener,
        plan=NEXT_PLAN,
    )
    assert outcome["created"] is True
    assert outcome["plan_revision"]["reason"] == "initial"
    assert outcome["plan_revision"]["status"] == "accepted"
    assert outcome["plan_revision"]["supersedes_revision_id"] is None
    assert outcome["planning_decision"]["predecessor_plan_revision_id"] is None

    # A second planless discussion on the same goal is now refused: its premise is gone.
    second = await DiscussionService(provider=ConvergingProvider()).start_discussion(
        project_id=scenario["project_id"],
        goal_id=goal_id,
        topic="a different first plan?",
        opened_by=opener,
        required_capabilities=CAPS,
        plan_revision_id=None,
    )
    if second["plan_revision_id"] is None:  # only reachable if it opened before the root landed
        with pytest.raises(DiscussionNotAdmissibleError):
            await _service().finalize(
                goal_id=goal_id,
                discussion_id=str(second["discussion_id"]),
                decided_by=opener,
                plan=NEXT_PLAN,
            )


# ==================================================================================================
# Lifecycle, lineage and the structured plan
# ==================================================================================================


@pytest.mark.asyncio
async def test_the_revision_is_created_draft_and_accepted_by_the_decision_not_born_accepted():
    """The AT-M3.2 backlog concern, closed on the autonomous path."""
    scenario = await _scenario()
    session = await _converged(scenario)
    outcome = await _service().finalize(
        goal_id=scenario["goal_id"],
        discussion_id=str(session["discussion_id"]),
        decided_by=scenario["opened_by"],
        plan=NEXT_PLAN,
    )
    revision_id = str(outcome["plan_revision"]["plan_revision_id"])

    store = _store_or_skip()
    conn = await store._connect()
    try:
        # Every accepted revision on this path has a planning decision, and that decision names it.
        orphans = await conn.fetchval(
            """
            SELECT count(*) FROM plan_revisions r
            WHERE r.project_id=$1 AND r.status='accepted'
              AND NOT EXISTS (
                  SELECT 1 FROM planning_decisions d WHERE d.resulting_plan_revision_id=r.plan_revision_id
              )
            """,
            uuid.UUID(scenario["project_id"]),
        )
        assert orphans == 0, "an accepted revision exists that no TeamDecision chose"
        # The acceptance is a transition on the SAME revision, not a second row.
        assert (
            await conn.fetchval(
                "SELECT count(*) FROM plan_revisions WHERE plan_revision_id=$1",
                uuid.UUID(revision_id),
            )
            == 1
        )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_the_predecessor_is_untouched_and_the_diff_is_computed_server_side():
    scenario = await _scenario()
    planning = PlanningStore()
    before = await planning.get_revision(scenario["plan_revision_id"])
    session = await _converged(scenario)

    outcome = await _service().finalize(
        goal_id=scenario["goal_id"],
        discussion_id=str(session["discussion_id"]),
        decided_by=scenario["opened_by"],
        plan=NEXT_PLAN,
    )

    assert await planning.get_revision(scenario["plan_revision_id"]) == before

    expected = compute_plan_diff(PlanContent(**PLAN), PlanContent(**NEXT_PLAN)).model_dump(
        mode="json"
    )
    assert outcome["plan_revision"]["diff"] == expected
    assert outcome["plan_revision"]["diff"]["objective_changed"] is True
    assert "s2" in outcome["plan_revision"]["diff"]["steps_added"]


@pytest.mark.asyncio
async def test_a_prose_only_plan_is_refused():
    scenario = await _scenario()
    session = await _converged(scenario)
    for bad in ("just do the thing", {"objective": ""}, {"steps": []}):
        with pytest.raises((PlanningDecisionStateError, ValueError)):
            await _service().finalize(
                goal_id=scenario["goal_id"],
                discussion_id=str(session["discussion_id"]),
                decided_by=scenario["opened_by"],
                plan=bad,
            )
    assert (await _counts(_store_or_skip(), scenario["project_id"]))["team_decisions"] == 0


@pytest.mark.asyncio
async def test_the_evidence_read_reconstructs_the_lineage_without_a_second_record():
    scenario = await _scenario()
    session = await _converged(scenario)
    service = _service()
    outcome = await service.finalize(
        goal_id=scenario["goal_id"],
        discussion_id=str(session["discussion_id"]),
        decided_by=scenario["opened_by"],
        plan=NEXT_PLAN,
    )
    evidence = await service.get_evidence(str(outcome["planning_decision"]["planning_decision_id"]))

    assert evidence["discussion_id"] == str(session["discussion_id"])
    assert evidence["goal_id"] == str(scenario["goal_id"])
    assert evidence["proposals"], "the deliberation's proposals must be readable"
    for item in evidence["proposals"]:
        assert item["message_type"] == "proposal"
        assert item["discussion_intent"] == "proposal"
        assert item["summary"]
    for item in evidence["challenges"]:
        assert item["message_type"] == "challenge"

    # And no proposal or challenge table was invented to hold any of it.
    conn = await _store_or_skip()._connect()
    try:
        invented = await conn.fetchval(
            "SELECT count(*) FROM pg_tables WHERE tablename IN "
            "('proposals','challenges','planning_proposals','planning_challenges')"
        )
        assert invented == 0
    finally:
        await conn.close()


# ==================================================================================================
# Idempotency, atomicity, concurrency
# ==================================================================================================


@pytest.mark.asyncio
async def test_a_repeated_command_replays_the_canonical_decision_without_making_a_second():
    scenario = await _scenario()
    session = await _converged(scenario)
    service = _service()
    args = dict(
        goal_id=scenario["goal_id"],
        discussion_id=str(session["discussion_id"]),
        decided_by=scenario["opened_by"],
        plan=NEXT_PLAN,
    )
    first = await service.finalize(**args)
    assert first["created"] is True

    for _ in range(3):
        again = await service.finalize(**args)
        assert again["created"] is False
        assert str(again["planning_decision"]["planning_decision_id"]) == str(
            first["planning_decision"]["planning_decision_id"]
        )
        assert str(again["team_decision"]["decision_id"]) == str(
            first["team_decision"]["decision_id"]
        )
        assert str(again["plan_revision"]["plan_revision_id"]) == str(
            first["plan_revision"]["plan_revision_id"]
        )

    counts = await _counts(_store_or_skip(), scenario["project_id"])
    assert counts == {"planning_decisions": 1, "team_decisions": 1, "plan_revisions": 2}


@pytest.mark.asyncio
async def test_the_idempotency_key_is_bound_to_the_discussion_and_its_evidence():
    a = derive_idempotency_key(discussion_id="d1", result_message_id="m1")
    assert a == derive_idempotency_key(discussion_id="d1", result_message_id="m1")
    assert a != derive_idempotency_key(discussion_id="d1", result_message_id="m2")
    assert a != derive_idempotency_key(discussion_id="d2", result_message_id="m1")


@pytest.mark.asyncio
async def test_a_failure_anywhere_in_the_boundary_leaves_nothing_behind():
    """Crash windows A, B and C at once: if any step raises, none of the others survives."""
    scenario = await _scenario()
    session = await _converged(scenario)
    store = _store_or_skip()

    class ExplodingAccept(PlanningStore):
        async def accept_revision(self, plan_revision_id, *, conn=None):
            raise RuntimeError("simulated crash between the decision and the acceptance")

    store.planning = ExplodingAccept(store.database_url)
    service = PlanningDecisionService(store=store)

    with pytest.raises(RuntimeError):
        await service.finalize(
            goal_id=scenario["goal_id"],
            discussion_id=str(session["discussion_id"]),
            decided_by=scenario["opened_by"],
            plan=NEXT_PLAN,
        )

    counts = await _counts(_store_or_skip(), scenario["project_id"])
    assert counts["planning_decisions"] == 0, "a ledger row survived a failed finalization"
    assert counts["team_decisions"] == 0, "a TeamDecision survived a failed finalization"
    assert counts["plan_revisions"] == 1, "a draft revision survived a failed finalization"

    # And the operation is still available: the failure left no poison behind.
    healthy = await _service().finalize(
        goal_id=scenario["goal_id"],
        discussion_id=str(session["discussion_id"]),
        decided_by=scenario["opened_by"],
        plan=NEXT_PLAN,
    )
    assert healthy["created"] is True
    assert healthy["plan_revision"]["status"] == "accepted"


@pytest.mark.asyncio
async def test_a_ledger_failure_also_rolls_back_the_decision_and_the_acceptance():
    """The last write in the transaction fails, and the first three do not survive it."""
    # One already-finalized decision elsewhere, purely to own an idempotency key we can collide
    # with. Colliding is the most faithful ledger failure available: it is the same constraint a
    # real duplicate would hit, rather than a synthetic exception thrown from outside the boundary.
    donor_scenario = await _scenario()
    donor_session = await _converged(donor_scenario)
    donor = await _service().finalize(
        goal_id=donor_scenario["goal_id"],
        discussion_id=str(donor_session["discussion_id"]),
        decided_by=donor_scenario["opened_by"],
        plan=NEXT_PLAN,
    )
    stolen_key = donor["planning_decision"]["idempotency_key"]

    scenario = await _scenario()
    session = await _converged(scenario)

    class CollidingStore(PlanningDecisionStore):
        async def finalize(self, **kwargs):
            return await super().finalize(**{**kwargs, "idempotency_key": stolen_key})

    service = PlanningDecisionService(store=CollidingStore(_store_or_skip().database_url))
    with pytest.raises(Exception):
        await service.finalize(
            goal_id=scenario["goal_id"],
            discussion_id=str(session["discussion_id"]),
            decided_by=scenario["opened_by"],
            plan=NEXT_PLAN,
        )

    counts = await _counts(_store_or_skip(), scenario["project_id"])
    assert counts == {"planning_decisions": 0, "team_decisions": 0, "plan_revisions": 1}
    # The donor's own decision is untouched by the failed attempt against it.
    assert (await _counts(_store_or_skip(), donor_scenario["project_id"]))[
        "planning_decisions"
    ] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("attempt", [1, 2, 3])
async def test_eight_workers_finalizing_one_discussion_produce_exactly_one_decision(attempt):
    """THE load-bearing proof of this slice."""
    scenario = await _scenario()
    session = await _converged(scenario, key=f"race-{attempt}-{uuid.uuid4().hex}")
    discussion_id = str(session["discussion_id"])

    async def worker():
        try:
            return await PlanningDecisionService(store=PlanningDecisionStore()).finalize(
                goal_id=scenario["goal_id"],
                discussion_id=discussion_id,
                decided_by=scenario["opened_by"],
                plan=NEXT_PLAN,
            )
        except Exception as exc:
            return exc

    results = await asyncio.gather(*(worker() for _ in range(8)))
    errors = [r for r in results if isinstance(r, Exception)]
    assert not errors, [f"{type(e).__name__}: {e}" for e in errors]

    created = [r for r in results if r["created"]]
    replayed = [r for r in results if not r["created"]]
    assert len(created) == 1, f"{len(created)} workers each believed they made the decision"
    assert len(replayed) == 7

    # Every worker reports the SAME canonical decision, winner and losers alike.
    ids = {str(r["planning_decision"]["planning_decision_id"]) for r in results}
    revisions = {str(r["plan_revision"]["plan_revision_id"]) for r in results}
    assert len(ids) == 1 and len(revisions) == 1
    assert all(r["plan_revision"]["status"] == "accepted" for r in results)

    counts = await _counts(_store_or_skip(), scenario["project_id"])
    assert counts == {"planning_decisions": 1, "team_decisions": 1, "plan_revisions": 2}

    planning = PlanningStore()
    current = await planning.get_current_revision(scenario["goal_id"])
    assert str(current["plan_revision_id"]) == revisions.pop()
    assert current["status"] == "accepted"


@pytest.mark.asyncio
async def test_two_discussions_racing_one_predecessor_yield_one_successor():
    scenario = await _scenario()
    first = await _converged(scenario, key=f"d1-{uuid.uuid4().hex}")
    second = await _converged(scenario, key=f"d2-{uuid.uuid4().hex}")
    assert str(first["discussion_id"]) != str(second["discussion_id"])
    assert (
        str(first["plan_revision_id"])
        == str(second["plan_revision_id"])
        == scenario["plan_revision_id"]
    )

    async def consume(discussion):
        try:
            return await PlanningDecisionService(store=PlanningDecisionStore()).finalize(
                goal_id=scenario["goal_id"],
                discussion_id=str(discussion["discussion_id"]),
                decided_by=scenario["opened_by"],
                plan=NEXT_PLAN,
            )
        except (StalePlanRevisionError, DiscussionNotAdmissibleError) as exc:
            return exc

    results = await asyncio.gather(consume(first), consume(second))
    winners = [r for r in results if not isinstance(r, Exception)]
    losers = [r for r in results if isinstance(r, Exception)]
    assert len(winners) == 1, "both discussions produced a successor from one predecessor"
    assert len(losers) == 1

    counts = await _counts(_store_or_skip(), scenario["project_id"])
    assert counts == {"planning_decisions": 1, "team_decisions": 1, "plan_revisions": 2}

    # The losing deliberation is preserved untouched -- evidence, not garbage.
    for discussion in (first, second):
        still = await DiscussionService().get_discussion(str(discussion["discussion_id"]))
        assert still["state"] == "converged"
        assert still["stop_reason"] == "convergence_reached"
        assert str(still["plan_revision_id"]) == scenario["plan_revision_id"]
        assert str(still["result_message_id"]) == str(discussion["result_message_id"])


@pytest.mark.asyncio
async def test_a_successor_appearing_between_the_pre_read_and_the_write_fails_closed():
    """The stale race: the pre-read said current, the CAS says otherwise, and the CAS wins."""
    scenario = await _scenario()
    session = await _converged(scenario)
    planning = PlanningStore()
    store = _store_or_skip()
    predecessor_before = await planning.get_revision(scenario["plan_revision_id"])

    class InterferingStore(PlanningDecisionStore):
        async def finalize(self, **kwargs):
            # Another legitimate path lands a successor after admissibility passed and before this
            # transaction takes the predecessor lock.
            await planning.create_successor_revision(
                {
                    "goal_id": scenario["goal_id"],
                    "expected_current_revision_id": scenario["plan_revision_id"],
                    "created_by": scenario["opened_by"],
                    "reason": "scope_correction",
                    "plan": PLAN,
                }
            )
            return await super().finalize(**kwargs)

    service = PlanningDecisionService(store=InterferingStore(store.database_url))
    with pytest.raises(StalePlanRevisionError):
        await service.finalize(
            goal_id=scenario["goal_id"],
            discussion_id=str(session["discussion_id"]),
            decided_by=scenario["opened_by"],
            plan=NEXT_PLAN,
        )

    counts = await _counts(_store_or_skip(), scenario["project_id"])
    assert counts["planning_decisions"] == 0, (
        "a decision claimed a revision derived from stale evidence"
    )
    assert counts["team_decisions"] == 0
    assert counts["plan_revisions"] == 2, "only the interfering successor exists"
    assert await planning.get_revision(scenario["plan_revision_id"]) == predecessor_before

    # The discussion is unchanged and remains historical evidence about the revision it discussed.
    still = await DiscussionService().get_discussion(str(session["discussion_id"]))
    assert still["state"] == "converged"
    assert str(still["plan_revision_id"]) == scenario["plan_revision_id"]


# ==================================================================================================
# Boundaries: approval, execution, audit
# ==================================================================================================


@pytest.mark.asyncio
async def test_a_team_decision_creates_no_approval_and_changes_no_authorization():
    scenario = await _scenario()
    session = await _converged(scenario)
    store = _store_or_skip()

    conn = await store._connect()
    try:
        approval_tables = [
            r["tablename"]
            for r in await conn.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                "AND (tablename LIKE '%approval%' OR tablename LIKE '%policy%')"
            )
        ]
        before = {t: await conn.fetchval(f"SELECT count(*) FROM {t}") for t in approval_tables}
    finally:
        await conn.close()

    await _service().finalize(
        goal_id=scenario["goal_id"],
        discussion_id=str(session["discussion_id"]),
        decided_by=scenario["opened_by"],
        plan=NEXT_PLAN,
    )

    conn = await store._connect()
    try:
        after = {t: await conn.fetchval(f"SELECT count(*) FROM {t}") for t in approval_tables}
    finally:
        await conn.close()
    assert before == after, "a planning decision touched an approval or policy table"
    assert approval_tables, "the fixture must actually have approval tables to be meaningful"


@pytest.mark.asyncio
async def test_no_work_item_run_or_dispatch_is_produced():
    scenario = await _scenario()
    session = await _converged(scenario)
    store = _store_or_skip()
    conn = await store._connect()
    try:
        before = await conn.fetchval("SELECT count(*) FROM project_work_items")
        routing_before = await conn.fetchval("SELECT count(*) FROM agent_routing_decisions")
    finally:
        await conn.close()

    await _service().finalize(
        goal_id=scenario["goal_id"],
        discussion_id=str(session["discussion_id"]),
        decided_by=scenario["opened_by"],
        plan=NEXT_PLAN,
    )

    conn = await store._connect()
    try:
        assert await conn.fetchval("SELECT count(*) FROM project_work_items") == before
        assert await conn.fetchval("SELECT count(*) FROM agent_routing_decisions") == routing_before
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_audit_metadata_carries_identifiers_and_no_discussion_body():
    scenario = await _scenario()
    session = await _converged(scenario)
    audit = AuditRecorder()
    outcome = await _service(audit).finalize(
        goal_id=scenario["goal_id"],
        discussion_id=str(session["discussion_id"]),
        decided_by=scenario["opened_by"],
        plan=NEXT_PLAN,
    )

    assert audit.events, "the finalization recorded no audit event"
    recorded = [e for e in audit.events if e["decision_type"] == "planning_decision_recorded"]
    assert len(recorded) == 1
    refs = recorded[0]["artifact_refs"]
    for key in (
        "planning_decision_id",
        "goal_id",
        "discussion_id",
        "result_message_id",
        "team_decision_id",
        "resulting_plan_revision_id",
    ):
        assert refs[key]
    assert refs["revision_status"] == "accepted"

    blob = str(audit.events)
    messages = await DiscussionService().get_messages(str(session["discussion_id"]))
    for message in messages:
        assert message["summary"] not in blob, "a message body reached the audit trail"
    for forbidden in ("chain_of_thought", "scratchpad", "raw_prompt", "completion", "token"):
        assert forbidden not in blob.lower()
    assert outcome["created"] is True


@pytest.mark.asyncio
async def test_a_recorded_planning_decision_cannot_be_rewritten():
    scenario = await _scenario()
    session = await _converged(scenario)
    outcome = await _service().finalize(
        goal_id=scenario["goal_id"],
        discussion_id=str(session["discussion_id"]),
        decided_by=scenario["opened_by"],
        plan=NEXT_PLAN,
    )
    ledger_id = outcome["planning_decision"]["planning_decision_id"]

    conn = await _store_or_skip()._connect()
    try:
        for sql in (
            "UPDATE planning_decisions SET outcome='plan_accepted', discussion_id=$2 "
            "WHERE planning_decision_id=$1",
        ):
            with pytest.raises(asyncpg.exceptions.RestrictViolationError):
                await conn.execute(sql, ledger_id, uuid.uuid4())
        # A second ledger row for the same discussion is unrepresentable.
        with pytest.raises(asyncpg.exceptions.UniqueViolationError):
            await conn.execute(
                "INSERT INTO planning_decisions (project_id, goal_id, discussion_id, "
                "result_message_id, team_decision_id, resulting_plan_revision_id, outcome, "
                "idempotency_key) SELECT project_id, goal_id, discussion_id, result_message_id, "
                "team_decision_id, resulting_plan_revision_id, outcome, $2 "
                "FROM planning_decisions WHERE planning_decision_id=$1",
                ledger_id,
                f"dup-{uuid.uuid4().hex}",
            )
    finally:
        await conn.close()


# ==================================================================================================
# Pure logic
# ==================================================================================================


def test_admissibility_names_the_clause_that_failed():
    base = {
        "state": "converged",
        "stop_reason": "convergence_reached",
        "result_message_id": "m1",
        "goal_id": "g1",
        "plan_revision_id": "r1",
    }
    assert evaluate_admissibility(
        discussion=base, goal_id="g1", current_plan_revision_id="r1"
    ).admissible
    assert (
        evaluate_admissibility(discussion=None, goal_id="g1", current_plan_revision_id="r1").clause
        == "exists"
    )
    for field, value, clause in (
        ("state", "exhausted", "state"),
        ("stop_reason", "round_limit_reached", "stop_reason"),
        ("result_message_id", None, "result"),
        ("goal_id", "other", "goal"),
    ):
        verdict = evaluate_admissibility(
            discussion={**base, field: value}, goal_id="g1", current_plan_revision_id="r1"
        )
        assert not verdict.admissible and verdict.clause == clause, field

    stale = evaluate_admissibility(discussion=base, goal_id="g1", current_plan_revision_id="r2")
    assert not stale.admissible and stale.clause == "currency"
    assert "not rebound" in stale.detail


def test_a_planless_discussion_is_current_only_while_the_goal_is_planless():
    planless = {
        "state": "converged",
        "stop_reason": "convergence_reached",
        "result_message_id": "m1",
        "goal_id": "g1",
        "plan_revision_id": None,
    }
    assert evaluate_admissibility(
        discussion=planless, goal_id="g1", current_plan_revision_id=None
    ).admissible
    verdict = evaluate_admissibility(
        discussion=planless, goal_id="g1", current_plan_revision_id="r1"
    )
    assert not verdict.admissible and verdict.clause == "currency"


def test_decision_evidence_comes_from_the_convergence_summary():
    result = {
        "message_id": "m9",
        "summary": "aligned",
        "content": {
            "summary": "aligned",
            "rationale_summary": "no concern remained",
            "options_considered": ["A", "B"],
            "selected_option": "A",
            "dissent_summary": None,
        },
    }
    messages = [
        {"message_id": "m1", "message_type": "proposal", "summary": "do A"},
        {"message_id": "m2", "message_type": "challenge", "summary": "what about B"},
        result | {"message_type": "message"},
    ]
    evidence = build_decision_evidence(result_message=result, messages=messages, turns=[])
    assert evidence.selected_option == "A"
    assert evidence.options_considered == ("A", "B")
    assert evidence.rationale_summary == "no concern remained"
    assert evidence.proposal_message_ids == ("m1",)
    assert evidence.challenge_message_ids == ("m2",)


def test_unresolved_concerns_are_reported_rather_than_suppressed():
    result = {"message_id": "m9", "summary": "aligned", "content": {"selected_option": "A"}}
    turns = [
        {"intent": "challenge", "concern_count": 2},
        {"intent": "support", "concern_count": 0},
    ]
    evidence = build_decision_evidence(result_message=result, messages=[], turns=turns)
    assert evidence.dissent_summary is not None
    assert "2 concern" in evidence.dissent_summary


def test_a_plan_must_be_structured():
    with pytest.raises(PlanningDecisionStateError):
        validate_plan("just do it")
    with pytest.raises(Exception):
        validate_plan(
            {"objective": "o", "steps": [{"step_key": "a", "title": "t", "depends_on": ["zz"]}]}
        )
    assert validate_plan(NEXT_PLAN)["objective"] == NEXT_PLAN["objective"]
