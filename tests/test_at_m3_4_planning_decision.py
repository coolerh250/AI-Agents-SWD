"""Step AT-M3.4 -- the formal planning decision against a real PostgreSQL.

The assertions that matter here are all about what CANNOT happen, and none of them is provable
against a fake: a plan the team never chose being recorded as the plan it chose, an accepted plan
with no decision, two decisions for one discussion, two successors from one predecessor, a decision
that changed nothing consuming a lineage slot, or a plan attributed to a principal that never wrote
it.

The load-bearing change these tests defend is that the command takes two identifiers. AT-M3.4
Validation 1 fed this slice a plan reading "REWRITE EVERYTHING IN RUST" against a discussion that
had selected something else, and it was recorded as the team's plan; with two callers racing,
commit ordering picked the winner. The remediation removed the input rather than checking it, so
what is asserted below is the absence of the parameter and the equality of the accepted revision to
the planner's own durable message.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import asyncpg
import pytest

from shared.sdk.agent_deliberation.service import DiscussionService
from shared.sdk.agent_deliberation.store import DeliberationStore
from shared.sdk.agent_planning.models import (
    PlanContent,
    PlanLineageError,
    StalePlanRevisionError,
    compute_plan_diff,
)
from shared.sdk.agent_planning.store import PlanningStore
from shared.sdk.agent_planning_decision.models import (
    CANDIDATE_REF_KEY,
    CASE_ACCEPT_DRAFT,
    CASE_CHANGED,
    CASE_INITIAL,
    CASE_NO_CHANGE,
    NO_CHANGE,
    PLAN_ACCEPTED,
    DiscussionNotAdmissibleError,
    PlannerUnavailableError,
    PlanningDecisionConflictError,
    PlanningDecisionStateError,
    build_decision_evidence,
    derive_candidate_correlation_id,
    derive_case,
    derive_idempotency_key,
    evaluate_admissibility,
    is_candidate_for,
    plan_from_candidate,
)
from shared.sdk.agent_planning_decision.service import PlanningDecisionService
from shared.sdk.agent_planning_decision.store import PlanningDecisionStore
from shared.sdk.agent_reasoning.mock_provider import MockReasoningProvider
from shared.sdk.agent_reasoning.models import PlanDraftArtifact, ReasoningRequest
from shared.sdk.agent_team.service import TeamService
from shared.sdk.agent_team.store import TeamStore

from tests.test_at_m3_3_deliberation_store import (
    PLAN,
    AuditRecorder,
    ContestingProvider,
    ConvergingProvider,
    _scenario,
    _start,
)


class Injected(RuntimeError):
    """A failure this test put there on purpose."""


async def _skip_without_migration() -> None:
    store = PlanningDecisionStore()
    try:
        conn = await store._connect()
    except Exception:
        pytest.skip("no reachable PostgreSQL; skipping AT-M3.4 store test")
    try:
        if await conn.fetchval("SELECT to_regclass('public.planning_decisions')") is None:
            pytest.skip("migration 040 not applied; skipping AT-M3.4 store test")
        if not await conn.fetchval(
            "SELECT 1 FROM information_schema.columns WHERE table_name='planning_decisions' "
            "AND column_name='candidate_plan_message_id'"
        ):
            pytest.skip("migration 040 predates the candidate-plan binding; skipping")
    finally:
        await conn.close()


def _service(audit=None, store=None) -> PlanningDecisionService:
    return PlanningDecisionService(store=store, audit_client=audit)


async def _converged(scenario, *, provider=None, key=None) -> dict:
    """Run one discussion to a genuine convergence and return its session row."""
    await _skip_without_migration()
    session = await _start(scenario, provider=provider or ConvergingProvider(), key=key)
    final = await DiscussionService(provider=provider or ConvergingProvider()).run(
        str(session["discussion_id"])
    )
    assert final["session"]["state"] == "converged", final["session"]["stop_reason"]
    return final["session"]


async def _planless_scenario() -> dict:
    """A project with a real team and a Goal that has no PlanRevision at all."""
    await _skip_without_migration()
    store = PlanningDecisionStore()
    conn = await store._connect()
    try:
        project_id = str(
            await conn.fetchval(
                "INSERT INTO projects (title) VALUES ($1) RETURNING id",
                f"m34-{uuid.uuid4().hex[:8]}",
            )
        )
        opener = str(
            await conn.fetchval(
                "INSERT INTO actor_principals (principal_type,display_name) "
                "VALUES ('human',$1) RETURNING principal_id",
                f"m34-opener-{uuid.uuid4().hex[:6]}",
            )
        )
    finally:
        await conn.close()
    await TeamService().form_team(
        project_id,
        goal_ref="m34",
        agent_keys=("project-planner-agent", "qa-agent", "design-review-agent"),
    )
    goal = await PlanningStore().create_goal(
        {
            "project_id": project_id,
            "statement": "deliver a reporting slice a reviewer can read",
            "acceptance_criteria": ["a reviewer can read one report"],
            "constraints": ["non-production only"],
            "created_by": opener,
        }
    )
    return {
        "store": store,
        "project_id": project_id,
        "opened_by": opener,
        "goal_id": str(goal["goal_id"]),
        "plan_revision_id": None,
    }


def _expected_plan(goal: dict) -> dict:
    """The plan the mock planner produces for this Goal, computed independently.

    Only three context fields reach ``PlanContent``: the statement, the acceptance criteria and the
    constraints. That is what makes a candidate deterministic per Goal, and it is what lets these
    tests build a revision the planner will later produce again -- the only way to reach the
    identical-plan outcomes at all.
    """
    artifact = MockReasoningProvider().decompose_plan(
        ReasoningRequest(
            verb="decompose_plan",
            context={
                "goal_statement": goal["statement"],
                "acceptance_criteria": list(goal["acceptance_criteria"] or []),
                "goal_constraints": list(goal["constraints"] or []),
            },
        )
    )
    return artifact.plan.model_dump(mode="json")


async def _counts(project_id: str) -> dict[str, int]:
    conn = await PlanningDecisionStore()._connect()
    pid = uuid.UUID(project_id)
    try:
        return {
            "ledger": await conn.fetchval(
                "SELECT count(*) FROM planning_decisions WHERE project_id=$1", pid
            ),
            "decisions": await conn.fetchval(
                "SELECT count(*) FROM team_decisions WHERE project_id=$1", pid
            ),
            "revisions": await conn.fetchval(
                "SELECT count(*) FROM plan_revisions WHERE project_id=$1", pid
            ),
            "accepted": await conn.fetchval(
                "SELECT count(*) FROM plan_revisions WHERE project_id=$1 AND status='accepted'",
                pid,
            ),
        }
    finally:
        await conn.close()


async def _candidates(project_id: str, discussion_id: str) -> list[dict]:
    messages = await TeamStore().list_messages(project_id)
    return [m for m in messages if is_candidate_for(m, discussion_id)]


async def _invocations(discussion_id: str, result_message_id) -> int:
    if result_message_id is None:
        return 0
    conn = await PlanningDecisionStore()._connect()
    try:
        return await conn.fetchval(
            "SELECT count(*) FROM reasoning_invocations WHERE correlation_id=$1",
            uuid.UUID(
                derive_candidate_correlation_id(
                    discussion_id=discussion_id, result_message_id=result_message_id
                )
            ),
        )
    finally:
        await conn.close()


# --- A. the caller can no longer supply a plan or an author ---------------------------------------


def test_the_command_takes_two_identifiers_and_nothing_else():
    """The substitution defect is closed by the signature, not by a check inside it."""
    import inspect

    signature = inspect.signature(PlanningDecisionService.finalize)
    assert set(signature.parameters) == {"self", "goal_id", "discussion_id"}
    for removed in ("plan", "decided_by", "created_by", "planner_principal_id", "outcome"):
        assert removed not in signature.parameters, removed


# --- B. the accepted plan is the planner's plan ----------------------------------------------------


@pytest.mark.asyncio
async def test_a_converged_discussion_becomes_one_decision_and_the_planners_own_plan():
    scenario = await _scenario()
    session = await _converged(scenario)

    result = await _service().finalize(
        goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
    )

    assert result["created"] is True
    assert result["outcome"] == PLAN_ACCEPTED
    revision = result["plan_revision"]
    decision = result["team_decision"]

    candidates = await _candidates(scenario["project_id"], str(session["discussion_id"]))
    assert len(candidates) == 1
    candidate = candidates[0]
    assert str(candidate["message_id"]) == result["candidate_plan_message_id"]

    # The load-bearing equality: what was accepted IS what the planner wrote, field for field.
    assert revision["plan"] == candidate["content"]["plan"]
    assert revision["plan"] == plan_from_candidate(candidate)
    assert revision["status"] == "accepted"
    assert str(revision["supersedes_revision_id"]) == scenario["plan_revision_id"]
    assert str(revision["trace_ref"]) == str(session["result_message_id"])
    assert str(decision["resulting_plan_revision_id"]) == str(revision["plan_revision_id"])
    assert str(result["planning_decision"]["candidate_plan_message_id"]) == str(
        candidate["message_id"]
    )
    assert await _invocations(str(session["discussion_id"]), session["result_message_id"]) == 1


@pytest.mark.asyncio
async def test_the_candidate_message_is_a_proposal_and_never_a_replan():
    """`replan` means "new PlanRevision" in the approved vocabulary; a candidate may produce none."""
    scenario = await _scenario()
    session = await _converged(scenario)
    await _service().finalize(
        goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
    )
    candidate = (await _candidates(scenario["project_id"], str(session["discussion_id"])))[0]
    assert candidate["message_type"] == "proposal"

    messages = await TeamStore().list_messages(scenario["project_id"])
    assert not [m for m in messages if m["message_type"] == "replan"]
    assert candidate["artifact_refs"][CANDIDATE_REF_KEY] == str(session["discussion_id"])
    assert candidate["artifact_refs"]["reasoning_invocation_id"]
    # A structured artifact, validated by the same model the revision's plan goes through.
    PlanDraftArtifact(**candidate["content"])


# --- input gate -------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_exhausted_discussion_is_refused_and_no_candidate_is_authored():
    scenario = await _scenario()
    await _skip_without_migration()
    session = await _start(scenario, provider=ContestingProvider())
    final = await DiscussionService(provider=ContestingProvider()).run(
        str(session["discussion_id"])
    )
    assert final["session"]["state"] != "converged"

    with pytest.raises(DiscussionNotAdmissibleError) as raised:
        await _service().finalize(
            goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
        )
    assert raised.value.clause == "state"
    assert await _counts(scenario["project_id"]) == {
        "ledger": 0,
        "decisions": 0,
        "revisions": 1,
        "accepted": 0,
    }
    # The gate runs before the planner does: a refused discussion costs no reasoning call.
    assert await _candidates(scenario["project_id"], str(session["discussion_id"])) == []


@pytest.mark.asyncio
async def test_a_cancelled_discussion_is_refused():
    scenario = await _scenario()
    await _skip_without_migration()
    session = await _start(scenario)
    await DiscussionService().cancel(str(session["discussion_id"]))

    with pytest.raises(DiscussionNotAdmissibleError) as raised:
        await _service().finalize(
            goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
        )
    assert raised.value.clause == "state"


@pytest.mark.asyncio
async def test_a_discussion_about_another_goal_is_refused():
    scenario = await _scenario()
    session = await _converged(scenario)
    other = await PlanningStore().create_goal(
        {
            "project_id": scenario["project_id"],
            "statement": "a different goal",
            "created_by": scenario["opened_by"],
        }
    )
    with pytest.raises(DiscussionNotAdmissibleError) as raised:
        await _service().finalize(
            goal_id=str(other["goal_id"]), discussion_id=str(session["discussion_id"])
        )
    assert raised.value.clause == "goal"


@pytest.mark.asyncio
async def test_a_discussion_bound_to_a_superseded_revision_is_refused_and_never_rebound():
    scenario = await _scenario()
    session = await _converged(scenario)
    await PlanningStore().create_successor_revision(
        {
            "goal_id": scenario["goal_id"],
            "expected_current_revision_id": scenario["plan_revision_id"],
            "created_by": scenario["opened_by"],
            "reason": "scope_correction",
            "plan": PLAN,
        }
    )

    with pytest.raises(DiscussionNotAdmissibleError) as raised:
        await _service().finalize(
            goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
        )
    assert raised.value.clause == "currency"

    still = await DeliberationStore().get_session(str(session["discussion_id"]))
    assert still["state"] == "converged"
    assert str(still["plan_revision_id"]) == scenario["plan_revision_id"]
    counts = await _counts(scenario["project_id"])
    assert counts["ledger"] == 0 and counts["decisions"] == 0


# --- F. the changed-plan path ------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_revision_is_created_draft_and_accepted_by_the_decision_not_born_accepted():
    scenario = await _scenario()
    session = await _converged(scenario)

    seen: list[str] = []
    original = PlanningStore.create_successor_revision

    async def watched(self, data, *, conn=None):
        row = await original(self, data, conn=conn)
        seen.append(row["status"])
        return row

    store = PlanningDecisionStore()
    store.planning.create_successor_revision = watched.__get__(store.planning, PlanningStore)

    result = await _service(store=store).finalize(
        goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
    )
    assert seen == ["draft"]
    assert result["plan_revision"]["status"] == "accepted"
    assert result["plan_revision"]["reason"] == "team_decision"

    predecessor = await PlanningStore().get_revision(scenario["plan_revision_id"])
    assert predecessor["status"] == "draft"  # untouched; supersession is derived, not stamped


@pytest.mark.asyncio
async def test_the_predecessor_is_untouched_and_the_diff_is_computed_server_side():
    scenario = await _scenario()
    session = await _converged(scenario)
    planning = PlanningStore()
    before = await planning.get_revision(scenario["plan_revision_id"])

    result = await _service().finalize(
        goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
    )

    assert await planning.get_revision(scenario["plan_revision_id"]) == before
    expected = compute_plan_diff(
        PlanContent(**before["plan"]), PlanContent(**result["plan_revision"]["plan"])
    ).model_dump(mode="json")
    assert result["plan_revision"]["diff"] == expected


# --- G. the current draft, accepted in place ----------------------------------------------------------


@pytest.mark.asyncio
async def test_an_identical_candidate_accepts_the_current_draft_without_a_successor():
    scenario = await _planless_scenario()
    goal = await PlanningStore().get_goal(scenario["goal_id"])
    draft = await PlanningStore().create_initial_revision(
        {
            "goal_id": scenario["goal_id"],
            "created_by": scenario["opened_by"],
            "plan": _expected_plan(goal),
        }
    )
    assert draft["status"] == "draft"
    scenario["plan_revision_id"] = str(draft["plan_revision_id"])
    session = await _converged(scenario)

    result = await _service().finalize(
        goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
    )

    assert result["outcome"] == PLAN_ACCEPTED
    assert str(result["plan_revision"]["plan_revision_id"]) == str(draft["plan_revision_id"])
    assert result["plan_revision"]["status"] == "accepted"
    assert result["plan_revision"]["supersedes_revision_id"] is None
    assert await _counts(scenario["project_id"]) == {
        "ledger": 1,
        "decisions": 1,
        "revisions": 1,
        "accepted": 1,
    }
    ledger = result["planning_decision"]
    assert str(ledger["predecessor_plan_revision_id"]) == str(ledger["resulting_plan_revision_id"])


@pytest.mark.asyncio
async def test_two_discussions_cannot_both_accept_the_same_current_draft():
    scenario = await _planless_scenario()
    goal = await PlanningStore().get_goal(scenario["goal_id"])
    draft = await PlanningStore().create_initial_revision(
        {
            "goal_id": scenario["goal_id"],
            "created_by": scenario["opened_by"],
            "plan": _expected_plan(goal),
        }
    )
    scenario["plan_revision_id"] = str(draft["plan_revision_id"])
    first = await _converged(scenario, key=f"a-{uuid.uuid4().hex}")
    second = await _converged(scenario, key=f"b-{uuid.uuid4().hex}")

    async def consume(session):
        try:
            return await PlanningDecisionService(store=PlanningDecisionStore()).finalize(
                goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
            )
        except Exception as exc:  # noqa: BLE001
            return exc

    outcomes = await asyncio.gather(consume(first), consume(second))
    winners = [o for o in outcomes if not isinstance(o, Exception)]
    losers = [o for o in outcomes if isinstance(o, Exception)]
    assert len(winners) == 1
    assert len(losers) == 1
    assert isinstance(losers[0], (PlanningDecisionConflictError, PlanningDecisionStateError))
    assert await _counts(scenario["project_id"]) == {
        "ledger": 1,
        "decisions": 1,
        "revisions": 1,
        "accepted": 1,
    }


# --- H. no_change ----------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_identical_candidate_against_an_accepted_plan_records_no_change():
    scenario = await _planless_scenario()
    first = await _converged(scenario, key=f"root-{uuid.uuid4().hex}")
    root = await _service().finalize(
        goal_id=scenario["goal_id"], discussion_id=str(first["discussion_id"])
    )
    assert root["outcome"] == PLAN_ACCEPTED
    assert root["plan_revision"]["status"] == "accepted"

    second = await _converged(scenario, key=f"again-{uuid.uuid4().hex}")
    result = await _service().finalize(
        goal_id=scenario["goal_id"], discussion_id=str(second["discussion_id"])
    )

    assert result["outcome"] == NO_CHANGE
    assert result["plan_revision"] is None
    assert result["planning_decision"]["resulting_plan_revision_id"] is None
    assert result["team_decision"]["resulting_plan_revision_id"] is None
    # It still names what it considered and declined to change.
    assert result["planning_decision"]["candidate_plan_message_id"]
    assert str(result["planning_decision"]["predecessor_plan_revision_id"]) == str(
        root["plan_revision"]["plan_revision_id"]
    )
    assert await _counts(scenario["project_id"]) == {
        "ledger": 2,
        "decisions": 2,
        "revisions": 1,
        "accepted": 1,
    }


@pytest.mark.asyncio
async def test_a_no_change_decision_does_not_consume_the_successor_slot():
    """The defect this outcome removes: a decision that changed nothing used to spend the
    predecessor's one and only successor slot on a superseding copy of itself."""
    scenario = await _planless_scenario()
    first = await _converged(scenario, key=f"root-{uuid.uuid4().hex}")
    root = await _service().finalize(
        goal_id=scenario["goal_id"], discussion_id=str(first["discussion_id"])
    )
    second = await _converged(scenario, key=f"again-{uuid.uuid4().hex}")
    replayed = await _service().finalize(
        goal_id=scenario["goal_id"], discussion_id=str(second["discussion_id"])
    )
    assert replayed["outcome"] == NO_CHANGE

    successor = await PlanningStore().create_successor_revision(
        {
            "goal_id": scenario["goal_id"],
            "expected_current_revision_id": str(root["plan_revision"]["plan_revision_id"]),
            "created_by": scenario["opened_by"],
            "reason": "scope_correction",
            "plan": PLAN,
        }
    )
    assert str(successor["supersedes_revision_id"]) == str(
        root["plan_revision"]["plan_revision_id"]
    )


