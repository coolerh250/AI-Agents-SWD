"""Step AT-M3.6A -- migration 043 against a real PostgreSQL, forwards and backwards.

043 adds one index and nothing else, so what needs proving is mostly what it does NOT do: it must
not create a table, a column, a constraint, a trigger or a view, it must reverse completely, and
the timeline it exists to speed up must return the same rows whether the index is there or not.

That last one is the point of an index-only migration and the easiest thing to get wrong. An index
is an optimisation; the moment a read gives a DIFFERENT answer with it than without it, the read
was depending on the index for correctness, and the index has quietly become schema.

Each test runs on its own throwaway database, migrated from 001, because reversing a migration on
the shared test database would destroy every other test's data and make the result depend on
execution order.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
FORWARD = MIGRATIONS / "043_at_m3_6a_audit_timeline_index.sql"
DOWN = MIGRATIONS / "043_at_m3_6a_audit_timeline_index_down.sql"
INDEX = "idx_audit_logs_artifact_refs_gin"

#: The exact `main` this slice branched from. 042 is its last migration, so this one is 043 --
#: derived, not assumed.
CANONICAL_MAIN = "f3a85afb465791457444b93b850014e1faf5d4f3"


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
    def __init__(self) -> None:
        self.name = f"m36a_mig_{uuid.uuid4().hex[:12]}"
        self.dsn = _with_database(_base_dsn(), self.name)

    async def __aenter__(self) -> _ThrowawayDatabase:
        try:
            admin = await asyncpg.connect(dsn=_with_database(_base_dsn(), "postgres"), timeout=5)
        except Exception:
            pytest.skip("no reachable PostgreSQL; skipping AT-M3.6A migration test")
        try:
            await admin.execute(f'CREATE DATABASE "{self.name}"')
        finally:
            await admin.close()
        conn = await asyncpg.connect(dsn=self.dsn, timeout=20)
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
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1",
                self.name,
            )
            await admin.execute(f'DROP DATABASE IF EXISTS "{self.name}"')
        finally:
            await admin.close()

    async def connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.dsn, timeout=10)


async def _schema_fingerprint(conn: asyncpg.Connection) -> dict[str, list]:
    """Everything 043 must leave untouched: tables, columns, constraints, triggers, views."""
    return {
        "columns": [
            tuple(r)
            for r in await conn.fetch(
                "SELECT table_name, column_name, data_type, is_nullable, column_default "
                "FROM information_schema.columns WHERE table_schema='public' "
                "ORDER BY table_name, column_name"
            )
        ],
        "constraints": [
            tuple(r)
            for r in await conn.fetch(
                "SELECT conrelid::regclass::text, conname, pg_get_constraintdef(oid) "
                "FROM pg_constraint ORDER BY 1, 2"
            )
        ],
        "triggers": [
            tuple(r)
            for r in await conn.fetch(
                "SELECT tgrelid::regclass::text, tgname FROM pg_trigger "
                "WHERE NOT tgisinternal ORDER BY 1, 2"
            )
        ],
        "views": [
            tuple(r)
            for r in await conn.fetch(
                "SELECT table_name FROM information_schema.views "
                "WHERE table_schema='public' ORDER BY 1"
            )
        ],
        "matviews": [
            tuple(r)
            for r in await conn.fetch(
                "SELECT matviewname FROM pg_matviews WHERE schemaname='public' ORDER BY 1"
            )
        ],
    }


def test_the_migration_number_is_derived_from_canonical_main():
    """042 is the last migration on the exact commit this branched from, so this one is 043.

    ``assert max(numbers) == 43`` is what this used to say, and it is the same shape of assertion
    AT-D23 section 7 recorded a GOVERNANCE_DRIFT_ALERT about: a stage claiming that its own
    migration is the last one that will ever exist forbids every later authorized milestone by
    construction, and AT-M3.6A itself had to repair the identical assertion in the AT-M3.5 suite for
    exactly this reason. AT-M3.6B.1 adds 044 under AT-D24 and trips it a second time.

    What this test is FOR is that AT-M3.6A picked its number from repository truth rather than
    assuming one, and that it picked exactly one. Both are still checked; "nothing may follow me"
    was never the property, and it is removed rather than repaired again.
    """
    numbers = [int(p.name[:3]) for p in _ordered_migrations()]
    assert 43 in numbers
    assert numbers.count(43) == 1, "one 043, not two files racing for the number"
    assert max(n for n in numbers if n < 43) == 42, "043 follows 042, the canonical-main tip"
    assert FORWARD.exists() and DOWN.exists()
    assert CANONICAL_MAIN in FORWARD.read_text(encoding="utf-8") or "042" in FORWARD.read_text(
        encoding="utf-8"
    )


def test_the_forward_migration_creates_an_index_and_nothing_else():
    """Read as text, so a table smuggled in beside the index fails before it ever runs."""
    sql = FORWARD.read_text(encoding="utf-8")
    statements = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    ).upper()
    assert "CREATE INDEX IF NOT EXISTS" in statements
    for forbidden in (
        "CREATE TABLE",
        "ALTER TABLE",
        "CREATE TRIGGER",
        "CREATE FUNCTION",
        "CREATE OR REPLACE FUNCTION",
        "CREATE VIEW",
        "MATERIALIZED VIEW",
        "CREATE TYPE",
        "INSERT INTO",
        "UPDATE ",
        "DELETE FROM",
        "DROP TABLE",
    ):
        assert forbidden not in statements, forbidden
    assert statements.count("CREATE INDEX") == 1, "one index, and only one"


@pytest.mark.asyncio
async def test_up_down_up_up_is_clean_and_changes_no_schema_object():
    """UP / DOWN / UP / UP, with the whole schema fingerprinted around it."""
    async with _ThrowawayDatabase() as db:
        conn = await db.connect()
        try:
            # The chain already applied 043 once. Capture the schema and the index.
            baseline = await _schema_fingerprint(conn)
            assert await conn.fetchval("SELECT to_regclass($1)", f"public.{INDEX}") is not None

            await conn.execute(DOWN.read_text(encoding="utf-8"))
            assert await conn.fetchval("SELECT to_regclass($1)", f"public.{INDEX}") is None
            # DOWN removed the index and nothing else.
            after_down = await _schema_fingerprint(conn)
            assert after_down == baseline

            await conn.execute(FORWARD.read_text(encoding="utf-8"))
            assert await conn.fetchval("SELECT to_regclass($1)", f"public.{INDEX}") is not None
            # Re-runnable: a second UP is a no-op, not a duplicate-object error.
            await conn.execute(FORWARD.read_text(encoding="utf-8"))
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM pg_indexes WHERE indexname=$1", INDEX
                )
                == 1
            )
            assert await _schema_fingerprint(conn) == baseline

            # DOWN is re-runnable too.
            await conn.execute(DOWN.read_text(encoding="utf-8"))
            await conn.execute(DOWN.read_text(encoding="utf-8"))
            assert await conn.fetchval("SELECT to_regclass($1)", f"public.{INDEX}") is None
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_the_index_is_on_audit_logs_and_touches_no_other_table():
    async with _ThrowawayDatabase() as db:
        conn = await db.connect()
        try:
            row = await conn.fetchrow(
                "SELECT tablename, indexdef FROM pg_indexes WHERE indexname=$1", INDEX
            )
            assert row["tablename"] == "audit_logs"
            assert "USING gin" in row["indexdef"]
            assert "jsonb_path_ops" in row["indexdef"]
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_the_timeline_returns_identical_rows_with_and_without_the_index():
    """The load-bearing property of an index-only migration: it changes speed, never answers.

    If the two result sets ever differed, the read would be depending on the index for
    CORRECTNESS, and the index would have stopped being an optimisation.
    """
    async with _ThrowawayDatabase() as db:
        conn = await db.connect()
        try:
            goal = str(uuid.uuid4())
            revision = str(uuid.uuid4())
            for i in range(40):
                refs = (
                    {"goal_id": goal} if i % 4 == 0
                    else {"plan_revision_id": revision} if i % 4 == 1
                    else {"goal_id": str(uuid.uuid4())}
                )
                await conn.execute(
                    "INSERT INTO audit_logs (agent, decision_type, summary, result, artifact_refs) "
                    "VALUES ($1,$2,$3,$4,$5::jsonb)",
                    "m36a-fixture",
                    f"event_{i}",
                    "summary",
                    "ok",
                    __import__("json").dumps(refs),
                )
            probes = [
                __import__("json").dumps({"goal_id": goal}),
                __import__("json").dumps({"plan_revision_id": revision}),
            ]
            query = (
                "SELECT id, decision_type FROM audit_logs "
                "WHERE artifact_refs @> ANY ($1::jsonb[]) "
                "ORDER BY created_at ASC, id ASC LIMIT 100"
            )

            with_index = [tuple(r) for r in await conn.fetch(query, probes)]
            assert len(with_index) == 20

            await conn.execute(DOWN.read_text(encoding="utf-8"))
            without_index = [tuple(r) for r in await conn.fetch(query, probes)]

            assert without_index == with_index

            await conn.execute(FORWARD.read_text(encoding="utf-8"))
            assert [tuple(r) for r in await conn.fetch(query, probes)] == with_index
        finally:
            await conn.close()
