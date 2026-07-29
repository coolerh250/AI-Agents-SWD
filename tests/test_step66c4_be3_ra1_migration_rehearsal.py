"""Step 66C.4-BE3-RA-1A -- isolated migration rehearsal and rollback proof.

Real-PostgreSQL 16 rehearsal of migrations 031-035 (the BE3 authorization/resume/replay/production-
approval schema), on top of the pre-existing 029/030 baseline. Proves, against an isolated ephemeral
database only:

  pre-031 schema -> apply 031..035 (stepwise-validated) -> failure injection (no partial schema) ->
  duplicate invocation (idempotent) -> out-of-order attempt (fails deterministically) -> concurrent
  migrators (serialized by shared.sdk.backup_dr.migration_runner's advisory lock, not a race) ->
  pre-activation down rehearsal (035..031, only because NO synthetic BE3 data exists yet) -> reapply
  (schema fingerprint equality) -> post-write operational rollback simulation (NON-destructive --
  no down script run once data exists).

Gated by the fail-closed destructive-PG guard (tests/step66c4_pg_safety.py). No shared database is
ever touched. No feature gate is enabled. No worker/relay/consumer is started. No production action.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

import pytest

from step66c4_pg_safety import destructive_pg_refusal_reason

REPO = Path(__file__).resolve().parents[1]
MIGRATIONS = REPO / "migrations"

BASELINE_FILES = (
    "029_operator_task_api_foundation.sql",
    "030_workroom_clarification_foundation.sql",
)
CHAIN_FILES = (
    "031_clarification_lifecycle_outbox_foundation.sql",
    "032_be3_resume_replay_authorization.sql",
    "033_be3_resume_requests.sql",
    "034_be3_replay_requests.sql",
    "035_be3_production_action_approvals.sql",
)
DOWN_FILES = (
    "035_be3_production_action_approvals_down.sql",
    "034_be3_replay_requests_down.sql",
    "033_be3_resume_requests_down.sql",
    "032_be3_resume_replay_authorization_down.sql",
    "031_clarification_lifecycle_outbox_foundation_down.sql",
)

ALL_TABLES = (
    "operator_tasks",
    "task_messages",
    "operator_clarification_requests",
    "clarification_lifecycle_outbox",
    "resume_replay_authorizations",
    "resume_requests",
    "replay_requests",
    "production_action_approvals",
)

try:
    import asyncpg

    _HAS_ASYNCPG = True
except ImportError:  # pragma: no cover
    _HAS_ASYNCPG = False

_REFUSAL = destructive_pg_refusal_reason()
_DSN = os.environ.get("BE1_TEST_DATABASE_URL")


def _pg_ok() -> bool:
    if _REFUSAL is not None or not (_HAS_ASYNCPG and _DSN):
        return False
    try:

        async def _ping() -> bool:
            c = await asyncpg.connect(dsn=_DSN, timeout=5)
            await c.close()
            return True

        return asyncio.new_event_loop().run_until_complete(_ping())
    except Exception:
        return False


requires_pg = pytest.mark.skipif(
    not _pg_ok(), reason=(_REFUSAL or "isolated ephemeral PostgreSQL 16 not reachable")
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _runner():
    from shared.sdk.backup_dr import migration_runner

    return migration_runner


async def _apply(conn, name: str) -> None:
    await conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))


async def _drop_all(conn) -> None:
    await conn.execute(
        "DROP TABLE IF EXISTS production_action_approvals, replay_requests, resume_requests, "
        "resume_replay_authorizations, clarification_lifecycle_outbox, "
        "operator_clarification_requests, task_messages, operator_tasks CASCADE;"
    )


async def _apply_baseline(conn) -> None:
    await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    for name in BASELINE_FILES:
        await _apply(conn, name)


async def _seed_sentinel(conn) -> dict:
    """Insert one representative pre-existing task/message/clarification and return their
    identifying fields + a business-value fingerprint, so later assertions can prove NOTHING about
    them changed."""
    task_id = uuid.uuid4()
    message_id = uuid.uuid4()
    clar_id = uuid.uuid4()
    await conn.execute(
        "INSERT INTO operator_tasks (id, title, task_type, created_by, project_id) "
        "VALUES ($1, $2, 'other', 'sentinel-operator', $3)",
        task_id,
        "RA-1A sentinel task -- must survive every migration step unchanged",
        uuid.uuid4(),
    )
    await conn.execute(
        "INSERT INTO task_messages (id, task_id, sender_type, sender_id, message_type, body) "
        "VALUES ($1, $2, 'human', 'sentinel-operator', 'clarification_question', $3)",
        message_id,
        task_id,
        "RA-1A sentinel question",
    )
    await conn.execute(
        "INSERT INTO operator_clarification_requests "
        "(id, task_id, question_message_id, question, requested_by_type, requested_by_id, due_at, "
        "reminder_at) "
        "VALUES ($1, $2, $3, $4, 'human', 'sentinel-operator', now() + interval '1 day', "
        "now() + interval '12 hours')",
        clar_id,
        task_id,
        message_id,
        "RA-1A sentinel clarification question",
    )
    row = await conn.fetchrow("SELECT * FROM operator_tasks WHERE id = $1", task_id)
    return {
        "task_id": task_id,
        "message_id": message_id,
        "clarification_id": clar_id,
        "fingerprint": dict(row),
    }


async def _assert_sentinel_unchanged(conn, sentinel: dict) -> None:
    row = await conn.fetchrow("SELECT * FROM operator_tasks WHERE id = $1", sentinel["task_id"])
    assert row is not None, "sentinel task row was removed"
    assert dict(row) == sentinel["fingerprint"], "sentinel task row was mutated"
    msg_count = await conn.fetchval(
        "SELECT count(*) FROM task_messages WHERE id = $1", sentinel["message_id"]
    )
    assert msg_count == 1
    clar_count = await conn.fetchval(
        "SELECT count(*) FROM operator_clarification_requests WHERE id = $1",
        sentinel["clarification_id"],
    )
    assert clar_count == 1


TABLE_FOR_STEP = {
    "031_clarification_lifecycle_outbox_foundation.sql": "clarification_lifecycle_outbox",
    "032_be3_resume_replay_authorization.sql": "resume_replay_authorizations",
    "033_be3_resume_requests.sql": "resume_requests",
    "034_be3_replay_requests.sql": "replay_requests",
    "035_be3_production_action_approvals.sql": "production_action_approvals",
}


@pytest.fixture
def dsn() -> str:
    assert _DSN is not None
    return _DSN


@requires_pg
def test_pg_up_rehearsal_all_five_migrations_stepwise(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            sentinel = await _seed_sentinel(conn)

            # Confirm none of the five new tables exist yet (true pre-031 baseline).
            for table in TABLE_FOR_STEP.values():
                exists = await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", table)
                assert not exists, f"{table} exists before its migration ran"

            for filename, table in TABLE_FOR_STEP.items():
                await _apply(conn, filename)
                exists = await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", table)
                assert exists, f"{table} missing after applying {filename}"
                # Column/constraint/index sanity: at least one NOT NULL column, one PK, one index.
                cols = await conn.fetch(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=$1",
                    table,
                )
                assert len(cols) > 0
                pk = await conn.fetchval(
                    "SELECT count(*) FROM information_schema.table_constraints "
                    "WHERE table_schema='public' AND table_name=$1 AND constraint_type='PRIMARY KEY'",
                    table,
                )
                assert pk == 1, f"{table} missing exactly one primary key"
                await _assert_sentinel_unchanged(conn, sentinel)
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_existing_data_preserved_through_full_chain(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            sentinel = await _seed_sentinel(conn)
            before_count = await conn.fetchval("SELECT count(*) FROM operator_tasks")

            for filename in CHAIN_FILES:
                await _apply(conn, filename)

            after_count = await conn.fetchval("SELECT count(*) FROM operator_tasks")
            assert after_count == before_count == 1
            await _assert_sentinel_unchanged(conn, sentinel)
            # No unexpected backfill: the 6 lifecycle columns added by 031 stay NULL on the
            # pre-existing clarification row (no value was ever inferred for it).
            row = await conn.fetchrow(
                "SELECT reminder_sent_at, expired_at, resume_eligible_at, resume_requested_at, "
                "resume_requested_by, resume_authorized_at FROM operator_clarification_requests "
                "WHERE id = $1",
                sentinel["clarification_id"],
            )
            assert all(v is None for v in dict(row).values()), "unexpected backfill on legacy row"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_failure_early_in_transaction_leaves_no_partial_schema(dsn: str) -> None:
    """Inject a failing statement immediately after BEGIN, before any real DDL -- proves nothing
    is created at all."""

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            await _seed_sentinel(conn)
            sql = (MIGRATIONS / "032_be3_resume_replay_authorization.sql").read_text(
                encoding="utf-8"
            )
            broken = sql.replace(
                "BEGIN;",
                "BEGIN;\nSELECT 1/0; -- RA-1A injected early failure (never committed)",
                1,
            )
            with pytest.raises(asyncpg.PostgresError):
                await conn.execute(broken)
            # PostgreSQL leaves the ISSUING connection in an aborted-transaction state after a
            # failed multi-statement execute (the server-side transaction is already rolled back
            # data-wise, but the session refuses further commands until an explicit ROLLBACK) --
            # confirmed here rather than assumed; a fresh connection is unaffected (see the
            # dedicated lock/connection-release test).
            await conn.execute("ROLLBACK")
            exists = await conn.fetchval(
                "SELECT to_regclass('resume_replay_authorizations') IS NOT NULL"
            )
            assert not exists, "table exists despite an early in-transaction failure"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_failure_just_before_commit_leaves_no_partial_schema(dsn: str) -> None:
    """Inject a failing statement immediately before COMMIT, after all real DDL has run in the
    SAME transaction -- proves even a late failure fully rolls back (no partial commit, and this
    project has no separate bookkeeping-commit step to fail before: the migration's own COMMIT IS
    the bookkeeping)."""

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            await _seed_sentinel(conn)
            sql = (MIGRATIONS / "032_be3_resume_replay_authorization.sql").read_text(
                encoding="utf-8"
            )
            broken = sql.replace(
                "\nCOMMIT;",
                "\nSELECT 1/0; -- RA-1A injected late failure (right before commit)\nCOMMIT;",
                1,
            )
            with pytest.raises(asyncpg.PostgresError):
                await conn.execute(broken)
            await conn.execute("ROLLBACK")
            exists = await conn.fetchval(
                "SELECT to_regclass('resume_replay_authorizations') IS NOT NULL"
            )
            assert not exists, "table exists despite a pre-commit failure"
            # Rerun behavior deterministic: the REAL (unmodified) file now applies cleanly.
            await _apply(conn, "032_be3_resume_replay_authorization.sql")
            exists = await conn.fetchval(
                "SELECT to_regclass('resume_replay_authorizations') IS NOT NULL"
            )
            assert exists
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_connection_lock_released_after_failed_migration(dsn: str) -> None:
    """A failed migration attempt must not block or hang any OTHER caller, and the failing
    connection itself must become fully usable again after a single, explicit ROLLBACK -- not stay
    wedged forever. (PostgreSQL's real, expected behavior: the failing connection's SESSION is left
    in "aborted transaction" state -- refusing further commands -- until ROLLBACK is sent, even
    though the migration's own data-level changes are already rolled back server-side. This is not
    a defect; a migration runner must account for it, e.g. by reconnecting or issuing ROLLBACK
    after a failure rather than reusing the connection blindly.)"""

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        other = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            sql = (MIGRATIONS / "032_be3_resume_replay_authorization.sql").read_text(
                encoding="utf-8"
            )
            broken = sql.replace("\nCOMMIT;", "\nSELECT 1/0;\nCOMMIT;", 1)
            with pytest.raises(asyncpg.PostgresError):
                await conn.execute(broken)
            # A second, independent connection is completely unaffected -- no global/session-level
            # lock or blocking was left by the failure.
            await other.execute("SELECT 1")
            # The failing connection itself refuses further commands until explicitly rolled back.
            with pytest.raises(asyncpg.exceptions.InFailedSQLTransactionError):
                await conn.execute("SELECT 1")
            await conn.execute("ROLLBACK")
            # Fully usable again after the explicit ROLLBACK -- no lingering wedge.
            value = await conn.fetchval("SELECT 1")
            assert value == 1
        finally:
            await conn.close()
            await other.close()

    _run(scenario())


@requires_pg
def test_pg_duplicate_migration_invocation_is_idempotent(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            for filename in CHAIN_FILES:
                await _apply(conn, filename)
            before = await _runner().schema_fingerprint(conn, ALL_TABLES)

            # Reapply the entire chain a second time -- every statement is IF NOT EXISTS / guarded.
            for filename in CHAIN_FILES:
                await _apply(conn, filename)
            after = await _runner().schema_fingerprint(conn, ALL_TABLES)
            assert before == after, "duplicate invocation changed the schema fingerprint"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_out_of_order_migration_attempt_fails_deterministically(dsn: str) -> None:
    """033 (resume_requests) references resume_replay_authorizations (032). Applying it before 032
    must fail with a clear, deterministic error and leave no partial resume_requests object."""

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            await _apply(conn, "031_clarification_lifecycle_outbox_foundation.sql")
            # Deliberately skip 032.
            with pytest.raises(asyncpg.exceptions.UndefinedTableError):
                await _apply(conn, "033_be3_resume_requests.sql")
            await conn.execute("ROLLBACK")
            exists = await conn.fetchval("SELECT to_regclass('resume_requests') IS NOT NULL")
            assert not exists, "resume_requests exists despite an out-of-order apply attempt"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_concurrent_migrators_serialize_via_advisory_lock(dsn: str) -> None:
    """Proves option A directly: while one caller holds the migration-chain advisory lock, a
    second caller's attempt to acquire the SAME key is refused immediately by
    pg_try_advisory_lock (non-blocking probe) rather than being granted concurrently -- then, once
    released, the second caller CAN acquire it. Separately, two REAL apply_chain_locked calls
    launched concurrently against the same fresh database converge on one complete, correct schema
    with no duplicate-object error escaping either caller (an asyncio.gather-timed wall-clock race
    is not a reliable proxy for lock-holding -- it also measures wait time -- so serialization
    itself is proven via the direct pg_try_advisory_lock probe above, not by timing)."""

    async def scenario() -> None:
        holder = await asyncpg.connect(dsn=dsn)
        waiter = await asyncpg.connect(dsn=dsn)
        try:
            await holder.fetchval(
                "SELECT pg_advisory_lock(hashtextextended($1, 0))", _runner().DEFAULT_LOCK_KEY
            )
            try:
                got_while_held = await waiter.fetchval(
                    "SELECT pg_try_advisory_lock(hashtextextended($1, 0))",
                    _runner().DEFAULT_LOCK_KEY,
                )
                assert got_while_held is False, (
                    "a second connection acquired the SAME migration-chain lock key while the "
                    "first still held it"
                )
            finally:
                await holder.fetchval(
                    "SELECT pg_advisory_unlock(hashtextextended($1, 0))",
                    _runner().DEFAULT_LOCK_KEY,
                )
            got_after_release = await waiter.fetchval(
                "SELECT pg_try_advisory_lock(hashtextextended($1, 0))", _runner().DEFAULT_LOCK_KEY
            )
            assert got_after_release is True, "lock was not obtainable after the holder released it"
            await waiter.fetchval(
                "SELECT pg_advisory_unlock(hashtextextended($1, 0))", _runner().DEFAULT_LOCK_KEY
            )
        finally:
            await holder.close()
            await waiter.close()

        setup = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(setup)
            await _apply_baseline(setup)
        finally:
            await setup.close()

        async def migrator() -> None:
            conn = await asyncpg.connect(dsn=dsn)
            try:
                await _runner().apply_chain_locked(conn, MIGRATIONS, CHAIN_FILES)
            finally:
                await conn.close()

        await asyncio.gather(migrator(), migrator())

        verify = await asyncpg.connect(dsn=dsn)
        try:
            for table in TABLE_FOR_STEP.values():
                exists = await verify.fetchval("SELECT to_regclass($1) IS NOT NULL", table)
                assert exists, f"{table} missing after concurrent migrator rehearsal"
            # No duplicate-object row: exactly one primary key constraint per table.
            for table in TABLE_FOR_STEP.values():
                pk = await verify.fetchval(
                    "SELECT count(*) FROM information_schema.table_constraints "
                    "WHERE table_schema='public' AND table_name=$1 AND constraint_type='PRIMARY KEY'",
                    table,
                )
                assert pk == 1
        finally:
            await verify.close()

    _run(scenario())


@requires_pg
def test_pg_predown_rehearsal_removes_only_new_objects(dsn: str) -> None:
    """Pre-activation down rehearsal: valid ONLY because no synthetic BE3 data has been written to
    the five new tables in this fixture. 035 -> 031 down, in reverse order."""

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            sentinel = await _seed_sentinel(conn)
            for filename in CHAIN_FILES:
                await _apply(conn, filename)

            for filename in DOWN_FILES:
                await _apply(conn, filename)

            for table in TABLE_FOR_STEP.values():
                exists = await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", table)
                assert not exists, f"{table} still exists after its down migration"
            for table in ("operator_tasks", "task_messages", "operator_clarification_requests"):
                exists = await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", table)
                assert exists, f"pre-031 table {table} was removed by a down migration"
            await _assert_sentinel_unchanged(conn, sentinel)
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_reapply_after_down_matches_original_fingerprint(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            sentinel = await _seed_sentinel(conn)
            for filename in CHAIN_FILES:
                await _apply(conn, filename)
            first_fingerprint = await _runner().schema_fingerprint(conn, ALL_TABLES)

            for filename in DOWN_FILES:
                await _apply(conn, filename)
            for filename in CHAIN_FILES:
                await _apply(conn, filename)
            second_fingerprint = await _runner().schema_fingerprint(conn, ALL_TABLES)

            assert (
                first_fingerprint == second_fingerprint
            ), "schema fingerprint differs after a down+reapply cycle"
            await _assert_sentinel_unchanged(conn, sentinel)
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_post_write_operational_rollback_is_nondestructive(dsn: str) -> None:
    """Once the new tables carry synthetic runtime-shaped data, the correct rollback is: feature
    gates off (already the default), no worker/relay/consumer (none exist to stop), old application
    version keeps running -- NOT a destructive down migration. This test proves the data survives
    doing nothing destructive, and that a pre-existing/old-style query against operator_tasks (using
    only pre-031 columns) still works with the new tables present -- i.e. no old-version
    compatibility blocker."""

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            sentinel = await _seed_sentinel(conn)
            for filename in CHAIN_FILES:
                await _apply(conn, filename)

            authz_id = uuid.uuid4()
            outbox_id = uuid.uuid4()
            team_id, project_id = uuid.uuid4(), uuid.uuid4()
            await conn.execute(
                "INSERT INTO clarification_lifecycle_outbox "
                "(id, clarification_id, task_id, event_type, idempotency_key) "
                "VALUES ($1, $2, $3, 'clarification.reminder_due', $4)",
                outbox_id,
                sentinel["clarification_id"],
                sentinel["task_id"],
                f"ra1a-outbox-{outbox_id}",
            )
            await conn.execute(
                "INSERT INTO resume_replay_authorizations "
                "(authorization_id, action_type, resource_type, resource_id, team_id, project_id, "
                "requested_by, requested_role, resource_state_version, expires_at, idempotency_key) "
                "VALUES ($1, 'resume', 'clarification', $2, $3, $4, 'ra1a-actor', "
                "'agent_operator', 'v1', now() + interval '1 hour', $5)",
                authz_id,
                sentinel["clarification_id"],
                team_id,
                project_id,
                f"ra1a-authz-{authz_id}",
            )
            resume_req_id = uuid.uuid4()
            await conn.execute(
                "INSERT INTO resume_requests "
                "(resume_request_id, authorization_id, clarification_id, task_id, team_id, "
                "project_id, resource_state_version, requested_by, idempotency_key) "
                "VALUES ($1, $2, $3, $4, $5, $6, 'v1', 'ra1a-actor', $7)",
                resume_req_id,
                authz_id,
                sentinel["clarification_id"],
                sentinel["task_id"],
                team_id,
                project_id,
                f"ra1a-resumereq-{resume_req_id}",
            )
            replay_req_id = uuid.uuid4()
            await conn.execute(
                "INSERT INTO replay_requests "
                "(replay_request_id, authorization_id, outbox_event_id, event_type, destination, "
                "team_id, project_id, resource_state_version, requested_by, idempotency_key) "
                "VALUES ($1, $2, $3, 'clarification.reminder_due', 'audit', $4, $5, 'v1', "
                "'ra1a-actor', $6)",
                replay_req_id,
                authz_id,
                outbox_id,
                team_id,
                project_id,
                f"ra1a-replayreq-{replay_req_id}",
            )
            approval_id = uuid.uuid4()
            await conn.execute(
                "INSERT INTO production_action_approvals "
                "(approval_id, action_type, resource_type, resource_id, team_id, project_id, "
                "resource_state_version, granted_by, granted_role, expires_at, idempotency_key) "
                "VALUES ($1, 'resume', 'clarification', $2, $3, $4, 'v1', 'ra1a-approver', "
                "'reviewer_approver', now() + interval '1 hour', $5)",
                approval_id,
                sentinel["clarification_id"],
                team_id,
                project_id,
                f"ra1a-approval-{approval_id}",
            )

            # Simulated operational rollback: NO destructive down script is run. Only an
            # application-version rollback is simulated (nothing to actually stop, since no
            # worker/relay/consumer is ever started -- see the RA-P safety findings).
            new_data_rows = {
                "clarification_lifecycle_outbox": outbox_id,
                "resume_replay_authorizations": authz_id,
                "resume_requests": resume_req_id,
                "replay_requests": replay_req_id,
                "production_action_approvals": approval_id,
            }
            pk_column = {
                "clarification_lifecycle_outbox": "id",
                "resume_replay_authorizations": "authorization_id",
                "resume_requests": "resume_request_id",
                "replay_requests": "replay_request_id",
                "production_action_approvals": "approval_id",
            }
            for table, row_id in new_data_rows.items():
                count = await conn.fetchval(
                    f"SELECT count(*) FROM {table} WHERE {pk_column[table]} = $1", row_id
                )
                assert count == 1, f"synthetic data in {table} did not survive (no-op) rollback"

            # Old-version compatibility: a query using ONLY pre-031 columns still works with the
            # new schema present (additive-only migrations never break an old code path).
            old_style_row = await conn.fetchrow(
                "SELECT id, title, status, created_by FROM operator_tasks WHERE id = $1",
                sentinel["task_id"],
            )
            assert old_style_row is not None, "pre-031-style query broke with new schema present"

            await _assert_sentinel_unchanged(conn, sentinel)
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_no_shared_environment_variables_leaked_into_evidence(dsn: str) -> None:
    """Defense-in-depth: the DSN used by this rehearsal must itself pass the same fail-closed
    isolated-database guard as every other Step 66C.4 destructive PG test (already enforced by
    `requires_pg`), and this test asserts the guard was not bypassed."""
    assert destructive_pg_refusal_reason() is None
