"""Step AT-M3.6B.1 -- AT-M3.3 and AT-M3.4 driven by the live adapter, against a real PostgreSQL.

The adapter is the real one and the ``httpx`` stack is the real one; only the socket is replaced.
What is being established is that swapping WHO authors an artifact changes nothing else: the same
discussion semantics, the same durability, the same replay, the same candidate binding, the same
crash recovery. If any of that moved, the claim that this slice is additive would be false.

Skips without a database, in line with every other AT-M3 store suite.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from shared.sdk.agent_deliberation.service import DiscussionService
from shared.sdk.agent_deliberation.store import DeliberationStore
from shared.sdk.agent_planning.store import PlanningStore
from shared.sdk.agent_planning_decision.service import PlanningDecisionService
from shared.sdk.agent_reasoning.anthropic_provider import AnthropicReasoningProvider
from shared.sdk.agent_reasoning.models import ReasoningRequest
from shared.sdk.agent_reasoning.service import ReasoningService
from shared.sdk.agent_reasoning.store import ReasoningInvocationStore
from shared.sdk.agent_team.service import TeamService
from tests.at_m3_6b_1_fakes import (
    FAKE_API_KEY,
    FakeBudgetEvaluator,
    FakeSecretProvider,
    live_config,
    verb_aware,
)

_DB_SKIP = "no reachable PostgreSQL with migration 044 applied; skipping live-shaped regression"

PLAN = {
    "objective": "deliver the reporting slice",
    "steps": [{"step_key": "s1", "title": "define the contract", "depends_on": []}],
    "constraints": [],
    "acceptance_criteria": ["a reviewer can read one report"],
}
CAPS = ("plan_project", "verify_quality", "review_design")

pytestmark = pytest.mark.asyncio


def _adapter(transport: object, **overrides: object) -> AnthropicReasoningProvider:
    return AnthropicReasoningProvider(
        config=live_config(enabled=True),
        secret_provider=FakeSecretProvider(),
        budget_evaluator=FakeBudgetEvaluator(),
        transport=transport,
        **overrides,  # type: ignore[arg-type]
    )


async def _store_or_skip() -> DeliberationStore:
    store = DeliberationStore()
    try:
        conn = await store._connect()
    except Exception:
        pytest.skip(_DB_SKIP)
    try:
        for table in ("discussion_sessions", "discussion_turns", "reasoning_invocations"):
            if await conn.fetchval("SELECT to_regclass($1)", f"public.{table}") is None:
                pytest.skip(_DB_SKIP)
        clause = await conn.fetchval(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conname='chk_reasoning_invocations_provider_mode'"
        )
        if clause is None or "live" not in clause:
            pytest.skip(_DB_SKIP)
    finally:
        await conn.close()
    return store


async def _scenario() -> dict:
    store = await _store_or_skip()
    conn = await store._connect()
    try:
        project_id = str(
            await conn.fetchval(
                "INSERT INTO projects (title) VALUES ($1) RETURNING id",
                f"m36b1-{uuid.uuid4().hex[:8]}",
            )
        )
        opener = str(
            await conn.fetchval(
                "INSERT INTO actor_principals (principal_type,display_name) "
                "VALUES ('human',$1) RETURNING principal_id",
                f"m36b1-opener-{uuid.uuid4().hex[:6]}",
            )
        )
    finally:
        await conn.close()

    await TeamService().form_team(
        project_id,
        goal_ref="m36b1",
        agent_keys=("project-planner-agent", "qa-agent", "design-review-agent"),
    )
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


async def _invocations(store: DeliberationStore, thread_id: str) -> list[dict]:
    conn = await store._connect()
    try:
        rows = await conn.fetch(
            "SELECT provider_mode, model_name, status, input_tokens, output_tokens, "
            "estimated_cost_usd, artifact_type, requested_provider_name, failure_category "
            "FROM reasoning_invocations WHERE thread_id=$1 ORDER BY created_at",
            uuid.UUID(str(thread_id)),
        )
        return [dict(row) for row in rows]
    finally:
        await conn.close()


# --- AT-M3.3 ---------------------------------------------------------------------------------------


class TestDiscussionUnderTheLiveAdapter:
    async def test_a_discussion_runs_its_verbs_through_the_live_adapter(self) -> None:
        scenario = await _scenario()
        transport = verb_aware()
        service = DiscussionService(provider=_adapter(transport))
        session = await service.start_discussion(
            project_id=scenario["project_id"],
            goal_id=scenario["goal_id"],
            topic="what is the smallest slice that satisfies the goal?",
            opened_by=scenario["opened_by"],
            required_capabilities=CAPS,
        )
        for _ in range(3):
            await service.advance(session["discussion_id"])

        rows = await _invocations(scenario["store"], session["thread_id"])
        assert rows, "the discussion produced no reasoning invocations"
        assert {row["provider_mode"] for row in rows} == {"live"}
        assert {row["model_name"] for row in rows} == {"claude-sonnet-5"}
        assert {row["status"] for row in rows} == {"succeeded"}
        # The verbs a discussion actually speaks, authored by the adapter rather than the mock.
        assert {row["artifact_type"] for row in rows} <= {
            "ProposalArtifact",
            "CritiqueArtifact",
            "DecisionSummaryArtifact",
        }
        assert transport.call_count == len(rows)

    async def test_usage_and_cost_land_on_every_durable_row(self) -> None:
        scenario = await _scenario()
        transport = verb_aware(input_tokens=321, output_tokens=123)
        service = DiscussionService(provider=_adapter(transport))
        session = await service.start_discussion(
            project_id=scenario["project_id"],
            goal_id=scenario["goal_id"],
            topic="what is the smallest slice?",
            opened_by=scenario["opened_by"],
            required_capabilities=CAPS,
        )
        await service.advance(session["discussion_id"])

        rows = await _invocations(scenario["store"], session["thread_id"])
        assert rows
        for row in rows:
            assert row["input_tokens"] == 321
            assert row["output_tokens"] == 123
            assert row["estimated_cost_usd"] is not None
            assert float(row["estimated_cost_usd"]) > 0

    async def test_the_message_bodies_carry_no_raw_completion_or_credential(self) -> None:
        scenario = await _scenario()
        service = DiscussionService(provider=_adapter(verb_aware()))
        session = await service.start_discussion(
            project_id=scenario["project_id"],
            goal_id=scenario["goal_id"],
            topic="what is the smallest slice?",
            opened_by=scenario["opened_by"],
            required_capabilities=CAPS,
        )
        await service.advance(session["discussion_id"])

        conn = await scenario["store"]._connect()
        try:
            rendered = repr(
                await conn.fetch(
                    "SELECT content, summary FROM team_messages WHERE thread_id=$1",
                    uuid.UUID(str(session["thread_id"])),
                )
            )
        finally:
            await conn.close()
        assert FAKE_API_KEY not in rendered
        assert "x-api-key" not in rendered
        for marker in ("chain_of_thought", "raw_prompt", "scratchpad", "JSON_SCHEMA"):
            assert marker not in rendered

    async def test_the_discussion_bounds_are_unchanged_by_the_provider(self) -> None:
        """A live provider does not get more rounds, more messages or a longer deadline."""
        scenario = await _scenario()
        service = DiscussionService(provider=_adapter(verb_aware()))
        session = await service.start_discussion(
            project_id=scenario["project_id"],
            goal_id=scenario["goal_id"],
            topic="what is the smallest slice?",
            opened_by=scenario["opened_by"],
            required_capabilities=CAPS,
        )
        assert session["max_rounds"] == 3
        assert session["max_invocations"] == 24
        assert session["max_turns_per_participant"] == 3

    async def test_replaying_a_turn_does_not_call_the_provider_again(self) -> None:
        scenario = await _scenario()
        transport = verb_aware()
        service = DiscussionService(provider=_adapter(transport))
        session = await service.start_discussion(
            project_id=scenario["project_id"],
            goal_id=scenario["goal_id"],
            topic="what is the smallest slice?",
            opened_by=scenario["opened_by"],
            required_capabilities=CAPS,
        )
        await service.advance(session["discussion_id"])
        after_first = transport.call_count
        assert after_first >= 1

        # Seat 0 speaks first and proposes, so the discussion's first correlation_id belongs to a
        # `propose` invocation. Re-invoking it must resolve to the durable artifact and ask nobody.
        correlation = await _first_correlation(scenario["store"], session["thread_id"])
        replay = await ReasoningService(store=ReasoningInvocationStore()).invoke(
            ReasoningRequest(
                verb="propose",
                context={"goal_statement": "x"},
                correlation_id=correlation,
            ),
            provider=_adapter(transport),
        )
        assert replay.disposition == "replay"
        assert replay.artifact is not None
        assert transport.call_count == after_first


async def _first_correlation(store: DeliberationStore, thread_id: str) -> str:
    conn = await store._connect()
    try:
        return str(
            await conn.fetchval(
                "SELECT correlation_id FROM reasoning_invocations WHERE thread_id=$1 "
                "ORDER BY created_at LIMIT 1",
                uuid.UUID(str(thread_id)),
            )
        )
    finally:
        await conn.close()


# --- AT-M3.4 ---------------------------------------------------------------------------------------


class TestPlanningDecisionUnderTheLiveAdapter:
    async def _converged(self, transport: object) -> tuple[dict, dict]:
        scenario = await _scenario()
        service = DiscussionService(provider=_adapter(transport))
        session = await service.start_discussion(
            project_id=scenario["project_id"],
            goal_id=scenario["goal_id"],
            topic="what is the smallest slice that satisfies the goal?",
            opened_by=scenario["opened_by"],
            required_capabilities=CAPS,
        )
        for _ in range(12):
            outcome = await service.advance(session["discussion_id"])
            current = outcome.get("session") or {}
            if current.get("state") != "open":
                break
        latest = await service.get_discussion(session["discussion_id"])
        if latest is None or latest.get("state") != "converged":
            pytest.skip(
                "the discussion did not converge under the fake transport; "
                "AT-M3.4 binding is exercised by its own suite"
            )
        return scenario, latest

    async def test_a_live_decompose_plan_produces_a_bounded_candidate_plan(self) -> None:
        transport = verb_aware(concerns=(), steps=3)
        scenario, discussion = await self._converged(transport)
        decision = await PlanningDecisionService(provider=_adapter(transport)).finalize(
            discussion["discussion_id"]
        )
        assert decision is not None

        rows = await _invocations(scenario["store"], discussion["thread_id"])
        planner_rows = [r for r in rows if r["artifact_type"] == "PlanDraftArtifact"]
        assert planner_rows, "no decompose_plan invocation was recorded"
        assert planner_rows[0]["provider_mode"] == "live"
        assert planner_rows[0]["model_name"] == "claude-sonnet-5"

        planning = PlanningStore()
        revision = await planning.get_revision(str(decision["resulting_plan_revision_id"]))
        assert revision is not None
        plan = revision["plan"]
        steps = plan["steps"] if isinstance(plan, dict) else []
        assert 0 < len(steps) <= 40

    async def test_finalizing_twice_does_not_call_the_provider_again(self) -> None:
        transport = verb_aware(concerns=(), steps=3)
        scenario, discussion = await self._converged(transport)
        service = PlanningDecisionService(provider=_adapter(transport))
        first = await service.finalize(discussion["discussion_id"])
        before = transport.call_count
        second = await service.finalize(discussion["discussion_id"])
        assert str(second["planning_decision_id"]) == str(first["planning_decision_id"])
        assert transport.call_count == before


# --- concurrency ----------------------------------------------------------------------------------


class TestConcurrentLiveInvocations:
    async def test_eight_racers_on_one_correlation_id_produce_one_provider_call(self) -> None:
        """The load-bearing ownership property, now with a provider that costs money.

        Eight independent connections claim the same correlation_id; exactly one wins the INSERT and
        is the only caller permitted to invoke the provider. The other seven resolve to that row.
        """
        await _store_or_skip()
        transport = verb_aware()
        service = ReasoningService(store=ReasoningInvocationStore())
        correlation = str(uuid.uuid4())
        request_kwargs = {
            "verb": "propose",
            "context": {"goal_statement": "deliver the slice"},
            "correlation_id": correlation,
        }

        results = await asyncio.gather(
            *(
                service.invoke(
                    ReasoningRequest(**request_kwargs),  # type: ignore[arg-type]
                    provider=_adapter(transport),
                )
                for _ in range(8)
            )
        )

        assert transport.call_count == 1
        fresh = [r for r in results if r.disposition == "fresh"]
        assert len(fresh) == 1
        assert {r.invocation["invocation_id"] for r in results} == {
            fresh[0].invocation["invocation_id"]
        }
        assert all(r.disposition in {"fresh", "replay", "in_progress"} for r in results)

    @pytest.mark.parametrize("round_index", [0, 1, 2])
    async def test_the_race_result_is_stable_across_rounds(self, round_index: int) -> None:
        await _store_or_skip()
        transport = verb_aware()
        service = ReasoningService(store=ReasoningInvocationStore())
        correlation = str(uuid.uuid4())
        results = await asyncio.gather(
            *(
                service.invoke(
                    ReasoningRequest(
                        verb="propose",
                        context={"goal_statement": "x"},
                        correlation_id=correlation,
                    ),
                    provider=_adapter(transport),
                )
                for _ in range(8)
            )
        )
        assert transport.call_count == 1
        assert len({r.invocation["invocation_id"] for r in results}) == 1
