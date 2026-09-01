"""Step AT-M3.5 -- shared scenario builders for the delegation tests against a real PostgreSQL.

Every scenario here builds the REAL upstream lineage rather than a fake: a project row, a genuine
AT-M2 team formed from the capability seed, an AT-M3.2 Goal, and a PlanRevision taken through the
real draft -> accepted transition. Nothing about the delegation guarantees is provable against a
double -- "eight workers produce one graph" and "a superseded revision cannot dispatch" are
statements about PostgreSQL, not about Python.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from shared.sdk.agent_planning.store import PlanningStore
from shared.sdk.agent_team.service import TeamService
from shared.sdk.plan_delegation.store import PlanDelegationStore

#: A three-step chain whose capabilities are covered by the real agent seed:
#: design-review-agent -> development-agent -> qa-agent.
CHAIN_PLAN: dict[str, Any] = {
    "objective": "deliver a reporting slice a reviewer can read",
    "acceptance_criteria": ["a reviewer can read one report"],
    "steps": [
        {
            "step_key": "design",
            "title": "Design the reporting slice",
            "description": "Decide the shape of the report.",
            "required_capabilities": ["review_design"],
            "expected_outputs": ["a design note"],
        },
        {
            "step_key": "build",
            "title": "Build the reporting slice",
            "required_capabilities": ["generate_code"],
            "expected_outputs": ["the slice"],
            "depends_on": ["design"],
        },
        {
            "step_key": "verify",
            "title": "Verify the reporting slice",
            "required_capabilities": ["verify_quality"],
            "expected_outputs": ["a verification result"],
            "depends_on": ["build"],
        },
    ],
}

#: Two independent roots converging on one step -- the fan-in case.
FAN_IN_PLAN: dict[str, Any] = {
    "objective": "two independent halves, then one join",
    "steps": [
        {
            "step_key": "left",
            "title": "Left half",
            "required_capabilities": ["review_design"],
        },
        {
            "step_key": "right",
            "title": "Right half",
            "required_capabilities": ["generate_code"],
        },
        {
            "step_key": "join",
            "title": "Join the halves",
            "required_capabilities": ["verify_quality"],
            "depends_on": ["left", "right"],
        },
    ],
}

#: One step requiring a capability no seeded agent declares.
UNSERVED_PLAN: dict[str, Any] = {
    "objective": "work this team cannot take",
    "steps": [
        {
            "step_key": "impossible",
            "title": "Something nobody declares",
            "required_capabilities": ["generate_code", "verify_quality"],
        }
    ],
}

DEFAULT_TEAM = (
    "design-review-agent",
    "development-agent",
    "qa-agent",
    "project-planner-agent",
)


async def store_or_skip() -> PlanDelegationStore:
    """Skip rather than fail when this workstation has no database or no migration 042."""
    store = PlanDelegationStore()
    try:
        conn = await store._connect()
    except Exception:
        pytest.skip("no reachable PostgreSQL; skipping AT-M3.5 store test")
    try:
        for table in (
            "goal_execution_lineage",
            "plan_execution_graphs",
            "plan_execution_units",
            "plan_execution_dispatches",
        ):
            if await conn.fetchval(f"SELECT to_regclass('public.{table}')") is None:
                pytest.skip(f"migration 042 not applied ({table} missing); skipping")
    finally:
        await conn.close()
    return store


async def scenario(
    *,
    plan: dict[str, Any] | None = None,
    agent_keys: tuple[str, ...] = DEFAULT_TEAM,
    accept: bool = True,
) -> dict[str, Any]:
    """A project with a real team, a Goal, and a PlanRevision -- accepted unless asked otherwise."""
    store = await store_or_skip()
    conn = await store._connect()
    try:
        project_id = str(
            await conn.fetchval(
                "INSERT INTO projects (title) VALUES ($1) RETURNING id",
                f"m35-{uuid.uuid4().hex[:8]}",
            )
        )
        author = str(
            await conn.fetchval(
                "INSERT INTO actor_principals (principal_type,display_name) "
                "VALUES ('human',$1) RETURNING principal_id",
                f"m35-author-{uuid.uuid4().hex[:6]}",
            )
        )
    finally:
        await conn.close()

    if agent_keys:
        await TeamService().form_team(project_id, goal_ref="m35", agent_keys=agent_keys)

    planning = PlanningStore()
    goal = await planning.create_goal(
        {
            "project_id": project_id,
            "statement": "deliver a reporting slice a reviewer can read",
            "acceptance_criteria": ["a reviewer can read one report"],
            "constraints": ["non-production only"],
            "created_by": author,
        }
    )
    revision = await planning.create_initial_revision(
        {
            "goal_id": str(goal["goal_id"]),
            "created_by": author,
            "plan": plan if plan is not None else CHAIN_PLAN,
        }
    )
    if accept:
        await planning.accept_revision(revision["plan_revision_id"])

    return {
        "store": store,
        "planning": planning,
        "project_id": project_id,
        "author": author,
        "goal_id": str(goal["goal_id"]),
        "plan_revision_id": str(revision["plan_revision_id"]),
    }


async def supersede(case: dict[str, Any], *, plan: dict[str, Any] | None = None) -> str:
    """Append an accepted successor, making the scenario's revision no longer current."""
    successor = await case["planning"].create_successor_revision(
        {
            "goal_id": case["goal_id"],
            "expected_current_revision_id": case["plan_revision_id"],
            "created_by": case["author"],
            "reason": "team_decision",
            "plan": plan if plan is not None else CHAIN_PLAN,
        }
    )
    await case["planning"].accept_revision(successor["plan_revision_id"])
    return str(successor["plan_revision_id"])


async def units_by_step(store: PlanDelegationStore, plan_revision_id: str) -> dict[str, Any]:
    graph = await store.get_graph(plan_revision_id)
    return {unit["step_key"]: unit for unit in graph["units"]}


async def cancel_primary_work_item(store: PlanDelegationStore, goal_id: str) -> None:
    """Cancel the Goal's execution root through the EXISTING work-item status, not a new model."""
    conn = await store._connect()
    try:
        await conn.execute(
            """
            UPDATE project_work_items SET status='cancelled', lifecycle_state='cancelled'
            WHERE id = (SELECT primary_work_item_id FROM goal_execution_lineage WHERE goal_id=$1)
            """,
            uuid.UUID(goal_id),
        )
    finally:
        await conn.close()


class RecordingBus:
    """An in-process stand-in for the Redis bus, for the tests that are about DB state.

    The stream semantics are asserted against a REAL local Redis in
    ``test_at_m3_5_dispatch_stream.py``; this one only records what was published so a database
    test does not need a broker to run.
    """

    def __init__(self, fail: bool = False) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []
        self.fail = fail

    async def publish_event(self, stream: str, event: dict[str, Any]) -> str:
        if self.fail:
            raise RuntimeError("broker unavailable")
        self.published.append((stream, event))
        return f"0-{len(self.published)}"

    def dispatches(self) -> list[dict[str, Any]]:
        return [e for _, e in self.published if e.get("event") == "plan_step.dispatched"]


__all__ = [
    "CHAIN_PLAN",
    "DEFAULT_TEAM",
    "FAN_IN_PLAN",
    "RecordingBus",
    "UNSERVED_PLAN",
    "cancel_primary_work_item",
    "scenario",
    "store_or_skip",
    "supersede",
    "units_by_step",
]