# --- I. no-change race safety -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_successor_appearing_before_a_no_change_decision_fails_it_closed():
    scenario = await _planless_scenario()
    first = await _converged(scenario, key=f"root-{uuid.uuid4().hex}")
    root = await _service().finalize(
        goal_id=scenario["goal_id"], discussion_id=str(first["discussion_id"])
    )
    current_id = str(root["plan_revision"]["plan_revision_id"])
    second = await _converged(scenario, key=f"again-{uuid.uuid4().hex}")

    class Interfering(PlanningDecisionStore):
        """Moves the plan on after admissibility passed, before the decision is written."""

        async def finalize(self, **kwargs):
            await PlanningStore().create_successor_revision(
                {
                    "goal_id": scenario["goal_id"],
                    "expected_current_revision_id": current_id,
                    "created_by": scenario["opened_by"],
                    "reason": "scope_correction",
                    "plan": PLAN,
                }
            )
            return await super().finalize(**kwargs)

    before = await _counts(scenario["project_id"])
    with pytest.raises(StalePlanRevisionError):
        await PlanningDecisionService(store=Interfering()).finalize(
            goal_id=scenario["goal_id"], discussion_id=str(second["discussion_id"])
        )

    after = await _counts(scenario["project_id"])
    assert after["ledger"] == before["ledger"]
    assert after["decisions"] == before["decisions"]
    assert after["revisions"] == before["revisions"] + 1  # the interfering successor only
    assert (await PlanningStore().get_revision(current_id))["status"] == "accepted"


