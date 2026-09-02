"""Step AT-M3.5 -- migration 042 against a real PostgreSQL, forwards and backwards.

Independent Validation 1 found a supported migration sequence that produced duplicated business
work:

    DOWN     the four AT-M3.5 tables are dropped. The child ``project_work_items`` a
             materialization created, and their dependency edges, are deliberately NOT dropped --
             they belong to the project's execution lineage. But the dropped tables were the only
             record of WHICH work item is which plan step, so that identity is now gone.
    UP       empty schema. ``uq_peu_revision_step`` has nothing left to collide with.
    materialize the SAME accepted PlanRevision
             not a replay -- the graph it would replay does not exist -- so a SECOND full set of
             child work items and edges is created for the same steps of the same plan.

The fix is to remove the sequence rather than repair its end: once any materialization evidence
exists, DOWN refuses and changes nothing. These tests run each migration file against real
PostgreSQL on its own throwaway database, because "the transaction rolled back and the evidence
survived" is a statement about PostgreSQL and cannot be shown any other way.
"""

from __future__ import annotations

import os
import re
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest

from shared.sdk.agent_planning.store import PlanningStore
from shared.sdk.agent_team.service import TeamService
from shared.sdk.agent_team.store import TeamStore
from shared.sdk.plan_delegation.service import PlanDelegationService
from shared.sdk.plan_delegation.store import PlanDelegationStore

from tests.plan_delegation_fixtures import CHAIN_PLAN

pytestmark = pytest.mark.asyncio

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
FORWARD = MIGRATIONS / "042_at_m3_5_plan_execution_graph.sql"
DOWN = MIGRATIONS / "042_at_m3_5_plan_execution_graph_down.sql"

M35_TABLES = (
    "goal_execution_lineage",
    "plan_execution_graphs",
    "plan_execution_units",
    "plan_execution_dispatches",
)

CANONICAL_MAIN = "c9f600185bade59a532d64bfe313b1c5c7890387"


def _ordered_migrations() -> list[Path]:
    return sorted(
        (
            p
            for p in MIGRATIONS.glob("*.sql")
            if p.name[:3].isdigit() and not p.name.endswith("_down.sql")
        ),
        key=lambda p: int(p.name[:3]),
    )


def _base_dsn() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://postgres@localhost:5432/aiagents")


def _with_database(dsn: str, database: str) -> str:
    parts = urlsplit(dsn)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


class _ThrowawayDatabase:
    """A database of its own, migrated from 001, dropped afterwards.

    Reversing a migration on the shared test database would destroy every other test's data and
    make the result depend on execution order. Each of these tests gets its own.
    """

    def __init__(self) -> None:
        self.name = f"m35_mig_{uuid.uuid4().hex[:12]}"
        self.dsn = _with_database(_base_dsn(), self.name)

    async def __aenter__(self) -> _ThrowawayDatabase:
        try:
            admin = await asyncpg.connect(dsn=_with_database(_base_dsn(), "postgres"), timeout=5)
        except Exception:
            pytest.skip("no reachable PostgreSQL; skipping AT-M3.5 migration lifecycle test")
        try:
            await admin.execute(f'CREATE DATABASE "{self.name}"')
        finally:
            await admin.close()
        conn = await asyncpg.connect(dsn=self.dsn, timeout=10)
        try:
            for path in _ordered_migrations():
                await conn.execute(path.read_text(encoding="utf-8"))
        finally:
            await conn.close()
        return self

    async def __aexit__(self, *exc: object) -> None:
        admin = await asyncpg.connect(dsn=_with_database(_base_dsn(), "postgres"), timeout=5)
        try:
            await admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=$1",
                self.name,
            )
            await admin.execute(f'DROP DATABASE IF EXISTS "{self.name}"')
        finally:
            await admin.close()

    async def connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.dsn, timeout=10)

    async def apply(self, path: Path) -> None:
        conn = await self.connect()
        try:
            await conn.execute(path.read_text(encoding="utf-8"))
        finally:
            await conn.close()

    async def tables_present(self) -> dict[str, bool]:
        conn = await self.connect()
        try:
            return {
                table: (await conn.fetchval(f"SELECT to_regclass('public.{table}')")) is not None
                for table in M35_TABLES
            }
        finally:
            await conn.close()


