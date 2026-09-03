"""Step AT-M3.6B.1 -- migration 044 against a real PostgreSQL, forwards and backwards.

044 widens two CHECK constraints and does nothing else, so most of what needs proving is what it
does NOT do: no table, no column, no index, no trigger, no function, no data change, and no
weakening of the invariants migrations 037 and 040 established. The interesting half is the reverse
migration, which must REFUSE rather than succeed once live evidence exists -- the two ways to make
it succeed anyway are to delete those rows or relabel them, and both destroy the record of provider
calls that really happened.

Each test runs on its own throwaway database, migrated from 001, because reversing a migration on a
shared database would destroy every other test's data and make the result depend on ordering.
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
FORWARD = MIGRATIONS / "044_at_m3_6b_1_live_reasoning_provider.sql"
DOWN = MIGRATIONS / "044_at_m3_6b_1_live_reasoning_provider_down.sql"

#: The exact `main` this slice branched from. 043 is its last migration, so this one is 044 --
#: derived from repository truth, not assumed.
CANONICAL_MAIN = "e50d42294119db4c561ea07ebe42a9382b8e3f68"

_NEW_CATEGORIES = ("provider_timeout", "rate_limited", "budget_exceeded")
_ORIGINAL_CATEGORIES = (
    "provider_disabled",
    "provider_unauthorized",
    "malformed_output",
    "content_safety_rejected",
    "provider_unavailable",
)

pytestmark = pytest.mark.asyncio


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
        self.name = f"m36b1_mig_{uuid.uuid4().hex[:12]}"
        self.dsn = _with_database(_base_dsn(), self.name)

    async def __aenter__(self) -> "_ThrowawayDatabase":
        try:
            admin = await asyncpg.connect(dsn=_base_dsn(), timeout=5)
        except Exception:
            pytest.skip("no reachable PostgreSQL; skipping migration 044 test")
        try:
            await admin.execute(f'CREATE DATABASE "{self.name}"')
        finally:
            await admin.close()
        return self

    async def __aexit__(self, *_: object) -> None:
        admin = await asyncpg.connect(dsn=_base_dsn(), timeout=5)
        try:
            await admin.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=$1",
                self.name,
            )
            await admin.execute(f'DROP DATABASE IF EXISTS "{self.name}"')
        finally:
            await admin.close()

    async def apply_through(self, last: int) -> None:
        conn = await asyncpg.connect(dsn=self.dsn, timeout=10)
        try:
            await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
            for path in _ordered_migrations():
                if int(path.name[:3]) > last:
                    continue
                await conn.execute(path.read_text(encoding="utf-8"))
        finally:
            await conn.close()

    async def run(self, path: Path) -> None:
        conn = await asyncpg.connect(dsn=self.dsn, timeout=10)
        try:
            await conn.execute(path.read_text(encoding="utf-8"))
        finally:
            await conn.close()

    async def connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.dsn, timeout=10)


async def _check_clause(conn: asyncpg.Connection, name: str) -> str:
    return await conn.fetchval(
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname=$1", name
    )


async def _schema_fingerprint(conn: asyncpg.Connection) -> dict[str, object]:
    """Everything 044 must NOT change."""
    return {
        "tables": [
            r["table_name"]
            for r in await conn.fetch(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' ORDER BY table_name"
            )
        ],
        "columns": [
            f"{r['table_name']}.{r['column_name']}:{r['data_type']}"
            for r in await conn.fetch(
                "SELECT table_name, column_name, data_type FROM information_schema.columns "
                "WHERE table_schema='public' ORDER BY table_name, column_name"
            )
        ],
        "indexes": [
            r["indexname"]
            for r in await conn.fetch(
                "SELECT indexname FROM pg_indexes WHERE schemaname='public' ORDER BY indexname"
            )
        ],
        "triggers": [
            r["tgname"]
            for r in await conn.fetch(
                "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal ORDER BY tgname"
            )
        ],
        "functions": [
            r["proname"]
            for r in await conn.fetch(
                "SELECT proname FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                "WHERE n.nspname='public' ORDER BY proname"
            )
        ],
    }


async def _seed_invocation(conn: asyncpg.Connection, **overrides: object) -> str:
    project = await conn.fetchval(
        "INSERT INTO projects (title, summary) VALUES ($1,$2) RETURNING id",
        f"at-m3-6b-1-mig-{uuid.uuid4().hex[:8]}",
        "AT-M3.6B.1 migration test project",
    )
    fields: dict[str, object] = {
        "project_id": project,
        "reasoning_verb": "propose",
        "requested_provider_name": "anthropic",
        "provider_mode": "live",
        "model_name": "claude-sonnet-5",
        "status": "started",
        "attempt_token": uuid.uuid4(),
    }
    fields.update(overrides)
    return await conn.fetchval(
        """
        INSERT INTO reasoning_invocations
            (project_id, reasoning_verb, requested_provider_name, provider_mode, model_name,
             status, attempt_token, lease_expires_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7, now() + interval '120 seconds')
        RETURNING invocation_id
        """,
        fields["project_id"],
        fields["reasoning_verb"],
        fields["requested_provider_name"],
        fields["provider_mode"],
        fields["model_name"],
        fields["status"],
        fields["attempt_token"],
    )


class TestMigrationNumberIsDerived:
    async def test_044_is_the_next_number_after_canonical_main(self) -> None:
        numbers = [int(p.name[:3]) for p in _ordered_migrations()]
        assert max(numbers) == 44
        assert numbers.count(44) == 1
        assert FORWARD.exists() and DOWN.exists()


class TestForward:
    async def test_live_mode_becomes_representable(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(43)
            conn = await db.connect()
            try:
                with pytest.raises(asyncpg.CheckViolationError):
                    await _seed_invocation(conn)
            finally:
                await conn.close()

            await db.run(FORWARD)
            conn = await db.connect()
            try:
                invocation = await _seed_invocation(conn)
                assert invocation is not None
                mode = await conn.fetchval(
                    "SELECT provider_mode FROM reasoning_invocations WHERE invocation_id=$1",
                    invocation,
                )
                assert mode == "live"
            finally:
                await conn.close()

    async def test_the_two_original_modes_are_unchanged(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(44)
            conn = await db.connect()
            try:
                for mode in ("mock", "disabled"):
                    assert await _seed_invocation(conn, provider_mode=mode) is not None
                with pytest.raises(asyncpg.CheckViolationError):
                    await _seed_invocation(conn, provider_mode="anthropic_live")
            finally:
                await conn.close()

    async def test_the_three_new_failure_categories_are_admitted(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(44)
            conn = await db.connect()
            try:
                for category in _NEW_CATEGORIES + _ORIGINAL_CATEGORIES:
                    invocation = await _seed_invocation(conn)
                    await conn.execute(
                        "UPDATE reasoning_invocations SET status='failed', failure_category=$2, "
                        "failure_reason='test', completed_at=now(), lease_expires_at=NULL "
                        "WHERE invocation_id=$1",
                        invocation,
                        category,
                    )
            finally:
                await conn.close()

    async def test_an_invented_failure_category_is_still_refused(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(44)
            conn = await db.connect()
            try:
                invocation = await _seed_invocation(conn)
                with pytest.raises(asyncpg.CheckViolationError):
                    await conn.execute(
                        "UPDATE reasoning_invocations SET status='failed', "
                        "failure_category='anthropic_overloaded_error', completed_at=now(), "
                        "lease_expires_at=NULL WHERE invocation_id=$1",
                        invocation,
                    )
            finally:
                await conn.close()

    async def test_nothing_else_in_the_schema_moves(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(43)
            conn = await db.connect()
            try:
                before = await _schema_fingerprint(conn)
            finally:
                await conn.close()

            await db.run(FORWARD)
            conn = await db.connect()
            try:
                after = await _schema_fingerprint(conn)
            finally:
                await conn.close()
            assert before == after

    async def test_the_migration_is_re_runnable(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(44)
            await db.run(FORWARD)
            conn = await db.connect()
            try:
                assert await _seed_invocation(conn) is not None
            finally:
                await conn.close()


class TestMigration040InvariantsSurvive:
    """A live invocation is not a privileged invocation."""

    async def test_a_succeeded_live_row_still_needs_its_artifact(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(44)
            conn = await db.connect()
            try:
                invocation = await _seed_invocation(conn)
                with pytest.raises(asyncpg.CheckViolationError):
                    await conn.execute(
                        "UPDATE reasoning_invocations SET status='succeeded', completed_at=now(), "
                        "lease_expires_at=NULL WHERE invocation_id=$1",
                        invocation,
                    )
            finally:
                await conn.close()

    async def test_a_terminal_live_row_is_still_frozen(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(44)
            conn = await db.connect()
            try:
                invocation = await _seed_invocation(conn)
                await conn.execute(
                    "UPDATE reasoning_invocations SET status='succeeded', "
                    "artifact_type='ProposalArtifact', artifact='{\"summary\":\"s\"}'::jsonb, "
                    "completed_at=now(), lease_expires_at=NULL WHERE invocation_id=$1",
                    invocation,
                )
                with pytest.raises(asyncpg.PostgresError):
                    await conn.execute(
                        'UPDATE reasoning_invocations SET artifact=\'{"summary":"other"}\'::jsonb '
                        "WHERE invocation_id=$1",
                        invocation,
                    )
            finally:
                await conn.close()

    async def test_provider_identity_is_still_immutable(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(44)
            conn = await db.connect()
            try:
                invocation = await _seed_invocation(conn)
                with pytest.raises(asyncpg.PostgresError):
                    await conn.execute(
                        "UPDATE reasoning_invocations SET model_name='claude-3-opus' "
                        "WHERE invocation_id=$1",
                        invocation,
                    )
            finally:
                await conn.close()


class TestReverse:
    async def test_down_reverses_cleanly_when_no_live_evidence_exists(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(44)
            conn = await db.connect()
            try:
                widened = await _check_clause(conn, "chk_reasoning_invocations_provider_mode")
                assert "live" in widened
            finally:
                await conn.close()

            await db.run(DOWN)
            conn = await db.connect()
            try:
                narrowed = await _check_clause(conn, "chk_reasoning_invocations_provider_mode")
                assert "live" not in narrowed
                categories = await _check_clause(conn, "chk_reasoning_invocations_failure_category")
                for category in _NEW_CATEGORIES:
                    assert category not in categories
                with pytest.raises(asyncpg.CheckViolationError):
                    await _seed_invocation(conn)
            finally:
                await conn.close()

    async def test_up_down_up_up_leaves_the_widened_vocabulary(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(44)
            await db.run(DOWN)
            await db.run(FORWARD)
            await db.run(FORWARD)
            conn = await db.connect()
            try:
                assert await _seed_invocation(conn) is not None
                clause = await _check_clause(conn, "chk_reasoning_invocations_provider_mode")
                assert "live" in clause
            finally:
                await conn.close()

    async def test_down_refuses_rather_than_destroying_live_evidence(self) -> None:
        """The load-bearing half of the reverse migration.

        A reasoning invocation is evidence -- migration 040 exists precisely to stop it being
        edited -- and a schema rollback is not a licence to edit it.
        """
        async with _ThrowawayDatabase() as db:
            await db.apply_through(44)
            conn = await db.connect()
            try:
                await _seed_invocation(conn)
            finally:
                await conn.close()

            with pytest.raises(asyncpg.PostgresError) as caught:
                await db.run(DOWN)
            assert "refused" in str(caught.value).lower()

            conn = await db.connect()
            try:
                # The row is still there, unmodified, and the schema still admits it.
                remaining = await conn.fetchval(
                    "SELECT count(*) FROM reasoning_invocations WHERE provider_mode='live'"
                )
                assert remaining == 1
                clause = await _check_clause(conn, "chk_reasoning_invocations_provider_mode")
                assert "live" in clause
            finally:
                await conn.close()

    async def test_down_refuses_when_a_new_failure_category_is_recorded(self) -> None:
        async with _ThrowawayDatabase() as db:
            await db.apply_through(44)
            conn = await db.connect()
            try:
                invocation = await _seed_invocation(conn, provider_mode="mock", model_name=None)
                await conn.execute(
                    "UPDATE reasoning_invocations SET status='failed', "
                    "failure_category='rate_limited', failure_reason='x', completed_at=now(), "
                    "lease_expires_at=NULL WHERE invocation_id=$1",
                    invocation,
                )
            finally:
                await conn.close()

            with pytest.raises(asyncpg.PostgresError):
                await db.run(DOWN)


class TestCanonicalMigrationsUnchanged:
    async def test_001_through_043_are_byte_identical_to_canonical_main(self) -> None:
        import subprocess

        changed = subprocess.run(
            ["git", "diff", "--name-only", f"{CANONICAL_MAIN}", "--", "migrations/"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if changed.returncode != 0:
            pytest.skip("git unavailable; skipping canonical-migration comparison")
        touched = {line.strip() for line in changed.stdout.splitlines() if line.strip()}
        assert touched == {
            "migrations/044_at_m3_6b_1_live_reasoning_provider.sql",
            "migrations/044_at_m3_6b_1_live_reasoning_provider_down.sql",
        }, touched