# --- J / L. the changed-plan stale race, and the candidate that survives it -----------------------


@pytest.mark.asyncio
async def test_a_stale_race_fails_closed_but_keeps_the_candidate_as_evidence():
    scenario = await _scenario()
    session = await _converged(scenario)
    planning = PlanningStore()
    before = await planning.get_revision(scenario["plan_revision_id"])

    class Interfering(PlanningDecisionStore):
        async def finalize(self, **kwargs):
            await PlanningStore().create_successor_revision(
                {
                    "goal_id": scenario["goal_id"],
                    "expected_current_revision_id": scenario["plan_revision_id"],
                    "created_by": scenario["opened_by"],
                    "reason": "scope_correction",
                    "plan": PLAN,
                }
            )
            return await super().finalize(**kwargs)

    with pytest.raises(StalePlanRevisionError):
        await PlanningDecisionService(store=Interfering()).finalize(
            goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
        )

    counts = await _counts(scenario["project_id"])
    assert counts["ledger"] == 0 and counts["decisions"] == 0 and counts["accepted"] == 0
    assert await planning.get_revision(scenario["plan_revision_id"]) == before

    # The plan the planner drafted stays, as evidence that it was drafted and not adopted.
    assert len(await _candidates(scenario["project_id"], str(session["discussion_id"]))) == 1
    still = await DeliberationStore().get_session(str(session["discussion_id"]))
    assert still["state"] == "converged"
    assert str(still["plan_revision_id"]) == scenario["plan_revision_id"]