async def _materialized_scenario(db: _ThrowawayDatabase) -> dict[str, object]:
    """A real accepted plan, materialized and dispatched on this throwaway database."""
    planning = PlanningStore(db.dsn)
    team = TeamService(store=TeamStore(db.dsn))

    conn = await db.connect()
    try:
        project_id = str(
            await conn.fetchval(
                "INSERT INTO projects (title) VALUES ($1) RETURNING id",
                f"m35mig-{uuid.uuid4().hex[:8]}",
            )
        )
        author = str(
            await conn.fetchval(
                "INSERT INTO actor_principals (principal_type,display_name) "
                "VALUES ('human',$1) RETURNING principal_id",
                f"m35mig-{uuid.uuid4().hex[:6]}",
            )
        )
    finally:
        await conn.close()

    await team.form_team(
        project_id,
        goal_ref="m35mig",
        agent_keys=("design-review-agent", "development-agent", "qa-agent"),
    )
    goal = await planning.create_goal(
        {
            "project_id": project_id,
            "statement": "a plan whose identity must survive a refused downgrade",
            "created_by": author,
        }
    )
    revision = await planning.create_initial_revision(
        {"goal_id": str(goal["goal_id"]), "created_by": author, "plan": CHAIN_PLAN}
    )
    await planning.accept_revision(revision["plan_revision_id"])

    store = PlanDelegationStore(db.dsn)
    service = PlanDelegationService(store=store, team_store=TeamStore(db.dsn))
    result = await service.materialize_accepted_plan(
        goal_id=str(goal["goal_id"]),
        plan_revision_id=str(revision["plan_revision_id"]),
        materialized_by=author,
    )
    # No event bus: the canonical dispatch row still commits, which is what DOWN must protect.
    await service.schedule_ready_work(plan_revision_id=str(revision["plan_revision_id"]))
    return {
        "service": service,
        "store": store,
        "project_id": project_id,
        "author": author,
        "goal_id": str(goal["goal_id"]),
        "plan_revision_id": str(revision["plan_revision_id"]),
        "graph": result,
    }


async def _counts(db: _ThrowawayDatabase, plan_revision_id: str, goal_id: str) -> dict[str, int]:
    conn = await db.connect()
    try:
        return {
            "graphs": await conn.fetchval(
                "SELECT count(*) FROM plan_execution_graphs WHERE plan_revision_id=$1",
                uuid.UUID(plan_revision_id),
            ),
            "units": await conn.fetchval(
                "SELECT count(*) FROM plan_execution_units WHERE plan_revision_id=$1",
                uuid.UUID(plan_revision_id),
            ),
            "dispatches": await conn.fetchval(
                """
                SELECT count(*) FROM plan_execution_dispatches
                WHERE plan_revision_id=$1
                """,
                uuid.UUID(plan_revision_id),
            ),
            "lineage": await conn.fetchval(
                "SELECT count(*) FROM goal_execution_lineage WHERE goal_id=$1",
                uuid.UUID(goal_id),
            ),
            "child_work_items": await conn.fetchval(
                """
                SELECT count(*) FROM project_work_items
                WHERE parent_work_item_id = (
                    SELECT primary_work_item_id FROM goal_execution_lineage WHERE goal_id=$1)
                """,
                uuid.UUID(goal_id),
            ),
            "edges": await conn.fetchval(
                """
                SELECT count(*) FROM project_work_item_dependencies d
                WHERE d.work_item_id IN (
                    SELECT work_item_id FROM plan_execution_units WHERE plan_revision_id=$1)
                """,
                uuid.UUID(plan_revision_id),
            ),
        }
    finally:
        await conn.close()


# --- the empty case still reverses cleanly ---------------------------------------------------------


async def test_up_down_up_up_is_clean_while_nothing_has_been_materialized():
    async with _ThrowawayDatabase() as db:
        assert all((await db.tables_present()).values())

        await db.apply(DOWN)
        assert not any((await db.tables_present()).values())

        await db.apply(FORWARD)
        assert all((await db.tables_present()).values())

        await db.apply(FORWARD)  # re-runnable
        assert all((await db.tables_present()).values())


async def test_down_is_safe_to_run_twice_when_there_is_nothing_to_lose():
    async with _ThrowawayDatabase() as db:
        await db.apply(DOWN)
        await db.apply(DOWN)
        assert not any((await db.tables_present()).values())


# --- the evidence case fails closed -----------------------------------------------------------------


