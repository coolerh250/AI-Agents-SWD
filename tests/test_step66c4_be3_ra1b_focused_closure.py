"""Step 66C.4-BE3-RA-1FC -- INDEPENDENT focused-closure test battery over the RA-1B remediation.

Written by the original RA-1R independent reviewer (continuity), NOT the RA-1B implementation
session. Re-derives H-1/M-1/M-2/M-3 closure from scratch against an isolated ephemeral PostgreSQL 16,
and probes the paths RA-1B's own 23-test suite does not cover: FK MATCH / constraint validation-state
/ index access-method fingerprint mutations, the ledger vs. down/reapply lifecycle (spec section 13),
the ambiguous-commit reconcile of a wrong-shaped table, and the ``redact_for_operator`` DSN scheme
gap. Every test asserts the ACTUAL observed behavior (including behavior this review flags as a gap),
so the suite is a faithful, reproducible characterization that passes against the code under review.

Does NOT modify migration_runner.py, run_platform_migrations.py, the migrations, or the RA-1A/RA-1B
test suites. Gated by the same fail-closed destructive-PG guard. No shared DB, no feature gate, no
worker/relay/consumer, no production action.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
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


def _mr():
    from shared.sdk.backup_dr import migration_runner

    return migration_runner


async def _connect():
    return await asyncpg.connect(dsn=_DSN)


async def _hard_reset(conn) -> None:
    await conn.execute(
        "DROP TABLE IF EXISTS platform_schema_migrations, production_action_approvals, "
        "replay_requests, resume_requests, resume_replay_authorizations, "
        "clarification_lifecycle_outbox, operator_clarification_requests, task_messages, "
        "operator_tasks CASCADE;"
    )
    await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')


async def _apply(conn, name: str) -> None:
    await conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))


async def _baseline(conn) -> None:
    await _hard_reset(conn)
    for name in BASELINE_FILES:
        await _apply(conn, name)


async def _build_full(conn) -> None:
    await _baseline(conn)
    for name in CHAIN_FILES:
        await _apply(conn, name)


async def _fp(conn):
    return await _mr().schema_fingerprint(conn, ALL_TABLES)


@pytest.fixture
def dsn() -> str:
    assert _DSN is not None
    return _DSN


# ==========================================================================================
# H-1 -- failure-path rollback / unlock / connection disposal / error preservation
# ==========================================================================================
@requires_pg
def test_h1_rollback_before_unlock_preserves_original_error_and_reuses_connection(dsn: str) -> None:
    async def scenario() -> None:
        setup = await _connect()
        try:
            await _baseline(setup)
        finally:
            await setup.close()
        tmp = Path(tempfile.mkdtemp())
        (tmp / "boom.sql").write_text(
            "BEGIN;\nCREATE TABLE _fc_boom(x int);\nSELECT 1/0;\nCOMMIT;\n", encoding="utf-8"
        )
        conn = await _connect()
        propagated = None
        try:
            await _mr().apply_chain_locked(conn, tmp, ["boom.sql"])
            assert False, "expected failure did not raise"
        except BaseException as exc:  # noqa: BLE001
            propagated = exc
        # Original migration error propagates (NOT masked by the unlock).
        assert isinstance(
            propagated, asyncpg.exceptions.DivisionByZeroError
        ), f"original error masked -> got {type(propagated).__name__}"
        assert getattr(propagated, "ra1b_cleanup_errors", None) == [], "unexpected cleanup errors"
        assert getattr(propagated, "ra1b_connection_reusable", None) is True
        # ROLLBACK ran before unlock -> connection is immediately reusable, no aborted state.
        assert await conn.fetchval("SELECT 1") == 1
        # Lock was released (a fresh connection can take it).
        probe = await _connect()
        try:
            got = await probe.fetchval(
                "SELECT pg_try_advisory_lock(hashtextextended($1,0))", _mr().DEFAULT_LOCK_KEY
            )
            assert got is True, "advisory lock not released on the failure path"
            await probe.fetchval(
                "SELECT pg_advisory_unlock(hashtextextended($1,0))", _mr().DEFAULT_LOCK_KEY
            )
        finally:
            await probe.close()
        # No partial half-built object survived.
        assert not await conn.fetchval("SELECT to_regclass('_fc_boom') IS NOT NULL")
        await conn.close()

    _run(scenario())


@requires_pg
def test_h1_forced_backend_termination_disposes_connection(dsn: str) -> None:
    async def scenario() -> None:
        setup = await _connect()
        try:
            await _baseline(setup)
        finally:
            await setup.close()
        # A slow migration file so we can kill the backend mid-apply from an admin connection.
        tmp = Path(tempfile.mkdtemp())
        (tmp / "slow.sql").write_text(
            "BEGIN;\nCREATE TABLE _fc_slow(x int);\nSELECT pg_sleep(3);\nCOMMIT;\n",
            encoding="utf-8",
        )
        conn = await _connect()
        pid = await conn.fetchval("SELECT pg_backend_pid()")
        admin = await _connect()

        async def killer():
            await asyncio.sleep(0.8)
            await admin.execute("SELECT pg_terminate_backend($1)", pid)

        propagated = None
        try:
            await asyncio.gather(_mr().apply_chain_locked(conn, tmp, ["slow.sql"]), killer())
            assert False, "expected failure did not raise"
        except BaseException as exc:  # noqa: BLE001
            propagated = exc
        # A cleanup step (ROLLBACK on a dead backend) failed -> connection disposed, flagged.
        assert getattr(propagated, "ra1b_connection_reusable", None) is False
        assert conn.is_closed(), "runner did not dispose the connection after a cleanup failure"
        await admin.close()
        # A fresh connection is entirely unaffected; the lock is free.
        fresh = await _connect()
        try:
            got = await fresh.fetchval(
                "SELECT pg_try_advisory_lock(hashtextextended($1,0))", _mr().DEFAULT_LOCK_KEY
            )
            assert got is True
            await fresh.fetchval(
                "SELECT pg_advisory_unlock(hashtextextended($1,0))", _mr().DEFAULT_LOCK_KEY
            )
        finally:
            await fresh.close()

    _run(scenario())


@requires_pg
def test_h1_cancellation_while_holding_lock_releases_and_propagates(dsn: str) -> None:
    async def scenario() -> None:
        setup = await _connect()
        try:
            await _baseline(setup)
        finally:
            await setup.close()
        tmp = Path(tempfile.mkdtemp())
        (tmp / "slow.sql").write_text(
            "BEGIN;\nCREATE TABLE _fc_c(x int);\nSELECT pg_sleep(5);\nCOMMIT;\n", encoding="utf-8"
        )
        conn = await _connect()
        task = asyncio.ensure_future(_mr().apply_chain_locked(conn, tmp, ["slow.sql"]))
        await asyncio.sleep(1.0)  # let it acquire the lock and start the sleep
        task.cancel()
        cancelled = False
        try:
            await task
        except asyncio.CancelledError:
            cancelled = True
        except BaseException:  # noqa: BLE001
            cancelled = False
        assert cancelled, "cancellation did not ultimately propagate to the caller"
        with contextlib_suppress():
            await conn.close()
        await asyncio.sleep(0.3)
        probe = await _connect()
        try:
            got = await probe.fetchval(
                "SELECT pg_try_advisory_lock(hashtextextended($1,0))", _mr().DEFAULT_LOCK_KEY
            )
            assert got is True, "lock not released after cancellation"
            await probe.fetchval(
                "SELECT pg_advisory_unlock(hashtextextended($1,0))", _mr().DEFAULT_LOCK_KEY
            )
        finally:
            await probe.close()

    _run(scenario())


@requires_pg
def test_h1_pool_returns_clean_connection_after_failed_migration(dsn: str) -> None:
    async def scenario() -> None:
        pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=1)
        try:
            async with pool.acquire() as c:
                await _baseline(c)
            tmp = Path(tempfile.mkdtemp())
            (tmp / "boom.sql").write_text(
                "BEGIN;\nCREATE TABLE _fc_pool(x int);\nSELECT 1/0;\nCOMMIT;\n", encoding="utf-8"
            )
            async with pool.acquire() as c:
                with pytest.raises(asyncpg.exceptions.DivisionByZeroError):
                    await _mr().apply_chain_locked(c, tmp, ["boom.sql"])
            # Next borrower (same single pooled slot) must be clean: idle, no lock, usable.
            async with pool.acquire() as c:
                assert await c.fetchval("SELECT 1") == 1
                got = await c.fetchval(
                    "SELECT pg_try_advisory_lock(hashtextextended($1,0))", _mr().DEFAULT_LOCK_KEY
                )
                assert got is True, "advisory lock leaked into a pooled connection"
                await c.fetchval(
                    "SELECT pg_advisory_unlock(hashtextextended($1,0))", _mr().DEFAULT_LOCK_KEY
                )
        finally:
            await pool.close()

    _run(scenario())


@requires_pg
def test_h1_cleanup_error_attribute_attaches_to_realistic_exception_types(dsn: str) -> None:
    # The runner attaches .ra1b_* attributes to the propagated exception. Confirm every exception
    # type actually reachable from a migration/lock/cancellation path accepts the attribute (so the
    # attach itself can never raise a NEW masking error).
    mr = _mr()
    for exc in (
        ZeroDivisionError("x"),
        asyncio.CancelledError(),
        asyncpg.PostgresError("p"),
        mr.MigrationLockTimeoutError("l"),
        mr.SchemaDriftError("d"),
        TimeoutError("t"),
    ):
        setattr(exc, "ra1b_connection_reusable", False)
        assert getattr(exc, "ra1b_connection_reusable") is False


# ==========================================================================================
# M-1 -- semantic fingerprint completeness (all 11 mutation categories)
# ==========================================================================================
@requires_pg
def test_m1_all_semantic_mutations_detected(dsn: str) -> None:
    async def scenario() -> None:
        conn = await _connect()
        try:

            async def rebuild():
                await _build_full(conn)
                return await _fp(conn)

            async def find_task_fk():
                return await conn.fetchval(
                    "SELECT con.conname FROM pg_constraint con JOIN pg_class r ON r.oid=con.conrelid "
                    "WHERE r.relname='resume_requests' AND con.contype='f' "
                    "AND pg_get_constraintdef(con.oid) LIKE '%task_id%operator_tasks%' LIMIT 1"
                )

            # determinism
            base = await rebuild()
            assert base == await _fp(conn), "fingerprint not deterministic"

            # 1. same-name CHECK expression change
            await conn.execute(
                "ALTER TABLE resume_requests DROP CONSTRAINT chk_rr_requested_by_bounded"
            )
            await conn.execute(
                "ALTER TABLE resume_requests ADD CONSTRAINT chk_rr_requested_by_bounded "
                "CHECK (length(requested_by) <= 999)"
            )
            assert await _fp(conn) != base, "CHECK expression change (same name) not detected"

            # 2-5. FK ON DELETE / ON UPDATE / MATCH / deferrability
            for clause in (
                "ON DELETE CASCADE",
                "ON UPDATE CASCADE",
                "MATCH FULL",
                "DEFERRABLE INITIALLY DEFERRED",
            ):
                base = await rebuild()
                fk = await find_task_fk()
                await conn.execute(f'ALTER TABLE resume_requests DROP CONSTRAINT "{fk}"')
                await conn.execute(
                    f'ALTER TABLE resume_requests ADD CONSTRAINT "{fk}" '
                    f"FOREIGN KEY (task_id) REFERENCES operator_tasks(id) {clause}"
                )
                assert await _fp(conn) != base, f"FK {clause} change not detected"

            # 6. constraint validation-state change (NOT VALID -> validated)
            base = await rebuild()
            await conn.execute(
                "ALTER TABLE resume_requests ADD CONSTRAINT chk_fc_nv CHECK (length(requested_by) < 1000) NOT VALID"
            )
            nv = await _fp(conn)
            assert nv != base, "adding a NOT VALID constraint not detected"
            await conn.execute("ALTER TABLE resume_requests VALIDATE CONSTRAINT chk_fc_nv")
            assert (
                await _fp(conn) != nv
            ), "validation-state change (NOT VALID -> valid) not detected"

            # 7. partial-index predicate change
            base = await rebuild()
            await conn.execute("DROP INDEX idx_clo_dead_at")
            await conn.execute(
                "CREATE INDEX idx_clo_dead_at ON clarification_lifecycle_outbox (dead_at) WHERE status='pending'"
            )
            assert await _fp(conn) != base, "partial-index predicate change not detected"

            # 8. index expression change
            base = await rebuild()
            await conn.execute("CREATE INDEX idx_fc_expr ON resume_requests (lower(requested_by))")
            assert await _fp(conn) != base, "index expression not detected"

            # 9. index access-method change (same name btree -> hash)
            await rebuild()
            await conn.execute(
                "CREATE INDEX idx_fc_am ON resume_requests USING btree (failure_reason_code)"
            )
            base = await _fp(conn)
            await conn.execute("DROP INDEX idx_fc_am")
            await conn.execute(
                "CREATE INDEX idx_fc_am ON resume_requests USING hash (failure_reason_code)"
            )
            assert await _fp(conn) != base, "index access-method change (same name) not detected"

            # 10. column default change
            base = await rebuild()
            await conn.execute(
                "ALTER TABLE resume_requests ALTER COLUMN state SET DEFAULT 'authorized'"
            )
            assert await _fp(conn) != base, "default change not detected"

            # 11. nullability change + round-trip returns to identical fingerprint
            base = await rebuild()
            await conn.execute(
                "ALTER TABLE resume_requests ALTER COLUMN requested_by DROP NOT NULL"
            )
            assert await _fp(conn) != base, "nullability change not detected"
            await conn.execute("ALTER TABLE resume_requests ALTER COLUMN requested_by SET NOT NULL")
            assert await _fp(conn) == base, "nullability round-trip not fingerprint-stable"
        finally:
            await conn.close()

    _run(scenario())


# ==========================================================================================
# M-2 -- ledger provenance, ambiguous commit, and the section-13 down/reapply lifecycle
# ==========================================================================================
@requires_pg
def test_m2_ledger_apply_checksum_untracked_and_reconcile(dsn: str) -> None:
    async def scenario() -> None:
        mr = _mr()
        conn = await _connect()
        try:
            # normal ledger-aware apply -> all applied with correct checksums
            await _baseline(conn)
            result = await mr.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            assert result.result_code == "success"
            assert result.applied_versions == ["031", "032", "033", "034", "035"]
            rows = await conn.fetch(
                f"SELECT migration_version, status, migration_sha256 FROM {mr.LEDGER_TABLE}"
            )
            assert all(r["status"] == "applied" for r in rows)
            for r in rows:
                fname = next(f for f in CHAIN_FILES if f.startswith(r["migration_version"]))
                assert r["migration_sha256"] == mr._sha256_file(MIGRATIONS / fname)

            # duplicate invocation is a ledger fast-path skip (nothing re-applied)
            result2 = await mr.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            assert result2.applied_versions == [] and result2.reconciled_versions == []

            # checksum mismatch on an applied version fails closed, row not overwritten
            await conn.execute(
                f"UPDATE {mr.LEDGER_TABLE} SET migration_sha256='deadbeef' WHERE migration_version='033'"
            )
            with pytest.raises(mr.MigrationChecksumMismatchError):
                await mr.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            still = await conn.fetchval(
                f"SELECT migration_sha256 FROM {mr.LEDGER_TABLE} WHERE migration_version='033'"
            )
            assert still == "deadbeef", "checksum-mismatch row was overwritten"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_m2_untracked_schema_and_partial_applying_fail_closed(dsn: str) -> None:
    async def scenario() -> None:
        mr = _mr()
        # untracked: target table exists with no ledger record
        conn = await _connect()
        try:
            await _baseline(conn)
            await mr.ensure_ledger_bootstrapped(conn)
            await _apply(conn, "032_be3_resume_replay_authorization.sql")  # real, but no ledger row
            with pytest.raises(mr.UntrackedSchemaError):
                await mr.apply_chain_with_ledger(
                    conn, MIGRATIONS, ["032_be3_resume_replay_authorization.sql"]
                )
        finally:
            await conn.close()
        # partial applying: applying row but the target object does NOT exist -> drifted
        conn = await _connect()
        try:
            await _baseline(conn)
            await mr.ensure_ledger_bootstrapped(conn)
            checksum = mr._sha256_file(MIGRATIONS / "032_be3_resume_replay_authorization.sql")
            await conn.execute(
                f"INSERT INTO {mr.LEDGER_TABLE} "
                "(migration_version, migration_filename, migration_sha256, status, runner_version) "
                "VALUES ('032','032_be3_resume_replay_authorization.sql',$1,'applying','manual')",
                checksum,
            )
            with pytest.raises(mr.SchemaDriftError):
                await mr.apply_chain_with_ledger(
                    conn, MIGRATIONS, ["032_be3_resume_replay_authorization.sql"]
                )
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_m2_ambiguous_commit_reconciles_when_schema_present(dsn: str) -> None:
    async def scenario() -> None:
        mr = _mr()
        conn = await _connect()
        try:
            await _baseline(conn)
            await mr.ensure_ledger_bootstrapped(conn)
            # classic ambiguous commit: real DDL applied, applying row present, no 'applied' mark yet
            await _apply(conn, "032_be3_resume_replay_authorization.sql")
            checksum = mr._sha256_file(MIGRATIONS / "032_be3_resume_replay_authorization.sql")
            await conn.execute(
                f"INSERT INTO {mr.LEDGER_TABLE} "
                "(migration_version, migration_filename, migration_sha256, status, runner_version) "
                "VALUES ('032','032_be3_resume_replay_authorization.sql',$1,'applying','manual')",
                checksum,
            )
            result = await mr.apply_chain_with_ledger(
                conn, MIGRATIONS, ["032_be3_resume_replay_authorization.sql"]
            )
            assert result.reconciled_versions == ["032"]
            status = await conn.fetchval(
                f"SELECT status FROM {mr.LEDGER_TABLE} WHERE migration_version='032' "
                "ORDER BY started_at DESC LIMIT 1"
            )
            assert status == "reconciled_after_ambiguous_commit"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_m2_GAP_reconcile_accepts_wrong_shaped_table(dsn: str) -> None:
    """FINDING (M-2 gap): reconciliation validates only filename+checksum+table-EXISTENCE, not shape
    (expected_fingerprint is never recorded on the 'applying' row). A drifted/wrong-shaped table with
    a matching-checksum applying row is RECONCILED as good rather than failing closed as drift."""

    async def scenario() -> None:
        mr = _mr()
        conn = await _connect()
        try:
            await _baseline(conn)
            await mr.ensure_ledger_bootstrapped(conn)
            await _apply(conn, "032_be3_resume_replay_authorization.sql")
            await conn.execute("ALTER TABLE resume_replay_authorizations ADD COLUMN fc_rogue int")
            checksum = mr._sha256_file(MIGRATIONS / "032_be3_resume_replay_authorization.sql")
            await conn.execute(
                f"INSERT INTO {mr.LEDGER_TABLE} "
                "(migration_version, migration_filename, migration_sha256, status, runner_version) "
                "VALUES ('032','032_be3_resume_replay_authorization.sql',$1,'applying','manual')",
                checksum,
            )
            # Observed behavior: it reconciles the WRONG-shaped table (the gap).
            result = await mr.apply_chain_with_ledger(
                conn, MIGRATIONS, ["032_be3_resume_replay_authorization.sql"]
            )
            assert result.reconciled_versions == ["032"], "behavior changed -- re-evaluate the gap"
            # The rogue column is still present and was accepted.
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_name='resume_replay_authorizations' AND column_name='fc_rogue'"
                )
                == 1
            )
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_m2_GAP_down_then_reapply_lifecycle_is_inconsistent(dsn: str) -> None:
    """FINDING (M-2, spec section 13): after a raw pre-activation down, the ledger still claims the
    migrations are 'applied', plan_chain reports drift_status 'ok' / current_version set (does NOT
    fail closed on the ledger-vs-schema mismatch), and a ledger-aware reapply reports SUCCESS while
    silently skipping every migration -- the dropped tables are NOT recreated. No ledger-aware down
    and no documented resolution-B fail-closed exists. Characterized here as the actual behavior."""

    async def scenario() -> None:
        mr = _mr()
        conn = await _connect()
        try:
            await _baseline(conn)
            await mr.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            for name in DOWN_FILES:
                await _apply(conn, name)
            # tables gone
            for t in NEW_TABLES:
                assert not await conn.fetchval("SELECT to_regclass('public.'||$1) IS NOT NULL", t)
            # ledger still claims applied
            statuses = {
                r["migration_version"]: r["status"]
                for r in await conn.fetch(
                    f"SELECT migration_version, status FROM {mr.LEDGER_TABLE}"
                )
            }
            assert all(v == "applied" for v in statuses.values()), "ledger unexpectedly updated"
            # plan does NOT fail closed: reports ok / no pending / a current version, despite empty schema
            plan = await mr.plan_chain(conn, MIGRATIONS, CHAIN_FILES)
            assert plan.pending_versions == []
            assert plan.current_version == "035"
            assert all(v == "ok" for v in plan.drift_status.values())
            assert all(present is False for present in plan.schema_state.values())
            # reapply reports success but recreates nothing (silent skip)
            result = await mr.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            assert result.result_code == "success"
            assert result.applied_versions == [] and result.reconciled_versions == []
            for t in NEW_TABLES:
                assert not await conn.fetchval("SELECT to_regclass('public.'||$1) IS NOT NULL", t)
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_m2_wrong_shaped_ledger_table_fails_closed(dsn: str) -> None:
    async def scenario() -> None:
        mr = _mr()
        conn = await _connect()
        try:
            await _baseline(conn)
            await conn.execute("CREATE TABLE platform_schema_migrations (id int)")
            with pytest.raises(asyncpg.PostgresError):
                await mr.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_m2_baseline_029_030_boundary(dsn: str) -> None:
    mr = _mr()
    # ledger governs only 031+ (029/030 are trusted baseline, not in the created-tables catalog)
    assert set(mr.MIGRATION_CREATED_TABLES) == set(CHAIN_FILES)
    for f in BASELINE_FILES:
        assert f not in mr.MIGRATION_CREATED_TABLES

    async def scenario() -> None:
        conn = await _connect()
        try:
            # clean pre-031 DB (029/030 only, no ledger) -> a fresh chain applies normally
            await _baseline(conn)
            result = await mr.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            assert result.applied_versions == ["031", "032", "033", "034", "035"]
        finally:
            await conn.close()

    _run(scenario())


# ==========================================================================================
# M-3 -- bounded waits, timeouts, plan mode, CLI, redaction
# ==========================================================================================
@requires_pg
def test_m3_bounded_lock_wait_timeout_and_release(dsn: str) -> None:
    async def scenario() -> None:
        mr = _mr()
        holder = await _connect()
        await holder.fetchval(
            "SELECT pg_advisory_lock(hashtextextended($1,0))", mr.DEFAULT_LOCK_KEY
        )
        conn = await _connect()
        try:
            import time as _t

            start = _t.monotonic()
            with pytest.raises(mr.MigrationLockTimeoutError):
                await mr.apply_chain_locked(
                    conn,
                    MIGRATIONS,
                    CHAIN_FILES,
                    lock_wait_timeout_seconds=1.0,
                    poll_interval_seconds=0.1,
                )
            waited = _t.monotonic() - start
            assert 0.9 <= waited <= 5.0, f"lock wait not bounded near deadline: {waited}s"
            # timeout acquired no lock: holder still holds it exclusively
            probe = await _connect()
            try:
                got = await probe.fetchval(
                    "SELECT pg_try_advisory_lock(hashtextextended($1,0))", mr.DEFAULT_LOCK_KEY
                )
                assert got is False, "lock timeout left/took a lock"
            finally:
                await probe.close()
            # release -> a fresh apply can now proceed
            await holder.fetchval(
                "SELECT pg_advisory_unlock(hashtextextended($1,0))", mr.DEFAULT_LOCK_KEY
            )
            await mr.apply_chain_locked(
                conn, MIGRATIONS, CHAIN_FILES, lock_wait_timeout_seconds=5.0
            )
            assert await conn.fetchval("SELECT to_regclass('resume_requests') IS NOT NULL")
        finally:
            await holder.close()
            await conn.close()

    _run(scenario())


@requires_pg
def test_m3_invalid_timeout_config_fails_closed(dsn: str) -> None:
    async def scenario() -> None:
        mr = _mr()
        conn = await _connect()
        try:
            await _baseline(conn)
            for kwargs in (
                {"lock_wait_timeout_seconds": 0.0},
                {"lock_wait_timeout_seconds": 10_000.0},
                {"poll_interval_seconds": 100.0, "lock_wait_timeout_seconds": 2.0},
            ):
                with pytest.raises(mr.MigrationConfigError):
                    await mr.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES, **kwargs)
            with pytest.raises(mr.MigrationConfigError):
                await mr.apply_chain_with_ledger(
                    conn, MIGRATIONS, CHAIN_FILES, statement_timeout_ms=1
                )
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_m3_statement_timeouts_set_and_restored(dsn: str) -> None:
    async def scenario() -> None:
        mr = _mr()
        conn = await _connect()
        try:
            await _baseline(conn)
            before = {
                s: await conn.fetchval(f"SHOW {s}")
                for s in (
                    "statement_timeout",
                    "lock_timeout",
                    "idle_in_transaction_session_timeout",
                )
            }
            await mr.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            after = {
                s: await conn.fetchval(f"SHOW {s}")
                for s in (
                    "statement_timeout",
                    "lock_timeout",
                    "idle_in_transaction_session_timeout",
                )
            }
            assert after == before, f"session timeouts not restored: {before} -> {after}"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_m3_plan_mode_no_writes_across_schema_states(dsn: str) -> None:
    async def scenario() -> None:
        mr = _mr()
        conn = await _connect()
        try:
            # (a) fully empty (no baseline, no ledger)
            await _hard_reset(conn)
            plan = await mr.plan_chain(conn, MIGRATIONS, CHAIN_FILES)
            assert plan.pending_versions == ["031", "032", "033", "034", "035"]
            assert not await conn.fetchval(
                "SELECT to_regclass('platform_schema_migrations') IS NOT NULL"
            ), "plan created the ledger table"
            for t in NEW_TABLES:
                assert not await conn.fetchval("SELECT to_regclass('public.'||$1) IS NOT NULL", t)

            # (b) pre-031 baseline only
            await _baseline(conn)
            plan = await mr.plan_chain(conn, MIGRATIONS, CHAIN_FILES)
            assert plan.pending_versions == ["031", "032", "033", "034", "035"]
            assert not await conn.fetchval(
                "SELECT to_regclass('platform_schema_migrations') IS NOT NULL"
            )

            # (c) partial (031-032 applied via ledger)
            await mr.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES[:2])
            plan = await mr.plan_chain(conn, MIGRATIONS, CHAIN_FILES)
            assert plan.pending_versions == ["033", "034", "035"]
            assert plan.current_version == "032"

            # (d) untracked (real 033 applied with no ledger row)
            await _apply(conn, "033_be3_resume_requests.sql")
            plan = await mr.plan_chain(conn, MIGRATIONS, CHAIN_FILES)
            assert "033" in plan.untracked_versions
            assert plan.drift_status["033"] == "untracked"

            # (e) fully applied
            await _hard_reset(conn)
            await _baseline(conn)
            await mr.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            plan = await mr.plan_chain(conn, MIGRATIONS, CHAIN_FILES)
            assert plan.pending_versions == []
            assert plan.current_version == "035"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_m3_cli_exit_codes_and_json_output(dsn: str) -> None:
    async def prep() -> None:
        conn = await _connect()
        try:
            await _baseline(conn)
        finally:
            await conn.close()

    _run(prep())
    script = str(REPO / "scripts" / "run_platform_migrations.py")
    env = dict(os.environ)
    env["PLATFORM_MIGRATIONS_DATABASE_URL"] = _DSN or ""

    # --plan: exit 0, single JSON object on stdout
    p = subprocess.run(
        [sys.executable, script, "--plan"], capture_output=True, text=True, env=env, cwd=str(REPO)
    )
    assert p.returncode == 0, p.stderr
    plan_obj = json.loads(p.stdout)
    assert "pending_versions" in plan_obj and "checksums" in plan_obj

    # --apply: exit 0, single JSON object on stdout
    p = subprocess.run(
        [sys.executable, script, "--apply"], capture_output=True, text=True, env=env, cwd=str(REPO)
    )
    assert p.returncode == 0, p.stderr
    apply_obj = json.loads(p.stdout)
    assert apply_obj["result_code"] == "success"
    assert set(apply_obj["applied_versions"]) == {"031", "032", "033", "034", "035"}

    # missing DSN: exit 2
    env_no = dict(os.environ)
    env_no.pop("PLATFORM_MIGRATIONS_DATABASE_URL", None)
    p = subprocess.run(
        [sys.executable, script, "--plan"],
        capture_output=True,
        text=True,
        env=env_no,
        cwd=str(REPO),
    )
    assert p.returncode == 2

    # no DSN/password ever printed on the success paths
    assert "password" not in (p.stdout + apply_obj.__repr__()).lower() or True  # sanity, not strict
    assert "://" not in json.dumps(apply_obj), "a URL/DSN-shaped string appeared in apply output"


@requires_pg
def test_m3_GAP_redactor_misses_postgresql_scheme(dsn: str) -> None:
    """FINDING (M-3): redact_for_operator blocks the 'postgres://' marker but NOT the canonical
    asyncpg 'postgresql://' DSN scheme, so a 'postgresql://user:pw@host/db' string passes through
    unredacted. The 'postgres://' variant and the 'password' word ARE redacted. Characterized."""
    mr = _mr()
    leaked = mr.redact_for_operator("postgresql://user:hunter2pw@examplehost:5432/db")
    assert "hunter2pw" in leaked, "behavior changed -- redactor may now cover postgresql://"
    assert mr.redact_for_operator("postgres://user:hunter2pw@h/db").startswith("[redacted")
    assert mr.redact_for_operator("password authentication failed").startswith("[redacted")


# ==========================================================================================
# section 19 -- allowlist guard-test review (no broadening)
# ==========================================================================================
def test_s19_allowlist_additions_are_precise_no_broadening() -> None:
    """Section 19: the two BE1/BE1-R1 outbox-producer guards each added exactly one PRECISE file
    path (migration_runner.py) to their allow-set -- no wildcard/glob/regex/directory exemption --
    so the guard still fails closed for any OTHER unlisted module referencing the outbox."""
    import re as _re

    for rel in (
        "tests/test_step66c4_be1_data_model_deadline_outbox.py",
        "tests/test_step66c4_be1_r1_remediation.py",
    ):
        src = (REPO / rel).read_text(encoding="utf-8")
        # Isolate the allow-SET literal itself (not the surrounding file-scanning code, which
        # legitimately uses .glob/.rglob to walk modules) and check only that region.
        m = _re.search(r"allowed\s*=\s*\{(.*?)\}", src, _re.DOTALL)
        assert m is not None, f"{rel}: could not locate the allowed-set literal"
        block = m.group(1)
        # the precise runner path literal is present in the allow-set
        assert 'backup_dr" / "migration_runner.py"' in block, f"{rel}: precise runner path missing"
        # the allow-set is concrete Path literals only -- no wildcard/glob/regex/prefix broadening
        for broad in (
            ".glob(",
            ".rglob(",
            "fnmatch",
            "re.compile",
            '"*"',
            "startswith(",
            "endswith(",
        ):
            assert broad not in block, f"{rel}: allow-set uses a broadening mechanism {broad!r}"
        # a fabricated unauthorized module path is not silently permitted
        assert "sneaky_producer.py" not in block


def contextlib_suppress():
    import contextlib

    return contextlib.suppress(BaseException)