# --- C / D / E. concurrency --------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("attempt", [1, 2, 3])
async def test_eight_workers_finalizing_one_discussion_produce_one_of_everything(attempt):
    scenario = await _scenario()
    session = await _converged(scenario)
    discussion_id = str(session["discussion_id"])

    async def worker():
        try:
            return await PlanningDecisionService(store=PlanningDecisionStore()).finalize(
                goal_id=scenario["goal_id"], discussion_id=discussion_id
            )
        except Exception as exc:  # noqa: BLE001
            return exc

    outcomes = await asyncio.gather(*(worker() for _ in range(8)))
    errors = [o for o in outcomes if isinstance(o, Exception)]
    assert not errors, [type(e).__name__ for e in errors]

    assert len([o for o in outcomes if o["created"]]) == 1
    assert len({str(o["planning_decision"]["planning_decision_id"]) for o in outcomes}) == 1
    assert len({str(o["plan_revision"]["plan_revision_id"]) for o in outcomes}) == 1
    assert len({o["candidate_plan_message_id"] for o in outcomes}) == 1
    assert {o["outcome"] for o in outcomes} == {PLAN_ACCEPTED}

    assert await _counts(scenario["project_id"]) == {
        "ledger": 1,
        "decisions": 1,
        "revisions": 2,
        "accepted": 1,
    }
    assert len(await _candidates(scenario["project_id"], discussion_id)) == 1
    assert await _invocations(discussion_id, session["result_message_id"]) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("attempt", [1, 2])