async def test_down_refuses_once_a_plan_has_been_materialized():
    async with _ThrowawayDatabase() as db:
        case = await _materialized_scenario(db)
        before = await _counts(db, case["plan_revision_id"], case["goal_id"])
        assert before["graphs"] == 1 and before["units"] == 3 and before["child_work_items"] == 3

        with pytest.raises(asyncpg.PostgresError) as exc:
            await db.apply(DOWN)
        message = str(exc.value)
        assert "refusing to reverse migration 042" in message
        assert "plan step" in message

        # The transaction rolled back: schema, mappings, dispatches and business work all survive.
        assert all((await db.tables_present()).values())
        assert await _counts(db, case["plan_revision_id"], case["goal_id"]) == before


async def test_a_refused_down_leaves_every_identity_mapping_intact():
    async with _ThrowawayDatabase() as db:
        case = await _materialized_scenario(db)
        with pytest.raises(asyncpg.PostgresError):
            await db.apply(DOWN)

        graph = await case["store"].get_graph(case["plan_revision_id"])
        assert graph is not None
        assert {u["step_key"] for u in graph["units"]} == {"design", "build", "verify"}
        assert len(graph["dependencies"]) == 2
        assert len(graph["dispatches"]) == 1
        assert await case["store"].get_execution_lineage(case["goal_id"]) is not None


async def test_rematerializing_after_a_refused_down_replays_and_creates_no_duplicate_work():
    """The Validation 1 defect, closed at its end as well as its start.

    Because DOWN refused, the graph is still there, so materializing the same PlanRevision is a
    canonical replay -- ``created=false``, the same graph, the same units, and NOT a second set of
    child work items.
    """
    async with _ThrowawayDatabase() as db:
        case = await _materialized_scenario(db)
        with pytest.raises(asyncpg.PostgresError):
            await db.apply(DOWN)

        before = await _counts(db, case["plan_revision_id"], case["goal_id"])
        again = await case["service"].materialize_accepted_plan(
            goal_id=case["goal_id"],
            plan_revision_id=case["plan_revision_id"],
            materialized_by=case["author"],
        )
        assert again["created"] is False
        assert str(again["graph"]["plan_execution_graph_id"]) == str(
            case["graph"]["graph"]["plan_execution_graph_id"]
        )

        after = await _counts(db, case["plan_revision_id"], case["goal_id"])
        assert after == before
        assert after["child_work_items"] == 3
        assert after["edges"] == 2


async def test_no_supported_sequence_reaches_an_empty_schema_with_orphaned_work_items():
    """The property the whole fix exists for, stated once.

    There is no longer any way to get from "this plan is materialized" to "the mapping tables are
    empty but the child work items remain". DOWN is the only path that dropped them, and DOWN now
    refuses.
    """
    async with _ThrowawayDatabase() as db:
        case = await _materialized_scenario(db)
        with pytest.raises(asyncpg.PostgresError):
            await db.apply(DOWN)

        conn = await db.connect()
        try:
            orphans = await conn.fetchval("""
                SELECT count(*) FROM project_work_items w
                WHERE w.parent_work_item_id IS NOT NULL
                  AND w.metadata->>'source' = 'at_m3_5_plan_delegation'
                  AND NOT EXISTS (
                      SELECT 1 FROM plan_execution_units u WHERE u.work_item_id = w.id)
                """)
        finally:
            await conn.close()
        assert orphans == 0
        assert case["plan_revision_id"]


# --- the canonical migrations are untouched ----------------------------------------------------------


def test_no_canonical_migration_001_through_041_was_changed_by_this_slice():
    try:
        changed = subprocess.run(
            ["git", "diff", "--name-only", CANONICAL_MAIN, "--", "migrations/"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - no git in this environment
        pytest.skip("git unavailable; cannot diff against canonical main")
    if changed.returncode != 0:
        pytest.skip("canonical main is not present in this checkout")

    touched = {line.strip() for line in changed.stdout.splitlines() if line.strip()}
    assert touched == {
        "migrations/042_at_m3_5_plan_execution_graph.sql",
        "migrations/042_at_m3_5_plan_execution_graph_down.sql",
    }, touched


def test_the_down_migration_refuses_before_it_drops_anything():
    """Order matters: the guard must run before the first DROP, or a partial reversal could commit
    on a database whose refusal fires late."""
    body = DOWN.read_text(encoding="utf-8")
    guard = body.index("RAISE EXCEPTION")
    first_drop = min(
        body.index(marker) for marker in ("DROP TRIGGER", "DROP TABLE", "DROP FUNCTION")
    )
    assert guard < first_drop
    assert re.search(r"USING ERRCODE = 'restrict_violation'", body)
    for table in M35_TABLES:
        assert f"FROM {table}" in body, table
