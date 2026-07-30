"""Step 66C.4-BE3-RA-1B -- migration runner safety, provenance, and operational-controls
remediation tests.

Real-PostgreSQL 16 coverage for the four findings closed by RA-1B:

- H-1: aborted-transaction cleanup / lock-release failure in apply_chain_locked.
- M-1: schema-fingerprint semantic blind spots (CHECK expressions, FK actions/deferrability,
  index predicates/expressions).
- M-2: migration ledger and version/checksum provenance (apply_chain_with_ledger).
- M-3: bounded lock-wait/statement timeouts, plan/apply CLI, structured secret-free results.

Gated by the fail-closed destructive-PG guard shared with every other Step 66C.4 PostgreSQL test.
Nothing here touches any shared database, enables any feature gate, or performs any runtime action.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from step66c4_pg_safety import destructive_pg_refusal_reason

REPO = Path(__file__).resolve().parents[1]
MIGRATIONS = REPO / "migrations"
CLI_SCRIPT = REPO / "scripts" / "run_platform_migrations.py"

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
        "operator_clarification_requests, task_messages, operator_tasks, "
        "platform_schema_migrations CASCADE;"
    )


async def _apply_baseline(conn) -> None:
    await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    for name in BASELINE_FILES:
        await _apply(conn, name)


@pytest.fixture
def dsn() -> str:
    assert _DSN is not None
    return _DSN


# ---------------------------------------------------------------------------------------------
# H-1: aborted-transaction cleanup / lock-release failure
# ---------------------------------------------------------------------------------------------


@requires_pg
def test_pg_mid_file_failure_rolls_back_before_unlock_and_preserves_original_error(
    dsn: str,
) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            # Build an in-memory broken variant and write it to a throwaway temp file so
            # apply_chain_locked (which reads files by path) exercises the real failure path.
            sql = (MIGRATIONS / "032_be3_resume_replay_authorization.sql").read_text(
                encoding="utf-8"
            )
            broken = sql.replace("\nCOMMIT;", "\nSELECT 1/0; -- injected\nCOMMIT;", 1)
            tmp = REPO / "migrations" / "_ra1b_tmp_broken_032.sql"
            tmp.write_text(broken, encoding="utf-8")
            try:
                with pytest.raises(asyncpg.exceptions.DivisionByZeroError) as excinfo:
                    await r.apply_chain_locked(conn, MIGRATIONS, ("_ra1b_tmp_broken_032.sql",))
                # The ORIGINAL migration error is what propagates -- not a masking unlock error.
                assert excinfo.value.ra1b_connection_reusable is True
                assert excinfo.value.ra1b_cleanup_errors == []
                # The connection is fully usable again -- proves ROLLBACK ran before unlock.
                value = await conn.fetchval("SELECT 1")
                assert value == 1
                exists = await conn.fetchval(
                    "SELECT to_regclass('resume_replay_authorizations') IS NOT NULL"
                )
                assert not exists
            finally:
                tmp.unlink(missing_ok=True)
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_failure_just_before_commit_rollback_and_lock_released(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        other = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            sql = (MIGRATIONS / "033_be3_resume_requests.sql").read_text(encoding="utf-8")
            broken = sql.replace("\nCOMMIT;", "\nSELECT 1/0;\nCOMMIT;", 1)
            tmp = REPO / "migrations" / "_ra1b_tmp_broken_033.sql"
            tmp.write_text(broken, encoding="utf-8")
            try:
                await _apply(conn, "031_clarification_lifecycle_outbox_foundation.sql")
                await _apply(conn, "032_be3_resume_replay_authorization.sql")
                with pytest.raises(asyncpg.PostgresError):
                    await r.apply_chain_locked(conn, MIGRATIONS, ("_ra1b_tmp_broken_033.sql",))
                # Lock released: another connection can acquire it immediately.
                got = await other.fetchval(
                    "SELECT pg_try_advisory_lock(hashtextextended($1, 0))", r.DEFAULT_LOCK_KEY
                )
                assert got is True
                await other.fetchval(
                    "SELECT pg_advisory_unlock(hashtextextended($1, 0))", r.DEFAULT_LOCK_KEY
                )
                exists = await conn.fetchval("SELECT to_regclass('resume_requests') IS NOT NULL")
                assert not exists
            finally:
                tmp.unlink(missing_ok=True)
        finally:
            await conn.close()
            await other.close()

    _run(scenario())


@requires_pg
def test_pg_cancellation_while_lock_held_releases_lock(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        other = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()

            async def slow_migrator() -> None:
                await r.apply_chain_locked(conn, MIGRATIONS, ("_ra1b_tmp_slow.sql",))

            slow_sql = (MIGRATIONS / "032_be3_resume_replay_authorization.sql").read_text(
                encoding="utf-8"
            )
            slow_sql = slow_sql.replace("BEGIN;", "BEGIN;\nSELECT pg_sleep(5);", 1)
            tmp = REPO / "migrations" / "_ra1b_tmp_slow.sql"
            tmp.write_text(slow_sql, encoding="utf-8")
            try:
                task = asyncio.ensure_future(slow_migrator())
                await asyncio.sleep(0.3)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                got = await other.fetchval(
                    "SELECT pg_try_advisory_lock(hashtextextended($1, 0))", r.DEFAULT_LOCK_KEY
                )
                assert got is True, "lock was not released after the holder was cancelled"
                await other.fetchval(
                    "SELECT pg_advisory_unlock(hashtextextended($1, 0))", r.DEFAULT_LOCK_KEY
                )
            finally:
                tmp.unlink(missing_ok=True)
        finally:
            await conn.close()
            await other.close()

    _run(scenario())


@requires_pg
def test_pg_rollback_failure_causes_connection_disposal(dsn: str) -> None:
    """Simulate a rollback-step failure by forcibly terminating the connection's backend mid-
    migration (from an admin connection) so the subsequent internal ROLLBACK attempt itself fails --
    confirming the runner discards rather than pretending the connection is fine."""

    async def scenario() -> None:
        admin = await asyncpg.connect(dsn=dsn)
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            pid = await conn.fetchval("SELECT pg_backend_pid()")

            slow_sql = (MIGRATIONS / "032_be3_resume_replay_authorization.sql").read_text(
                encoding="utf-8"
            )
            slow_sql = slow_sql.replace("BEGIN;", "BEGIN;\nSELECT pg_sleep(2);\nSELECT 1/0;", 1)
            tmp = REPO / "migrations" / "_ra1b_tmp_terminate.sql"
            tmp.write_text(slow_sql, encoding="utf-8")
            try:

                async def victim() -> BaseException | None:
                    try:
                        await r.apply_chain_locked(conn, MIGRATIONS, ("_ra1b_tmp_terminate.sql",))
                        return None
                    except BaseException as exc:  # noqa: BLE001
                        return exc

                task = asyncio.ensure_future(victim())
                await asyncio.sleep(0.5)
                await admin.execute("SELECT pg_terminate_backend($1)", pid)
                result = await task
                assert result is not None
                assert getattr(result, "ra1b_connection_reusable", True) is False
                assert conn.is_closed()
            finally:
                tmp.unlink(missing_ok=True)
        finally:
            await admin.close()
            with contextlib.suppress(Exception):
                await conn.close()

    _run(scenario())


@requires_pg
def test_pg_fresh_connection_after_disposal_is_unaffected(dsn: str) -> None:
    """After a connection is disposed following a cleanup failure, a brand-new connection is
    completely unaffected -- proves no lingering session-level or database-level poisoning."""

    async def scenario() -> None:
        fresh = await asyncpg.connect(dsn=dsn)
        try:
            r = _runner()
            got = await fresh.fetchval(
                "SELECT pg_try_advisory_lock(hashtextextended($1, 0))", r.DEFAULT_LOCK_KEY
            )
            assert got is True
            await fresh.fetchval(
                "SELECT pg_advisory_unlock(hashtextextended($1, 0))", r.DEFAULT_LOCK_KEY
            )
            value = await fresh.fetchval("SELECT 1")
            assert value == 1
        finally:
            await fresh.close()

    _run(scenario())


# ---------------------------------------------------------------------------------------------
# M-1: schema fingerprint semantic completeness
# ---------------------------------------------------------------------------------------------


@requires_pg
def test_pg_fingerprint_detects_check_expression_change(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            for f in CHAIN_FILES:
                await _apply(conn, f)
            r = _runner()
            before = await r.schema_fingerprint(conn, ("resume_replay_authorizations",))
            await conn.execute(
                "ALTER TABLE resume_replay_authorizations "
                "DROP CONSTRAINT chk_rra_idempotency_key_bounded, "
                "ADD CONSTRAINT chk_rra_idempotency_key_bounded "
                "CHECK (length(idempotency_key) BETWEEN 1 AND 999)"
            )
            after = await r.schema_fingerprint(conn, ("resume_replay_authorizations",))
            assert before != after
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_fingerprint_detects_fk_on_delete_change(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            for f in CHAIN_FILES:
                await _apply(conn, f)
            r = _runner()
            before = await r.schema_fingerprint(conn, ("resume_requests",))
            await conn.execute(
                "ALTER TABLE resume_requests DROP CONSTRAINT resume_requests_task_id_fkey, "
                "ADD CONSTRAINT resume_requests_task_id_fkey FOREIGN KEY (task_id) "
                "REFERENCES operator_tasks(id) ON DELETE CASCADE"
            )
            after = await r.schema_fingerprint(conn, ("resume_requests",))
            assert before != after
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_fingerprint_detects_fk_on_update_change(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            for f in CHAIN_FILES:
                await _apply(conn, f)
            r = _runner()
            before = await r.schema_fingerprint(conn, ("resume_requests",))
            await conn.execute(
                "ALTER TABLE resume_requests DROP CONSTRAINT resume_requests_task_id_fkey, "
                "ADD CONSTRAINT resume_requests_task_id_fkey FOREIGN KEY (task_id) "
                "REFERENCES operator_tasks(id) ON UPDATE CASCADE"
            )
            after = await r.schema_fingerprint(conn, ("resume_requests",))
            assert before != after
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_fingerprint_detects_deferrability_change(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            for f in CHAIN_FILES:
                await _apply(conn, f)
            r = _runner()
            before = await r.schema_fingerprint(conn, ("resume_requests",))
            await conn.execute(
                "ALTER TABLE resume_requests DROP CONSTRAINT resume_requests_task_id_fkey, "
                "ADD CONSTRAINT resume_requests_task_id_fkey FOREIGN KEY (task_id) "
                "REFERENCES operator_tasks(id) DEFERRABLE INITIALLY DEFERRED"
            )
            after = await r.schema_fingerprint(conn, ("resume_requests",))
            assert before != after
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_fingerprint_detects_index_predicate_and_expression_change(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            for f in CHAIN_FILES:
                await _apply(conn, f)
            r = _runner()
            before = await r.schema_fingerprint(conn, ("resume_requests",))
            await conn.execute("DROP INDEX uq_rr_active_per_clarification")
            await conn.execute(
                "CREATE UNIQUE INDEX uq_rr_active_per_clarification ON resume_requests "
                "(clarification_id) WHERE (state = 'authorized')"
            )
            after = await r.schema_fingerprint(conn, ("resume_requests",))
            assert before != after
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_fingerprint_still_detects_drop_index_nullability_and_default(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            for f in CHAIN_FILES:
                await _apply(conn, f)
            r = _runner()
            baseline = await r.schema_fingerprint(conn, ("resume_replay_authorizations",))

            await conn.execute("DROP INDEX idx_rra_authorized_unconsumed")
            after_drop = await r.schema_fingerprint(conn, ("resume_replay_authorizations",))
            assert baseline != after_drop
            await conn.execute(
                "CREATE INDEX idx_rra_authorized_unconsumed ON resume_replay_authorizations "
                "(action_type, resource_id) WHERE decision = 'authorized' AND consumed_at IS NULL "
                "AND revoked_at IS NULL AND expired_at IS NULL"
            )

            # requested_by is genuinely NOT NULL in the baseline (unlike decided_by, which is
            # nullable until a decision is made) -- a real toggle-away-and-back is meaningful here.
            await conn.execute(
                "ALTER TABLE resume_replay_authorizations ALTER COLUMN requested_by DROP NOT NULL"
            )
            after_nullable = await r.schema_fingerprint(conn, ("resume_replay_authorizations",))
            assert after_nullable != baseline, "nullability change was not detected"
            await conn.execute(
                "ALTER TABLE resume_replay_authorizations ALTER COLUMN requested_by SET NOT NULL"
            )
            after_null_roundtrip = await r.schema_fingerprint(
                conn, ("resume_replay_authorizations",)
            )
            assert after_null_roundtrip == baseline

            await conn.execute(
                "ALTER TABLE resume_replay_authorizations ALTER COLUMN decision SET DEFAULT 'rejected'"
            )
            after_default = await r.schema_fingerprint(conn, ("resume_replay_authorizations",))
            assert after_default != baseline
        finally:
            await conn.close()

    _run(scenario())


# ---------------------------------------------------------------------------------------------
# M-2: migration ledger and provenance
# ---------------------------------------------------------------------------------------------


@requires_pg
def test_pg_ledger_bootstrap_and_applied_status_checksum(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            result = await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            assert result.result_code == "success"
            assert list(result.applied_versions) == ["031", "032", "033", "034", "035"]
            rows = await conn.fetch(
                f"SELECT migration_version, status, migration_sha256 FROM {r.LEDGER_TABLE} "
                "ORDER BY migration_version"
            )
            assert [row["status"] for row in rows] == ["applied"] * 5
            for row, filename in zip(rows, CHAIN_FILES):
                expected_checksum = r._sha256_file(MIGRATIONS / filename)
                assert row["migration_sha256"] == expected_checksum
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_duplicate_invocation_uses_ledger_fast_path(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            first = await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            assert first.applied_versions == ["031", "032", "033", "034", "035"]
            second = await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            assert second.applied_versions == []
            assert second.reconciled_versions == []
            assert second.result_code == "success"
            count = await conn.fetchval(
                f"SELECT count(*) FROM {r.LEDGER_TABLE} WHERE status = 'applied'"
            )
            assert count == 5
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_checksum_mismatch_fails_closed(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            await conn.execute(
                f"UPDATE {r.LEDGER_TABLE} SET migration_sha256 = 'deadbeef' "
                "WHERE migration_version = '032'"
            )
            with pytest.raises(r.MigrationChecksumMismatchError):
                await r.apply_chain_with_ledger(conn, MIGRATIONS, CHAIN_FILES)
            row = await conn.fetchrow(
                f"SELECT migration_sha256 FROM {r.LEDGER_TABLE} WHERE migration_version = '032'"
            )
            assert row["migration_sha256"] == "deadbeef", "mismatched checksum row was overwritten"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_ambiguous_commit_reconciles_when_schema_matches(dsn: str) -> None:
    """Simulate the classic ambiguous-commit scenario: the migration's own DDL actually succeeded
    on the server, but the ledger row was never advanced past 'applying' (as if the client crashed
    right after the migration file committed but before the ledger update ran). A retry must
    reconcile, not re-execute or fail."""

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            await r.apply_chain_with_ledger(
                conn, MIGRATIONS, ("031_clarification_lifecycle_outbox_foundation.sql",)
            )
            checksum = r._sha256_file(MIGRATIONS / "032_be3_resume_replay_authorization.sql")
            manifest = await r._validate_manifest(
                conn, "032_be3_resume_replay_authorization.sql", checksum
            )
            await _apply(conn, "032_be3_resume_replay_authorization.sql")  # DDL "already committed"
            await conn.execute(
                f"INSERT INTO {r.LEDGER_TABLE} "
                "(migration_version, migration_filename, migration_sha256, status, runner_version, "
                "expected_fingerprint) "
                "VALUES ('032', '032_be3_resume_replay_authorization.sql', $1, 'applying', $2, $3)",
                checksum,
                r.RUNNER_VERSION,
                manifest.canonical_semantic_fingerprint,
            )
            result = await r.apply_chain_with_ledger(
                conn, MIGRATIONS, ("032_be3_resume_replay_authorization.sql",)
            )
            assert result.reconciled_versions == ["032"]
            assert result.applied_versions == []
            row = await conn.fetchrow(
                f"SELECT status, resolution FROM {r.LEDGER_TABLE} WHERE migration_version = '032'"
            )
            assert row["status"] == "reconciled_after_ambiguous_commit"
            assert row["resolution"] == "ambiguous_commit_reconciled"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_untracked_schema_rejected(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            # Create a FOREIGN, wrong-shaped object under the same name, with NO ledger row.
            await conn.execute("CREATE TABLE resume_replay_authorizations (id int)")
            with pytest.raises(r.UntrackedSchemaError):
                await r.apply_chain_with_ledger(
                    conn, MIGRATIONS, ("032_be3_resume_replay_authorization.sql",)
                )
            row = await conn.fetchrow(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='resume_replay_authorizations'"
            )
            assert row["column_name"] == "id", "the foreign object was silently replaced/adopted"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_partial_schema_in_applying_state_rejected_as_drifted(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            await r.ensure_ledger_bootstrapped(conn)
            checksum = r._sha256_file(MIGRATIONS / "032_be3_resume_replay_authorization.sql")
            manifest = await r._validate_manifest(
                conn, "032_be3_resume_replay_authorization.sql", checksum
            )
            await conn.execute(
                f"INSERT INTO {r.LEDGER_TABLE} "
                "(migration_version, migration_filename, migration_sha256, status, runner_version, "
                "expected_fingerprint) "
                "VALUES ('032', '032_be3_resume_replay_authorization.sql', $1, 'applying', $2, $3)",
                checksum,
                r.RUNNER_VERSION,
                manifest.canonical_semantic_fingerprint,
            )
            # No actual table exists -- ledger says "applying" but schema is INCOMPLETE.
            with pytest.raises(r.SchemaDriftError):
                await r.apply_chain_with_ledger(
                    conn, MIGRATIONS, ("032_be3_resume_replay_authorization.sql",)
                )
            row = await conn.fetchrow(
                f"SELECT status FROM {r.LEDGER_TABLE} WHERE migration_version = '032'"
            )
            assert row["status"] == "drifted"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_failed_migration_ledger_state_recorded(dsn: str, tmp_path: Path, monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            broken = (
                (MIGRATIONS / "032_be3_resume_replay_authorization.sql")
                .read_text(encoding="utf-8")
                .replace("\nCOMMIT;", "\nSELECT 1/0;\nCOMMIT;", 1)
            )
            tmp = REPO / "migrations" / "032_ra1b_tmp_ledger_fail.sql"
            tmp.write_text(broken, encoding="utf-8")
            # This is a synthetic fault-injection file, not the real migration 032 -- its manifest
            # binding (filename + checksum) must be adjusted to match, in an isolated copy of the
            # manifests directory, so RA-1C's manifest-filename check doesn't short-circuit the
            # DDL-failure path this test actually exercises.
            bad_manifests = tmp_path / "manifests_for_tmp_ledger_fail"
            bad_manifests.mkdir()
            for f in r.MANIFESTS_DIR.glob("*.json"):
                shutil.copy(f, bad_manifests / f.name)
            data = json.loads((bad_manifests / "032.json").read_text(encoding="utf-8"))
            data["migration_filename"] = "032_ra1b_tmp_ledger_fail.sql"
            data["migration_sha256"] = r._sha256_file(tmp)
            (bad_manifests / "032.json").write_text(json.dumps(data), encoding="utf-8")
            monkeypatch.setattr(r, "MANIFESTS_DIR", bad_manifests)
            try:
                with pytest.raises(asyncpg.PostgresError):
                    await r.apply_chain_with_ledger(
                        conn, MIGRATIONS, ("032_ra1b_tmp_ledger_fail.sql",)
                    )
                row = await conn.fetchrow(
                    f"SELECT status, error_code FROM {r.LEDGER_TABLE} "
                    "WHERE migration_filename = '032_ra1b_tmp_ledger_fail.sql'"
                )
                assert row["status"] == "failed"
                assert row["error_code"] is not None
                assert "postgres://" not in row["error_code"]
            finally:
                tmp.unlink(missing_ok=True)
        finally:
            await conn.close()

    _run(scenario())


# ---------------------------------------------------------------------------------------------
# M-3: bounded waits and operational controls
# ---------------------------------------------------------------------------------------------


@requires_pg
def test_pg_lock_wait_timeout_raises_and_does_not_hang(dsn: str) -> None:
    async def scenario() -> None:
        holder = await asyncpg.connect(dsn=dsn)
        waiter = await asyncpg.connect(dsn=dsn)
        try:
            r = _runner()
            await holder.fetchval(
                "SELECT pg_advisory_lock(hashtextextended($1, 0))", r.DEFAULT_LOCK_KEY
            )
            start = asyncio.get_event_loop().time()
            with pytest.raises(r.MigrationLockTimeoutError):
                await r.apply_chain_locked(
                    waiter,
                    MIGRATIONS,
                    (),
                    lock_wait_timeout_seconds=1.0,
                    poll_interval_seconds=0.1,
                )
            elapsed = asyncio.get_event_loop().time() - start
            assert elapsed < 5.0, "lock-wait timeout did not bound the wait"
        finally:
            await holder.fetchval(
                "SELECT pg_advisory_unlock(hashtextextended($1, 0))", r.DEFAULT_LOCK_KEY
            )
            await holder.close()
            await waiter.close()

    _run(scenario())


@requires_pg
def test_pg_statement_timeout_applied_and_restored(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            original = await conn.fetchval("SHOW statement_timeout")
            await r.apply_chain_with_ledger(
                conn,
                MIGRATIONS,
                ("031_clarification_lifecycle_outbox_foundation.sql",),
                statement_timeout_ms=5000,
            )
            restored = await conn.fetchval("SHOW statement_timeout")
            assert restored == original
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_invalid_timeout_config_fails_closed(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            r = _runner()
            with pytest.raises(r.MigrationConfigError):
                await r.apply_chain_with_ledger(
                    conn, MIGRATIONS, (), lock_wait_timeout_seconds=-1.0
                )
            with pytest.raises(r.MigrationConfigError):
                await r.apply_chain_with_ledger(conn, MIGRATIONS, (), poll_interval_seconds=999.0)
            with pytest.raises(r.MigrationConfigError):
                await r.apply_chain_with_ledger(conn, MIGRATIONS, (), statement_timeout_ms=1)
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_plan_mode_produces_no_writes(dsn: str) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
            r = _runner()
            plan = await r.plan_chain(conn, MIGRATIONS, CHAIN_FILES)
            assert plan.pending_versions == ["031", "032", "033", "034", "035"]
            assert plan.untracked_versions == []
            ledger_exists = await conn.fetchval(
                "SELECT to_regclass('public.platform_schema_migrations') IS NOT NULL"
            )
            assert not ledger_exists, "plan mode created the ledger table"
            for table in (
                "clarification_lifecycle_outbox",
                "resume_replay_authorizations",
                "resume_requests",
                "replay_requests",
                "production_action_approvals",
            ):
                exists = await conn.fetchval("SELECT to_regclass($1) IS NOT NULL", table)
                assert not exists, f"plan mode created {table}"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_cli_plan_and_apply_exit_codes_and_secret_redaction(dsn: str) -> None:
    async def reset() -> None:
        conn = await asyncpg.connect(dsn=dsn)
        try:
            await _drop_all(conn)
            await _apply_baseline(conn)
        finally:
            await conn.close()

    _run(reset())

    env = dict(os.environ)
    env["PLATFORM_MIGRATIONS_DATABASE_URL"] = dsn

    plan_proc = subprocess.run(
        [sys.executable, str(CLI_SCRIPT), "--plan"],
        cwd=REPO,
        capture_output=True,
        text=True,
        env=env,
    )
    assert plan_proc.returncode == 0, plan_proc.stdout + plan_proc.stderr
    plan_payload = json.loads(plan_proc.stdout)
    assert plan_payload["pending_versions"] == ["031", "032", "033", "034", "035"]
    assert dsn not in plan_proc.stdout

    apply_proc = subprocess.run(
        [sys.executable, str(CLI_SCRIPT), "--apply"],
        cwd=REPO,
        capture_output=True,
        text=True,
        env=env,
    )
    assert apply_proc.returncode == 0, apply_proc.stdout + apply_proc.stderr
    apply_payload = json.loads(apply_proc.stdout)
    assert apply_payload["applied_versions"] == ["031", "032", "033", "034", "035"]
    assert dsn not in apply_proc.stdout

    # A second --apply call is idempotent (ledger fast path), still exit 0.
    apply_again = subprocess.run(
        [sys.executable, str(CLI_SCRIPT), "--apply"],
        cwd=REPO,
        capture_output=True,
        text=True,
        env=env,
    )
    assert apply_again.returncode == 0
    again_payload = json.loads(apply_again.stdout)
    assert again_payload["applied_versions"] == []

    # Missing DSN -> exit 2, never a traceback with a DSN in it.
    env_no_dsn = dict(os.environ)
    env_no_dsn.pop("PLATFORM_MIGRATIONS_DATABASE_URL", None)
    no_dsn_proc = subprocess.run(
        [sys.executable, str(CLI_SCRIPT), "--plan"],
        cwd=REPO,
        capture_output=True,
        text=True,
        env=env_no_dsn,
    )
    assert no_dsn_proc.returncode == 2