async def test_eight_workers_on_a_planless_discussion_all_replay_the_canonical_root(attempt):
    """The AT-M3.4 Validation 1 defect: the losers used to receive a raw PlanLineageError."""
    scenario = await _planless_scenario()
    session = await _converged(scenario)
    discussion_id = str(session["discussion_id"])

    async def worker():
        try:
            return await PlanningDecisionService(store=PlanningDecisionStore()).finalize(
                goal_id=scenario["goal_id"], discussion_id=discussion_id
            )
        except Exception as exc:  # noqa: BLE001
            return exc

    outcomes = await asyncio.gather(*(worker() for _ in range(8)))
    errors = [o for o in outcomes if isinstance(o, Exception)]
    assert not errors, [type(e).__name__ for e in errors]

    assert len([o for o in outcomes if o["created"]]) == 1
    assert len([o for o in outcomes if not o["created"]]) == 7
    assert len({str(o["planning_decision"]["planning_decision_id"]) for o in outcomes}) == 1
    assert len({str(o["plan_revision"]["plan_revision_id"]) for o in outcomes}) == 1

    assert await _counts(scenario["project_id"]) == {
        "ledger": 1,
        "decisions": 1,
        "revisions": 1,
        "accepted": 1,
    }
    assert len(await _candidates(scenario["project_id"], discussion_id)) == 1


@pytest.mark.asyncio
async def test_two_planless_discussions_conflict_rather_than_replay():
    """A different discussion losing the root is a real conflict: it has no decision to replay."""
    scenario = await _planless_scenario()
    first = await _converged(scenario, key=f"a-{uuid.uuid4().hex}")
    second = await _converged(scenario, key=f"b-{uuid.uuid4().hex}")

    async def consume(session):
        try:
            return await PlanningDecisionService(store=PlanningDecisionStore()).finalize(
                goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
            )
        except Exception as exc:  # noqa: BLE001
            return exc

    outcomes = await asyncio.gather(consume(first), consume(second))
    winners = [o for o in outcomes if not isinstance(o, Exception)]
    losers = [o for o in outcomes if isinstance(o, Exception)]
    assert len(winners) == 1 and len(losers) == 1
    assert isinstance(losers[0], PlanLineageError)
    assert await _counts(scenario["project_id"]) == {
        "ledger": 1,
        "decisions": 1,
        "revisions": 1,
        "accepted": 1,
    }
    for session in (first, second):
        assert (
            await DeliberationStore().get_session(str(session["discussion_id"]))
        )["state"] == "converged"


@pytest.mark.asyncio
async def test_two_discussions_racing_one_predecessor_yield_one_successor():
    scenario = await _scenario()
    first = await _converged(scenario, key=f"a-{uuid.uuid4().hex}")
    second = await _converged(scenario, key=f"b-{uuid.uuid4().hex}")

    async def consume(session):
        try:
            return await PlanningDecisionService(store=PlanningDecisionStore()).finalize(
                goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
            )
        except Exception as exc:  # noqa: BLE001
            return exc

    outcomes = await asyncio.gather(consume(first), consume(second))
    winners = [o for o in outcomes if not isinstance(o, Exception)]
    losers = [o for o in outcomes if isinstance(o, Exception)]
    assert len(winners) == 1 and len(losers) == 1
    assert isinstance(losers[0], StalePlanRevisionError)
    assert await _counts(scenario["project_id"]) == {
        "ledger": 1,
        "decisions": 1,
        "revisions": 2,
        "accepted": 1,
    }
    # Both deliberations, and both candidate plans, survive.
    for session in (first, second):
        still = await DeliberationStore().get_session(str(session["discussion_id"]))
        assert still["state"] == "converged"
        assert str(still["plan_revision_id"]) == scenario["plan_revision_id"]
        assert len(await _candidates(scenario["project_id"], str(session["discussion_id"]))) == 1


@pytest.mark.asyncio
async def test_a_repeated_command_replays_the_canonical_decision_without_making_a_second():
    scenario = await _scenario()
    session = await _converged(scenario)
    first = await _service().finalize(
        goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
    )
    again = await PlanningDecisionService(store=PlanningDecisionStore()).finalize(
        goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
    )
    assert again["created"] is False
    assert str(again["planning_decision"]["planning_decision_id"]) == str(
        first["planning_decision"]["planning_decision_id"]
    )
    assert str(again["team_decision"]["decision_id"]) == str(first["team_decision"]["decision_id"])
    assert str(again["plan_revision"]["plan_revision_id"]) == str(
        first["plan_revision"]["plan_revision_id"]
    )
    assert again["candidate_plan_message_id"] == first["candidate_plan_message_id"]
    assert await _counts(scenario["project_id"]) == {
        "ledger": 1,
        "decisions": 1,
        "revisions": 2,
        "accepted": 1,
    }


