"""Step 66C.4-BE3-RA-1R -- INDEPENDENT reviewer test battery.

Written by the independent reviewer (NOT the RA-1A implementation session) to re-derive every RA-1A
claim from scratch against an isolated ephemeral PostgreSQL 16, and to probe the migration-runner
paths the RA-1A suite does not exercise -- in particular the ``apply_chain_locked`` FAILURE path
(its ``finally`` unlock behavior when a migration leaves the connection in aborted-transaction
state) and the ``schema_fingerprint`` blind spots.

These tests assert the ACTUAL observed behavior (including behavior the review flags as a defect for
FUTURE shared-apply readiness), so the suite is a faithful, reproducible characterization: it passes
against the code under review while the review artifacts interpret the characterized behavior. It
modifies NO file under review (migration_runner.py, migrations/*, the RA-1A test suite).

Gated by the SAME fail-closed destructive-PG guard as every other Step 66C.4 PG test. No shared
database, no feature gate, no worker/relay/consumer, no production action.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
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
NEW_TABLES = (
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


LOCK_KEY_SQL_LOCK = "SELECT pg_advisory_lock(hashtextextended($1,0))"
LOCK_KEY_SQL_UNLOCK = "SELECT pg_advisory_unlock(hashtextextended($1,0))"
LOCK_KEY_SQL_TRY = "SELECT pg_try_advisory_lock(hashtextextended($1,0))"


async def _connect():
    return await asyncpg.connect(dsn=_DSN)


async def _drop_all(conn) -> None:
    await conn.execute(
        "DROP TABLE IF EXISTS production_action_approvals, replay_requests, resume_requests, "
        "resume_replay_authorizations, clarification_lifecycle_outbox, "
        "operator_clarification_requests, task_messages, operator_tasks CASCADE;"
    )


async def _apply(conn, name: str) -> None:
    await conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))


async def _apply_baseline(conn) -> None:
    await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    for name in BASELINE_FILES:
        await _apply(conn, name)


async def _seed_sentinel(conn) -> dict:
    task_id, message_id, clar_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await conn.execute(
        "INSERT INTO operator_tasks (id, title, task_type, created_by, project_id) "
        "VALUES ($1, $2, 'other', 'rev-operator', $3)",
        task_id,
        "RA-1R independent sentinel task",
        uuid.uuid4(),
    )
    await conn.execute(
        "INSERT INTO task_messages (id, task_id, sender_type, sender_id, message_type, body) "
        "VALUES ($1, $2, 'human', 'rev-operator', 'clarification_question', $3)",
        message_id,
        task_id,
        "RA-1R sentinel question",
    )
    await conn.execute(
        "INSERT INTO operator_clarification_requests "
        "(id, task_id, question_message_id, question, requested_by_type, requested_by_id, due_at, "
        "reminder_at) VALUES ($1, $2, $3, $4, 'human', 'rev-operator', now() + interval '1 day', "
        "now() + interval '12 hours')",
        clar_id,
        task_id,
        message_id,
        "RA-1R sentinel clarification",
    )
    task_row = await conn.fetchrow("SELECT * FROM operator_tasks WHERE id=$1", task_id)
    task_ctid = await conn.fetchval("SELECT ctid::text FROM operator_tasks WHERE id=$1", task_id)
    clar_row = await conn.fetchrow(
        "SELECT * FROM operator_clarification_requests WHERE id=$1", clar_id
    )
    return {
        "task_id": task_id,
        "message_id": message_id,
        "clarification_id": clar_id,
        "task_fp": dict(task_row),
        "task_ctid": task_ctid,
        "clar_fp": dict(clar_row),
    }


async def _assert_sentinel_unchanged(conn, s: dict, *, check_ctid: bool = True) -> None:
    task_row = await conn.fetchrow("SELECT * FROM operator_tasks WHERE id=$1", s["task_id"])
    assert task_row is not None, "sentinel task disappeared"
    assert dict(task_row) == s["task_fp"], "sentinel task columns changed"
    if check_ctid:
        ctid = await conn.fetchval(
            "SELECT ctid::text FROM operator_tasks WHERE id=$1", s["task_id"]
        )
        assert ctid == s["task_ctid"], "sentinel task physical row was rewritten (ctid changed)"
    # clarification: pre-031 columns unchanged; the 6 new lifecycle columns must be NULL after 031.
    clar_row = await conn.fetchrow(
        "SELECT * FROM operator_clarification_requests WHERE id=$1", s["clarification_id"]
    )
    assert clar_row is not None
    for k, v in s["clar_fp"].items():
        assert dict(clar_row)[k] == v, f"sentinel clarification column {k} changed"
    for col in (
        "reminder_sent_at",
        "expired_at",
        "resume_eligible_at",
        "resume_requested_at",
        "resume_requested_by",
        "resume_authorized_at",
    ):
        if col in dict(clar_row):
            assert dict(clar_row)[col] is None, f"unexpected backfill of {col} on legacy row"


@pytest.fixture
def dsn() -> str:
    assert _DSN is not None
    return _DSN


# ---------------------------------------------------------------------------
# 1. Full 029-035 rehearsal, stepwise, sentinel preserved every step.
# ---------------------------------------------------------------------------
@requires_pg
def test_rev_full_chain_stepwise_and_data_preserved(dsn: str) -> None:
    async def scenario() -> None:
        conn = await _connect()
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            s = await _seed_sentinel(conn)
            for name in NEW_TABLES:
                exists = await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", name)
                assert not exists
            for f in CHAIN_FILES:
                await _apply(conn, f)
                await _assert_sentinel_unchanged(conn, s)
            for name in ALL_TABLES:
                exists = await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", name)
                assert exists, f"{name} missing after full chain"
                pk = await conn.fetchval(
                    "SELECT count(*) FROM information_schema.table_constraints "
                    "WHERE table_schema='public' AND table_name=$1 AND constraint_type='PRIMARY KEY'",
                    name,
                )
                assert pk == 1, f"{name} does not have exactly one primary key"
            assert await conn.fetchval("SELECT count(*) FROM operator_tasks") == 1
        finally:
            await conn.close()

    _run(scenario())


# ---------------------------------------------------------------------------
# 2. apply_chain_locked SUCCESS path releases the lock via finally.
# ---------------------------------------------------------------------------
@requires_pg
def test_rev_apply_chain_locked_success_releases_lock(dsn: str) -> None:
    async def scenario() -> None:
        setup = await _connect()
        try:
            await _drop_all(setup)
            await _apply_baseline(setup)
        finally:
            await setup.close()
        conn = await _connect()
        try:
            await _runner().apply_chain_locked(conn, MIGRATIONS, CHAIN_FILES)
            # Lock is free now: another connection can grab it while conn is still open.
            probe = await _connect()
            try:
                got = await probe.fetchval(LOCK_KEY_SQL_TRY, _runner().DEFAULT_LOCK_KEY)
                assert got is True, "success path did not release the advisory lock"
                await probe.fetchval(LOCK_KEY_SQL_UNLOCK, _runner().DEFAULT_LOCK_KEY)
            finally:
                await probe.close()
            for name in NEW_TABLES:
                assert await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", name)
        finally:
            await conn.close()

    _run(scenario())


# ---------------------------------------------------------------------------
# 3. apply_chain_locked FAILURE path -- characterizes the runner's cleanup defect.
#    (a) the propagated exception is the finally-unlock's aborted-transaction error,
#        masking the real migration error;
#    (b) the advisory lock is NOT released by the runner while the connection stays open;
#    (c) the connection is left in aborted-transaction state (no ROLLBACK issued);
#    (d) closing the connection DOES release the session-level lock;
#    (e) no partial (half-built) table survives -- the failed file's own txn rolled back.
# ---------------------------------------------------------------------------
@requires_pg
def test_rev_apply_chain_locked_failure_path_characterization(dsn: str) -> None:
    async def scenario() -> None:
        setup = await _connect()
        try:
            await _drop_all(setup)
            await _apply_baseline(setup)
        finally:
            await setup.close()

        tmp = Path(tempfile.mkdtemp())
        (tmp / "boom.sql").write_text(
            "BEGIN;\nCREATE TABLE _rev_boom(x int);\nSELECT 1/0;\nCOMMIT;\n", encoding="utf-8"
        )
        conn = await _connect()
        propagated = None
        try:
            await _runner().apply_chain_locked(conn, tmp, ["boom.sql"])
            assert False, "expected failure did not raise"
        except BaseException as exc:  # noqa: BLE001
            propagated = exc
        # (a) real error masked by aborted-transaction error from the finally unlock
        assert isinstance(
            propagated, asyncpg.exceptions.InFailedSQLTransactionError
        ), f"expected the masking InFailedSQLTransactionError, got {type(propagated).__name__}"
        assert "division" not in str(propagated).lower(), "root-cause error was NOT masked (good?)"
        # (b) lock still held while conn open -> runner did not release it on failure
        held_probe = await _connect()
        try:
            got = await held_probe.fetchval(LOCK_KEY_SQL_TRY, _runner().DEFAULT_LOCK_KEY)
            assert got is False, "lock was somehow released by the runner on the failure path"
        finally:
            await held_probe.close()
        # (c) connection left aborted -> not safely reusable without an external ROLLBACK
        with pytest.raises(asyncpg.exceptions.InFailedSQLTransactionError):
            await conn.execute("SELECT 1")
        # (e) no partial table survived
        probe2 = await _connect()
        try:
            assert not await probe2.fetchval("SELECT to_regclass('_rev_boom') IS NOT NULL")
        finally:
            await probe2.close()
        # (d) closing the connection releases the session-level lock
        await conn.close()
        await asyncio.sleep(0.2)
        after = await _connect()
        try:
            got = await after.fetchval(LOCK_KEY_SQL_TRY, _runner().DEFAULT_LOCK_KEY)
            assert got is True, "session lock not released even after connection close"
            await after.fetchval(LOCK_KEY_SQL_UNLOCK, _runner().DEFAULT_LOCK_KEY)
        finally:
            await after.close()

    _run(scenario())


# ---------------------------------------------------------------------------
# 4. A raw failed migration (no runner) + explicit ROLLBACK -> connection reusable.
#    Confirms the recovery pattern the runner itself omits.
# ---------------------------------------------------------------------------
@requires_pg
def test_rev_failed_migration_then_explicit_rollback_reuses_connection(dsn: str) -> None:
    async def scenario() -> None:
        conn = await _connect()
        other = await _connect()
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            sql = (MIGRATIONS / "032_be3_resume_replay_authorization.sql").read_text("utf-8")
            broken = sql.replace("\nCOMMIT;", "\nSELECT 1/0;\nCOMMIT;", 1)
            with pytest.raises(asyncpg.PostgresError):
                await conn.execute(broken)
            # independent connection unaffected
            assert await other.fetchval("SELECT 1") == 1
            # failing conn refuses commands until ROLLBACK
            with pytest.raises(asyncpg.exceptions.InFailedSQLTransactionError):
                await conn.execute("SELECT 1")
            await conn.execute("ROLLBACK")
            assert await conn.fetchval("SELECT 1") == 1
            assert not await conn.fetchval(
                "SELECT to_regclass('resume_replay_authorizations') IS NOT NULL"
            )
        finally:
            await conn.close()
            await other.close()

    _run(scenario())


# ---------------------------------------------------------------------------
# 5. Advisory-lock cleanup across exception kinds + forced termination + conn close.
# ---------------------------------------------------------------------------
@requires_pg
def test_rev_session_lock_released_on_all_teardown_paths(dsn: str) -> None:
    async def _holds() -> bool:
        p = await _connect()
        try:
            got = await p.fetchval(LOCK_KEY_SQL_TRY, _runner().DEFAULT_LOCK_KEY)
            if got:
                await p.fetchval(LOCK_KEY_SQL_UNLOCK, _runner().DEFAULT_LOCK_KEY)
                return False
            return True
        finally:
            await p.close()

    async def scenario() -> None:
        key = _runner().DEFAULT_LOCK_KEY
        # (i) Python exception around a held lock, released in finally
        c = await _connect()
        try:
            await c.fetchval(LOCK_KEY_SQL_LOCK, key)
            try:
                raise RuntimeError("boom")
            except RuntimeError:
                pass
            finally:
                await c.fetchval(LOCK_KEY_SQL_UNLOCK, key)
            assert not await _holds()
        finally:
            await c.close()

        # (ii) asyncio cancellation (BaseException) while holding: connection close releases
        c2 = await _connect()
        await c2.fetchval(LOCK_KEY_SQL_LOCK, key)
        assert await _holds()

        async def _hold_forever():
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                raise

        t = asyncio.ensure_future(_hold_forever())
        await asyncio.sleep(0.05)
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
        await c2.close()  # session end releases the lock
        await asyncio.sleep(0.2)
        assert not await _holds(), "lock not released after cancellation + connection close"

        # (iii) forced backend termination releases a session-level lock
        c3 = await _connect()
        pid = await c3.fetchval("SELECT pg_backend_pid()")
        await c3.fetchval(LOCK_KEY_SQL_LOCK, key)
        assert await _holds()
        admin = await _connect()
        try:
            await admin.execute("SELECT pg_terminate_backend($1)", pid)
        finally:
            await admin.close()
        await asyncio.sleep(0.3)
        assert not await _holds(), "lock not released after forced backend termination"
        try:
            await c3.close()
        except Exception:
            pass

    _run(scenario())


# ---------------------------------------------------------------------------
# 6. Two concurrent FULL migrators with injected delay + injected mid-chain failure.
#    migrator1 holds the lock, sleeps, then fails on a broken 034; migrator2 must wait,
#    then complete the real chain to a coherent schema. Exactly one holds the lock at a time.
# ---------------------------------------------------------------------------
@requires_pg
def test_rev_concurrent_migrators_delay_and_midchain_failure(dsn: str) -> None:
    async def scenario() -> None:
        setup = await _connect()
        try:
            await _drop_all(setup)
            await _apply_baseline(setup)
        finally:
            await setup.close()

        # Build migrator1's chain in a temp dir: a leading pg_sleep, real 031-033, broken 034.
        tmp = Path(tempfile.mkdtemp())
        (tmp / "00_delay.sql").write_text(
            "BEGIN;\nSELECT pg_sleep(2);\nCOMMIT;\n", encoding="utf-8"
        )
        for f in (
            "031_clarification_lifecycle_outbox_foundation.sql",
            "032_be3_resume_replay_authorization.sql",
            "033_be3_resume_requests.sql",
        ):
            (tmp / f).write_text((MIGRATIONS / f).read_text("utf-8"), encoding="utf-8")
        broken034 = (
            (MIGRATIONS / "034_be3_replay_requests.sql")
            .read_text("utf-8")
            .replace("\nCOMMIT;", "\nSELECT 1/0;\nCOMMIT;", 1)
        )
        (tmp / "034_broken.sql").write_text(broken034, encoding="utf-8")
        m1_files = [
            "00_delay.sql",
            "031_clarification_lifecycle_outbox_foundation.sql",
            "032_be3_resume_replay_authorization.sql",
            "033_be3_resume_requests.sql",
            "034_broken.sql",
        ]

        observations: dict = {}

        async def migrator1() -> None:
            conn = await _connect()
            try:
                with pytest.raises(asyncpg.PostgresError):
                    await _runner().apply_chain_locked(conn, tmp, m1_files)
            finally:
                # close releases the leaked session lock (runner did not release it on failure)
                await conn.close()

        async def migrator2() -> None:
            await asyncio.sleep(0.3)  # ensure m1 grabs the lock first
            # While m1 holds the lock (mid delay), a non-blocking probe must be refused.
            probe = await _connect()
            try:
                got = await probe.fetchval(LOCK_KEY_SQL_TRY, _runner().DEFAULT_LOCK_KEY)
                observations["probe_refused_while_m1_holds"] = got is False
                if got:
                    await probe.fetchval(LOCK_KEY_SQL_UNLOCK, _runner().DEFAULT_LOCK_KEY)
            finally:
                await probe.close()
            conn = await _connect()
            try:
                await _runner().apply_chain_locked(conn, MIGRATIONS, CHAIN_FILES)
                observations["m2_completed"] = True
            finally:
                await conn.close()

        await asyncio.gather(migrator1(), migrator2())

        assert (
            observations.get("probe_refused_while_m1_holds") is True
        ), "second migrator was NOT blocked while the first held the lock"
        assert observations.get("m2_completed") is True

        verify = await _connect()
        try:
            for name in ALL_TABLES:
                assert await verify.fetchval("SELECT to_regclass($1) IS NOT NULL", name), name
                pk = await verify.fetchval(
                    "SELECT count(*) FROM information_schema.table_constraints "
                    "WHERE table_schema='public' AND table_name=$1 AND constraint_type='PRIMARY KEY'",
                    name,
                )
                assert pk == 1, f"{name} has {pk} primary keys (duplicate/partial object)"
            # lock is free afterward
            got = await verify.fetchval(LOCK_KEY_SQL_TRY, _runner().DEFAULT_LOCK_KEY)
            assert got is True
            await verify.fetchval(LOCK_KEY_SQL_UNLOCK, _runner().DEFAULT_LOCK_KEY)
        finally:
            await verify.close()

    _run(scenario())


# ---------------------------------------------------------------------------
# 7. Out-of-order fails closed; 8. duplicate idempotent; 9. ambiguous-commit blind reapply.
# ---------------------------------------------------------------------------
@requires_pg
def test_rev_out_of_order_fails_closed(dsn: str) -> None:
    async def scenario() -> None:
        conn = await _connect()
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            await _apply(conn, "031_clarification_lifecycle_outbox_foundation.sql")
            with pytest.raises(asyncpg.exceptions.UndefinedTableError):
                await _apply(conn, "033_be3_resume_requests.sql")  # needs 032
            await conn.execute("ROLLBACK")
            assert not await conn.fetchval("SELECT to_regclass('resume_requests') IS NOT NULL")
            # 031 down out of order (before 034 down) also fails closed if 034 exists:
            await _apply(conn, "032_be3_resume_replay_authorization.sql")
            await _apply(conn, "033_be3_resume_requests.sql")
            await _apply(conn, "034_be3_replay_requests.sql")
            with pytest.raises(asyncpg.PostgresError):
                await _apply(conn, "031_clarification_lifecycle_outbox_foundation_down.sql")
            await conn.execute("ROLLBACK")
            # replay_requests (034) still references outbox -> outbox not dropped
            assert await conn.fetchval(
                "SELECT to_regclass('clarification_lifecycle_outbox') IS NOT NULL"
            )
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_rev_duplicate_invocation_idempotent_and_ambiguous_reapply(dsn: str) -> None:
    async def scenario() -> None:
        conn = await _connect()
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            for f in CHAIN_FILES:
                await _apply(conn, f)
            fp1 = await _runner().schema_fingerprint(conn, ALL_TABLES)
            # duplicate full chain
            for f in CHAIN_FILES:
                await _apply(conn, f)
            fp2 = await _runner().schema_fingerprint(conn, ALL_TABLES)
            assert fp1 == fp2, "duplicate chain invocation changed the fingerprint"
            # ambiguous-commit stand-in: blind reapply of a single real file, fingerprint stable
            await _apply(conn, "032_be3_resume_replay_authorization.sql")
            fp3 = await _runner().schema_fingerprint(conn, ALL_TABLES)
            assert fp3 == fp1, "blind reapply changed the fingerprint (unsafe ambiguous recovery)"
        finally:
            await conn.close()

    _run(scenario())


# ---------------------------------------------------------------------------
# 10. Foreign/wrong-shaped pre-existing object is not silently accepted.
# ---------------------------------------------------------------------------
@requires_pg
def test_rev_foreign_wrong_shaped_object_not_silently_accepted(dsn: str) -> None:
    async def scenario() -> None:
        conn = await _connect()
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            await conn.execute("CREATE TABLE resume_replay_authorizations (id int)")
            # real 032: CREATE TABLE IF NOT EXISTS is a no-op, then its index references columns
            # that do not exist on the foreign table -> loud failure, never silent success.
            with pytest.raises(asyncpg.PostgresError):
                await _apply(conn, "032_be3_resume_replay_authorization.sql")
            await conn.execute("ROLLBACK")
            fp = await _runner().schema_fingerprint(conn, ["resume_replay_authorizations"])
            cols = fp["resume_replay_authorizations"]["columns"]
            assert len(cols) == 1, "fingerprint failed to expose the wrong-shaped foreign object"
            # dependent migration 033 refuses to build against the wrong-shaped 032 table.
            with pytest.raises(asyncpg.PostgresError):
                await _apply(conn, "033_be3_resume_requests.sql")
            await conn.execute("ROLLBACK")
            assert not await conn.fetchval("SELECT to_regclass('resume_requests') IS NOT NULL")
        finally:
            await conn.close()

    _run(scenario())


# ---------------------------------------------------------------------------
# 11. Fingerprint determinism + all six §10 mutation types (characterizes the FK/CHECK gaps).
# ---------------------------------------------------------------------------
@requires_pg
def test_rev_fingerprint_mutation_detection(dsn: str) -> None:
    async def build(conn) -> None:
        await _drop_all(conn)
        await _apply_baseline(conn)
        for f in CHAIN_FILES:
            await _apply(conn, f)

    async def scenario() -> None:
        conn = await _connect()
        try:
            await build(conn)
            base = await _runner().schema_fingerprint(conn, ALL_TABLES)
            assert base == await _runner().schema_fingerprint(conn, ALL_TABLES), "not deterministic"

            # DETECTED mutations (must differ):
            await conn.execute("DROP INDEX idx_rr_state")
            assert await _runner().schema_fingerprint(conn, ALL_TABLES) != base  # drop index

            await build(conn)
            base = await _runner().schema_fingerprint(conn, ALL_TABLES)
            await conn.execute("DROP INDEX idx_clo_dead_at")
            await conn.execute(
                "CREATE INDEX idx_clo_dead_at ON clarification_lifecycle_outbox (dead_at) "
                "WHERE status='pending'"
            )
            assert await _runner().schema_fingerprint(conn, ALL_TABLES) != base  # partial predicate

            await build(conn)
            base = await _runner().schema_fingerprint(conn, ALL_TABLES)
            await conn.execute("ALTER TABLE resume_requests ALTER COLUMN workflow_id SET NOT NULL")
            assert await _runner().schema_fingerprint(conn, ALL_TABLES) != base  # nullability

            await build(conn)
            base = await _runner().schema_fingerprint(conn, ALL_TABLES)
            await conn.execute(
                "ALTER TABLE resume_requests ADD CONSTRAINT chk_rev_new CHECK (length(requested_by)<500)"
            )
            assert (
                await _runner().schema_fingerprint(conn, ALL_TABLES) != base
            )  # add CHECK (new name)

            await build(conn)
            base = await _runner().schema_fingerprint(conn, ALL_TABLES)
            await conn.execute(
                "ALTER TABLE resume_requests ALTER COLUMN state SET DEFAULT 'authorized'"
            )
            assert await _runner().schema_fingerprint(conn, ALL_TABLES) != base  # default

            # NOT DETECTED mutations (fingerprint blind spots -- characterized, review finding):
            await build(conn)
            base = await _runner().schema_fingerprint(conn, ALL_TABLES)
            fkname = await conn.fetchval(
                "SELECT tc.constraint_name FROM information_schema.table_constraints tc "
                "JOIN information_schema.key_column_usage kcu "
                "ON tc.constraint_name=kcu.constraint_name "
                "WHERE tc.table_name='resume_requests' AND tc.constraint_type='FOREIGN KEY' "
                "AND kcu.column_name='task_id' LIMIT 1"
            )
            await conn.execute(f'ALTER TABLE resume_requests DROP CONSTRAINT "{fkname}"')
            await conn.execute(
                f'ALTER TABLE resume_requests ADD CONSTRAINT "{fkname}" '
                "FOREIGN KEY (task_id) REFERENCES operator_tasks(id) ON DELETE CASCADE"
            )
            fk_changed = await _runner().schema_fingerprint(conn, ALL_TABLES) != base
            assert (
                fk_changed is False
            ), "unexpected: FK ON DELETE action change WAS detected (fingerprint improved?)"

            await build(conn)
            base = await _runner().schema_fingerprint(conn, ALL_TABLES)
            await conn.execute(
                "ALTER TABLE resume_requests DROP CONSTRAINT chk_rr_requested_by_bounded"
            )
            await conn.execute(
                "ALTER TABLE resume_requests ADD CONSTRAINT chk_rr_requested_by_bounded "
                "CHECK (length(requested_by) <= 999)"
            )
            chk_changed = await _runner().schema_fingerprint(conn, ALL_TABLES) != base
            assert (
                chk_changed is False
            ), "unexpected: CHECK expression change (same name) WAS detected"
        finally:
            await conn.close()

    _run(scenario())


# ---------------------------------------------------------------------------
# 12. Pre-activation down (valid scenario) + reapply fingerprint equality + sentinel preserved.
# ---------------------------------------------------------------------------
@requires_pg
def test_rev_predown_reapply_fingerprint_equal(dsn: str) -> None:
    async def scenario() -> None:
        conn = await _connect()
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            s = await _seed_sentinel(conn)
            for f in CHAIN_FILES:
                await _apply(conn, f)
            fp_before = await _runner().schema_fingerprint(conn, ALL_TABLES)
            for f in DOWN_FILES:
                await _apply(conn, f)
            for name in NEW_TABLES:
                assert not await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", name)
            for name in ("operator_tasks", "task_messages", "operator_clarification_requests"):
                assert await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", name)
            await _assert_sentinel_unchanged(conn, s)
            for f in CHAIN_FILES:
                await _apply(conn, f)
            fp_after = await _runner().schema_fingerprint(conn, ALL_TABLES)
            assert fp_before == fp_after, "fingerprint differs after down+reapply"
            await _assert_sentinel_unchanged(conn, s)
        finally:
            await conn.close()

    _run(scenario())


# ---------------------------------------------------------------------------
# 13. Post-write operational rollback (non-destructive) + old-version compatibility.
# ---------------------------------------------------------------------------
@requires_pg
def test_rev_post_write_nondestructive_and_old_version_compat(dsn: str) -> None:
    async def scenario() -> None:
        conn = await _connect()
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            s = await _seed_sentinel(conn)
            for f in CHAIN_FILES:
                await _apply(conn, f)

            team, project = uuid.uuid4(), uuid.uuid4()
            authz, outbox = uuid.uuid4(), uuid.uuid4()
            await conn.execute(
                "INSERT INTO clarification_lifecycle_outbox "
                "(id, clarification_id, task_id, event_type, idempotency_key) "
                "VALUES ($1,$2,$3,'clarification.reminder_due',$4)",
                outbox,
                s["clarification_id"],
                s["task_id"],
                f"rev-outbox-{outbox}",
            )
            await conn.execute(
                "INSERT INTO resume_replay_authorizations "
                "(authorization_id, action_type, resource_type, resource_id, team_id, project_id, "
                "requested_by, requested_role, resource_state_version, expires_at, idempotency_key) "
                "VALUES ($1,'resume','clarification',$2,$3,$4,'rev','agent_operator','v1',"
                "now()+interval '1 hour',$5)",
                authz,
                s["clarification_id"],
                team,
                project,
                f"rev-authz-{authz}",
            )
            rr = uuid.uuid4()
            await conn.execute(
                "INSERT INTO resume_requests "
                "(resume_request_id, authorization_id, clarification_id, task_id, team_id, "
                "project_id, resource_state_version, requested_by, idempotency_key) "
                "VALUES ($1,$2,$3,$4,$5,$6,'v1','rev',$7)",
                rr,
                authz,
                s["clarification_id"],
                s["task_id"],
                team,
                project,
                f"rev-rr-{rr}",
            )
            pr = uuid.uuid4()
            await conn.execute(
                "INSERT INTO replay_requests "
                "(replay_request_id, authorization_id, outbox_event_id, event_type, destination, "
                "team_id, project_id, resource_state_version, requested_by, idempotency_key) "
                "VALUES ($1,$2,$3,'clarification.reminder_due','audit',$4,$5,'v1','rev',$6)",
                pr,
                authz,
                outbox,
                team,
                project,
                f"rev-pr-{pr}",
            )
            ap = uuid.uuid4()
            await conn.execute(
                "INSERT INTO production_action_approvals "
                "(approval_id, action_type, resource_type, resource_id, team_id, project_id, "
                "resource_state_version, granted_by, granted_role, expires_at, idempotency_key) "
                "VALUES ($1,'resume','clarification',$2,$3,$4,'v1','rev','reviewer_approver',"
                "now()+interval '1 hour',$5)",
                ap,
                s["clarification_id"],
                team,
                project,
                f"rev-ap-{ap}",
            )
            # No destructive down script is run. Confirm every synthetic row survives.
            for tbl, col, rid in (
                ("clarification_lifecycle_outbox", "id", outbox),
                ("resume_replay_authorizations", "authorization_id", authz),
                ("resume_requests", "resume_request_id", rr),
                ("replay_requests", "replay_request_id", pr),
                ("production_action_approvals", "approval_id", ap),
            ):
                assert (
                    await conn.fetchval(f"SELECT count(*) FROM {tbl} WHERE {col}=$1", rid) == 1
                ), f"{tbl} row lost"

            # Old-version compatibility, exercised several ways (not a single SELECT):
            # (a) explicit pre-031 column list still works
            row = await conn.fetchrow(
                "SELECT id, title, status, created_by FROM operator_tasks WHERE id=$1", s["task_id"]
            )
            assert row is not None
            # (b) SELECT * returns rows without error and includes only additive columns
            star = await conn.fetchrow(
                "SELECT * FROM operator_clarification_requests WHERE id=$1", s["clarification_id"]
            )
            assert star is not None
            # (c) a representative task write using only pre-031 columns still succeeds
            new_task = uuid.uuid4()
            await conn.execute(
                "INSERT INTO operator_tasks (id, title, task_type, created_by) "
                "VALUES ($1,'old-style write','other','rev')",
                new_task,
            )
            assert (
                await conn.fetchval("SELECT count(*) FROM operator_tasks WHERE id=$1", new_task)
                == 1
            )
            # (d) a representative clarification write not naming any new column still succeeds
            new_msg, new_clar = uuid.uuid4(), uuid.uuid4()
            await conn.execute(
                "INSERT INTO task_messages (id, task_id, sender_type, sender_id, message_type, body) "
                "VALUES ($1,$2,'human','rev','human_message','hi')",
                new_msg,
                new_task,
            )
            await conn.execute(
                "INSERT INTO operator_clarification_requests "
                "(id, task_id, question_message_id, question, requested_by_type, requested_by_id, "
                "due_at, reminder_at) VALUES ($1,$2,$3,'q','human','rev',now()+interval '1 day',"
                "now()+interval '1 hour')",
                new_clar,
                new_task,
                new_msg,
            )
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM operator_clarification_requests WHERE id=$1", new_clar
                )
                == 1
            )
            await _assert_sentinel_unchanged(conn, s)
        finally:
            await conn.close()

    _run(scenario())


# ---------------------------------------------------------------------------
# 14. The runner and its module log no DSN/credential (no logging at all) + guard not bypassed.
# ---------------------------------------------------------------------------
@requires_pg
def test_rev_guard_not_bypassed(dsn: str) -> None:
    assert destructive_pg_refusal_reason() is None


def test_rev_runner_source_has_no_credential_logging() -> None:
    import re

    src = (REPO / "shared" / "sdk" / "backup_dr" / "migration_runner.py").read_text("utf-8")
    # Precise (word-boundary / call-site) checks: the runner receives an already-open connection,
    # never a DSN/credential, and performs no logging or printing at all.
    patterns = {
        "password": r"\bpassword\b",
        "credential": r"\bcredential",
        "dsn identifier": r"\bdsn\b",
        "import logging": r"\bimport\s+logging\b",
        "logging call": r"\blogging\.",
        "logger": r"\blogger\b",
        "print call": r"(?<![A-Za-z_])print\s*\(",
        "os.environ": r"\bos\.environ\b",
        "getenv": r"\bgetenv\b",
    }
    for label, pat in patterns.items():
        assert not re.search(pat, src, re.IGNORECASE), f"migration_runner.py contains {label}"