# --- K. actor provenance ------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_plan_is_attributed_to_the_routed_planner_and_to_nobody_else():
    scenario = await _scenario()
    session = await _converged(scenario)
    result = await _service().finalize(
        goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
    )

    participants = await DeliberationStore().list_participants(str(session["discussion_id"]))
    planner = next(
        p for p in participants if "plan_project" in list(p["matched_capabilities"] or [])
    )
    candidate = (await _candidates(scenario["project_id"], str(session["discussion_id"])))[0]

    assert str(candidate["sender_principal_id"]) == str(planner["principal_id"])
    assert str(result["team_decision"]["proposed_by"]) == str(planner["principal_id"])
    assert str(result["plan_revision"]["created_by"]) == str(planner["principal_id"])
    # The human who opened the discussion is not credited with authoring the plan.
    assert str(result["team_decision"]["proposed_by"]) != scenario["opened_by"]


@pytest.mark.asyncio
async def test_a_team_with_no_planner_is_refused_rather_than_attributed_to_anyone():
    scenario = await _scenario(agent_keys=("qa-agent", "design-review-agent"))
    await _skip_without_migration()
    session = await _start(scenario, caps=("verify_quality", "review_design"))
    final = await DiscussionService(provider=ConvergingProvider()).run(
        str(session["discussion_id"])
    )
    if final["session"]["state"] != "converged":
        pytest.skip("this roster could not converge; the planner-absence path is unreachable here")

    with pytest.raises(PlannerUnavailableError):
        await _service().finalize(
            goal_id=scenario["goal_id"], discussion_id=str(final["session"]["discussion_id"])
        )
    counts = await _counts(scenario["project_id"])
    assert counts["ledger"] == 0 and counts["decisions"] == 0


# --- M. atomicity ---------------------------------------------------------------------------------------


def _failing_store(stage: str) -> PlanningDecisionStore:
    class Failing(PlanningDecisionStore):
        async def finalize(self, **kwargs):
            target, name = {
                "revision": (self.planning, "create_successor_revision"),
                "decision": (self.team, "record_decision"),
                "acceptance": (self.planning, "accept_revision"),
            }[stage]
            original = getattr(type(target), name)

            async def boom(*args, **inner):
                await original(target, *args, **inner)
                raise Injected(f"injected failure after {stage}")

            setattr(target, name, boom)
            return await super().finalize(**kwargs)

    return Failing()


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["revision", "decision", "acceptance"])
async def test_a_failure_anywhere_in_the_boundary_leaves_nothing_behind(stage):
    scenario = await _scenario()
    session = await _converged(scenario)
    planning = PlanningStore()
    before_predecessor = await planning.get_revision(scenario["plan_revision_id"])
    before = await _counts(scenario["project_id"])

    with pytest.raises(Injected):
        await PlanningDecisionService(store=_failing_store(stage)).finalize(
            goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
        )

    assert await _counts(scenario["project_id"]) == before
    assert await planning.get_revision(scenario["plan_revision_id"]) == before_predecessor

    # And the same operation then succeeds, reusing the candidate the failed attempt authored.
    retry = await _service().finalize(
        goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
    )
    assert retry["created"] is True
    assert len(await _candidates(scenario["project_id"], str(session["discussion_id"]))) == 1
    assert await _counts(scenario["project_id"]) == {
        "ledger": 1,
        "decisions": 1,
        "revisions": 2,
        "accepted": 1,
    }


@pytest.mark.asyncio
async def test_a_ledger_failure_also_rolls_back_the_decision_and_the_acceptance():
    scenario = await _scenario()
    session = await _converged(scenario)
    donor = await _scenario()
    donor_session = await _converged(donor)
    donor_result = await _service().finalize(
        goal_id=donor["goal_id"], discussion_id=str(donor_session["discussion_id"])
    )
    conn = await PlanningDecisionStore()._connect()
    try:
        donor_key = await conn.fetchval(
            "SELECT idempotency_key FROM planning_decisions WHERE planning_decision_id=$1",
            uuid.UUID(str(donor_result["planning_decision"]["planning_decision_id"])),
        )
    finally:
        await conn.close()

    class CollidingKey(PlanningDecisionStore):
        async def finalize(self, **kwargs):
            return await super().finalize(**{**kwargs, "idempotency_key": donor_key})

    before = await _counts(scenario["project_id"])
    with pytest.raises(Exception):
        await PlanningDecisionService(store=CollidingKey()).finalize(
            goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
        )
    assert await _counts(scenario["project_id"]) == before


# --- N. the approval and execution boundary -------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_team_decision_creates_no_approval_and_no_work_item():
    scenario = await _scenario()
    session = await _converged(scenario)
    conn = await PlanningDecisionStore()._connect()
    try:
        tables = [
            r["tablename"]
            for r in await conn.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' AND ("
                "tablename LIKE '%approval%' OR tablename LIKE '%policy%' "
                "OR tablename LIKE '%work_item%')"
            )
        ]
        before = {t: await conn.fetchval(f"SELECT count(*) FROM {t}") for t in tables}
    finally:
        await conn.close()

    await _service().finalize(
        goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
    )

    conn = await PlanningDecisionStore()._connect()
    try:
        after = {t: await conn.fetchval(f"SELECT count(*) FROM {t}") for t in tables}
    finally:
        await conn.close()
    assert tables, "expected at least one approval/policy/work-item table to be checked"
    assert before == after


# --- audit ------------------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_metadata_carries_identifiers_and_no_plan_or_message_body():
    scenario = await _scenario()
    session = await _converged(scenario)
    audit = AuditRecorder()
    result = await _service(audit=audit).finalize(
        goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
    )

    recorded = [e for e in audit.events if e["decision_type"] == "planning_decision_recorded"]
    assert len(recorded) == 1
    refs = recorded[0]["artifact_refs"]
    assert refs["candidate_plan_message_id"] == result["candidate_plan_message_id"]
    assert refs["planner_principal_id"] == str(result["team_decision"]["proposed_by"])
    assert refs["outcome"] == PLAN_ACCEPTED

    blob = json.dumps(audit.events, default=str)
    assert result["plan_revision"]["plan"]["objective"] not in blob
    for marker in ("chain_of_thought", "scratchpad", "raw_prompt", "completion", "api_key"):
        assert marker not in blob


@pytest.mark.asyncio
async def test_a_rolled_back_finalization_records_no_success_event():
    scenario = await _scenario()
    session = await _converged(scenario)
    audit = AuditRecorder()
    with pytest.raises(Injected):
        await PlanningDecisionService(
            store=_failing_store("acceptance"), audit_client=audit
        ).finalize(goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"]))
    assert "planning_decision_recorded" not in [e["decision_type"] for e in audit.events]


# --- the ledger and the evidence read --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_recorded_planning_decision_cannot_be_rewritten():
    scenario = await _scenario()
    session = await _converged(scenario)
    result = await _service().finalize(
        goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
    )
    decision_id = uuid.UUID(str(result["planning_decision"]["planning_decision_id"]))

    conn = await PlanningDecisionStore()._connect()
    try:
        for column, value in (
            ("outcome", "'no_change'"),
            ("candidate_plan_message_id", "NULL"),
            ("resulting_plan_revision_id", "NULL"),
        ):
            with pytest.raises(asyncpg.PostgresError):
                await conn.execute(
                    f"UPDATE planning_decisions SET {column}={value} "
                    "WHERE planning_decision_id=$1",
                    decision_id,
                )
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_the_evidence_read_reconstructs_the_lineage_including_the_candidate_plan():
    scenario = await _scenario()
    session = await _converged(scenario)
    result = await _service().finalize(
        goal_id=scenario["goal_id"], discussion_id=str(session["discussion_id"])
    )
    evidence = await _service().get_evidence(
        str(result["planning_decision"]["planning_decision_id"])
    )

    assert evidence["outcome"] == PLAN_ACCEPTED
    assert evidence["candidate_plan"]["message_id"] == result["candidate_plan_message_id"]
    assert evidence["candidate_plan"]["plan"] == result["plan_revision"]["plan"]
    assert evidence["candidate_plan"]["reasoning_invocation_id"]
    assert evidence["convergence_result"]["message_id"] == str(session["result_message_id"])
    assert evidence["proposals"] and all(p["discussion_intent"] for p in evidence["proposals"])
    # The candidate is not double-counted as one of the options the room weighed.
    assert result["candidate_plan_message_id"] not in [
        p["message_id"] for p in evidence["proposals"]
    ]
    assert str(evidence["team_decision_id"]) == str(result["team_decision"]["decision_id"])


@pytest.mark.asyncio
async def test_database_wide_invariants_hold():
    await _skip_without_migration()
    conn = await PlanningDecisionStore()._connect()
    try:
        checks = {
            "plan_accepted with no resulting revision": (
                "SELECT count(*) FROM planning_decisions "
                "WHERE outcome='plan_accepted' AND resulting_plan_revision_id IS NULL"
            ),
            "no_change with a resulting revision": (
                "SELECT count(*) FROM planning_decisions "
                "WHERE outcome='no_change' AND resulting_plan_revision_id IS NOT NULL"
            ),
            "a ledger row with no candidate plan": (
                "SELECT count(*) FROM planning_decisions WHERE candidate_plan_message_id IS NULL"
            ),
            "decision and ledger disagree on the revision": (
                "SELECT count(*) FROM planning_decisions pd JOIN team_decisions td "
                "ON td.decision_id = pd.team_decision_id "
                "WHERE td.resulting_plan_revision_id IS DISTINCT FROM pd.resulting_plan_revision_id"
            ),
            "a decided revision that is not accepted": (
                "SELECT count(*) FROM planning_decisions pd JOIN plan_revisions r "
                "ON r.plan_revision_id = pd.resulting_plan_revision_id WHERE r.status <> 'accepted'"
            ),
            "a revision claimed by two decisions": (
                "SELECT count(*) FROM (SELECT resulting_plan_revision_id FROM planning_decisions "
                "WHERE resulting_plan_revision_id IS NOT NULL GROUP BY 1 HAVING count(*) > 1) x"
            ),
            "a decision whose revision plan differs from its candidate": (
                "SELECT count(*) FROM planning_decisions pd "
                "JOIN plan_revisions r ON r.plan_revision_id = pd.resulting_plan_revision_id "
                "JOIN team_messages m ON m.message_id = pd.candidate_plan_message_id "
                "WHERE r.plan IS DISTINCT FROM (m.content->'plan')"
            ),
            "a candidate authored by someone other than the decision's proposer": (
                "SELECT count(*) FROM planning_decisions pd "
                "JOIN team_decisions td ON td.decision_id = pd.team_decision_id "
                "JOIN team_messages m ON m.message_id = pd.candidate_plan_message_id "
                "WHERE m.sender_principal_id <> td.proposed_by"
            ),
            "two decompose_plan invocations for one discussion": (
                "SELECT count(*) FROM (SELECT correlation_id FROM reasoning_invocations "
                "WHERE reasoning_verb='decompose_plan' GROUP BY 1 HAVING count(*) > 1) x"
            ),
            "two candidate messages for one discussion": (
                "SELECT count(*) FROM (SELECT artifact_refs->>'candidate_plan_for_discussion' AS d "
                "FROM team_messages WHERE artifact_refs ? 'candidate_plan_for_discussion' "
                "GROUP BY 1 HAVING count(*) > 1) x"
            ),
        }
        for label, sql in checks.items():
            assert await conn.fetchval(sql) == 0, label
    finally:
        await conn.close()


# --- pure units ---------------------------------------------------------------------------------------------


def test_admissibility_names_the_clause_that_failed():
    assert (
        evaluate_admissibility(
            discussion=None, goal_id="g", current_plan_revision_id=None
        ).clause
        == "exists"
    )

    base = {
        "state": "converged",
        "stop_reason": "convergence_reached",
        "result_message_id": "m",
        "goal_id": "g",
        "plan_revision_id": "r1",
    }
    assert (
        evaluate_admissibility(
            discussion={**base, "state": "exhausted"}, goal_id="g", current_plan_revision_id="r1"
        ).clause
        == "state"
    )
    assert (
        evaluate_admissibility(
            discussion={**base, "result_message_id": None},
            goal_id="g",
            current_plan_revision_id="r1",
        ).clause
        == "result"
    )
    assert (
        evaluate_admissibility(
            discussion=base, goal_id="other", current_plan_revision_id="r1"
        ).clause
        == "goal"
    )
    stale = evaluate_admissibility(discussion=base, goal_id="g", current_plan_revision_id="r2")
    assert stale.clause == "currency" and not stale.admissible
    assert evaluate_admissibility(
        discussion=base, goal_id="g", current_plan_revision_id="r1"
    ).admissible


def test_the_case_is_derived_from_the_plans_never_requested():
    plan = {"objective": "o", "steps": [{"step_key": "a", "title": "t"}]}
    other = {"objective": "different", "steps": []}
    assert derive_case(current_revision=None, candidate_plan=plan) == CASE_INITIAL
    assert (
        derive_case(current_revision={"plan": other, "status": "accepted"}, candidate_plan=plan)
        == CASE_CHANGED
    )
    assert (
        derive_case(current_revision={"plan": plan, "status": "draft"}, candidate_plan=plan)
        == CASE_ACCEPT_DRAFT
    )
    assert (
        derive_case(current_revision={"plan": plan, "status": "accepted"}, candidate_plan=plan)
        == CASE_NO_CHANGE
    )
    # An unreadable predecessor counts as DIFFERENT, never accidentally equal.
    assert (
        derive_case(
            current_revision={"plan": {"steps": [{"step_id": "x"}]}, "status": "accepted"},
            candidate_plan=plan,
        )
        == CASE_CHANGED
    )
    with pytest.raises(PlanningDecisionStateError):
        derive_case(current_revision={"plan": plan, "status": "rejected"}, candidate_plan=plan)


def test_a_candidate_is_identified_by_reference_not_by_shape():
    discussion = str(uuid.uuid4())
    marked = {"message_type": "proposal", "artifact_refs": {CANDIDATE_REF_KEY: discussion}}
    assert is_candidate_for(marked, discussion)
    assert not is_candidate_for(marked, str(uuid.uuid4()))
    # A deliberation proposal that merely CONTAINS a plan is not the candidate.
    assert not is_candidate_for(
        {"message_type": "proposal", "content": {"plan": {}}, "artifact_refs": {}}, discussion
    )
    assert not is_candidate_for(
        {"message_type": "challenge", "artifact_refs": {CANDIDATE_REF_KEY: discussion}}, discussion
    )


def test_a_candidate_without_a_structured_plan_is_refused():
    with pytest.raises(PlanningDecisionStateError):
        plan_from_candidate({"message_id": "m", "content": {}})
    with pytest.raises(PlanningDecisionStateError):
        plan_from_candidate({"message_id": "m", "content": {"plan": "just do it"}})
    good = {"objective": "o", "steps": [{"step_key": "a", "title": "t"}]}
    assert plan_from_candidate({"message_id": "m", "content": {"plan": good}})["objective"] == "o"


def test_the_identity_keys_are_derived_and_stable():
    key = derive_idempotency_key(discussion_id="d", result_message_id="m")
    assert key == derive_idempotency_key(discussion_id="d", result_message_id="m")
    assert key != derive_idempotency_key(discussion_id="d", result_message_id="other")
    correlation = derive_candidate_correlation_id(discussion_id="d", result_message_id="m")
    assert uuid.UUID(correlation)
    assert correlation == derive_candidate_correlation_id(discussion_id="d", result_message_id="m")


def test_decision_evidence_comes_from_the_summary_and_excludes_the_candidate():
    discussion = str(uuid.uuid4())
    result_message = {
        "message_id": "r",
        "summary": "aligned",
        "content": {
            "selected_option": "the boring way",
            "options_considered": ["the boring way", "the clever way"],
            "rationale_summary": "fewest moving parts",
        },
    }
    messages = [
        result_message,
        {"message_id": "p1", "message_type": "proposal", "summary": "a deliberation proposal"},
        {"message_id": "c1", "message_type": "challenge", "summary": "an objection"},
        {
            "message_id": "cand",
            "message_type": "proposal",
            "summary": "the candidate plan",
            "artifact_refs": {CANDIDATE_REF_KEY: discussion},
        },
    ]
    evidence = build_decision_evidence(
        result_message=result_message, messages=messages, turns=[], discussion_id=discussion
    )
    assert evidence.selected_option == "the boring way"
    assert list(evidence.options_considered) == ["the boring way", "the clever way"]
    assert evidence.proposal_message_ids == ("p1",)
    assert evidence.challenge_message_ids == ("c1",)


def test_unresolved_concerns_are_reported_rather_than_suppressed():
    result_message = {
        "message_id": "r",
        "summary": "converged",
        "content": {"selected_option": "go", "options_considered": ["go"]},
    }
    evidence = build_decision_evidence(
        result_message=result_message,
        messages=[result_message],
        turns=[
            {"intent": "challenge", "concern_count": 2},
            {"intent": "support", "concern_count": 0},
        ],
        discussion_id=str(uuid.uuid4()),
    )
    assert evidence.dissent_summary is not None
    assert "2 concern" in evidence.dissent_summary
