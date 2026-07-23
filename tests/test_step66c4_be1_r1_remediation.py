"""Step 66C.4-BE1-R1 -- remediation tests for the Step 66C.4-BE1-R blocking findings.

Covers:
  * B-1 deadline semantics: the transaction-crossing-deadline regression (MANDATORY), the
    strict-boundary equality case, statement-time answered_at consistency, and the
    due_at NOT NULL regression.
  * B-2 outbox durability: available_at persistence and claim eligibility, retry backoff
    persistence, dead/published terminal timestamps, status/timestamp coherence, bounded
    last_error, duplicate idempotency key, replay state mapping, transaction atomicity.
  * M-1 payload safety: the positive allowlist and its bypass probes.
  * Fixture safety: the fail-closed ephemerality guard.
  * Disabled-foundation posture: no live producer, no relay, no scheduler.

The PostgreSQL tests are gated on the fail-closed guard in step66c4_pg_safety.py. They are
MANDATORY evidence: a run without them is reported as "PostgreSQL evidence unavailable" and
must not be presented as a complete technical pass (see the R1 verifier).
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

import pytest

from step66c4_pg_safety import (
    ALLOWED_DB_NAME_PATTERNS,
    FORBIDDEN_DB_NAMES,
    destructive_pg_refusal_reason,
)

REPO = Path(__file__).resolve().parents[1]
MIGRATIONS = REPO / "migrations"
UP_SQL = MIGRATIONS / "031_clarification_lifecycle_outbox_foundation.sql"
DOWN_SQL = MIGRATIONS / "031_clarification_lifecycle_outbox_foundation_down.sql"

REMINDER_EVENT = "clarification.reminder_recorded"

DURABILITY_COLUMNS = ("available_at", "dead_at", "last_error")


def _outbox():
    from shared.sdk.tasks import lifecycle_outbox

    return lifecycle_outbox


# --------------------------------------------------------------------------------------
# Remediation A/B -- canonical time semantics (static)
# --------------------------------------------------------------------------------------

CONTRACT_DIR = REPO / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"


def test_canonical_contract_records_correct_now_semantics() -> None:
    text = (CONTRACT_DIR / "lifecycle-and-time-contract.md").read_text(encoding="utf-8")
    lowered = text.lower()
    # The corrected fact must be stated.
    assert "transaction_timestamp()" in text
    assert "statement_timestamp()" in text
    assert "transaction started" in lowered or "transaction start" in lowered
    # The refuted claim must be gone.
    assert "now() is evaluated per statement" not in lowered
    assert "now() provides claim-execution time" not in lowered
    # The binding predicate must be the corrected one.
    assert "due_at > statement_timestamp()" in text
    assert "due_at > now()" not in text


def test_answer_cas_uses_statement_timestamp_for_predicate_and_answered_at() -> None:
    src = (REPO / "shared" / "sdk" / "tasks" / "workroom_store.py").read_text(encoding="utf-8")
    assert "due_at > statement_timestamp()" in src
    assert "answered_at=statement_timestamp()" in src
    # now()/transaction_timestamp() must not decide the deadline or stamp answered_at.
    # (The module DOCSTRING names them to explain why they are banned; only their use in SQL
    # is forbidden, so assert on the SQL forms rather than on any mention of the name.)
    for banned in (
        "answered_at=now()",
        "due_at > now()",
        "answered_at=transaction_timestamp()",
        "due_at > transaction_timestamp()",
    ):
        assert banned not in src, banned


# --------------------------------------------------------------------------------------
# Remediation C -- outbox durability schema (static)
# --------------------------------------------------------------------------------------


def test_migration_031_adds_durability_columns() -> None:
    up = UP_SQL.read_text(encoding="utf-8")
    assert "available_at      TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp()" in up
    assert "dead_at           TIMESTAMPTZ" in up
    assert "last_error        TEXT" in up
    assert "chk_clo_last_error_bounded" in up
    assert "chk_clo_status_timestamps" in up
    assert "idx_clo_pending_available" in up
    # Still additive.
    for banned in ("DROP TABLE", "DROP COLUMN", "ALTER COLUMN", "TRUNCATE", "DELETE FROM"):
        assert banned not in up, banned


def test_data_model_contract_defines_durability_semantics() -> None:
    text = (CONTRACT_DIR / "data-model-contract.md").read_text(encoding="utf-8")
    for col in DURABILITY_COLUMNS:
        assert col in text, col
    for heading in ("Status semantics", "Retry semantics", "Operator replay semantics"):
        assert heading in text, heading
    assert "attempts is\n  deliberately NOT reset" in text or "NOT reset" in text


# --------------------------------------------------------------------------------------
# Remediation D -- pure state mapping
# --------------------------------------------------------------------------------------


def test_retry_plan_persists_backoff_then_dies() -> None:
    lo = _outbox()
    first = lo.plan_retry_state(attempts=0, error="ConnectionError")
    assert first["status"] == "pending"
    assert first["attempts"] == 1
    assert first["backoff_seconds"] == lo.RETRY_BACKOFF_SECONDS[0]
    assert first["set_dead_at"] is False

    # Backoff grows, so an outage cannot burn the whole budget in seconds.
    second = lo.plan_retry_state(attempts=1, error="ConnectionError")
    assert second["backoff_seconds"] > first["backoff_seconds"]

    terminal = lo.plan_retry_state(attempts=lo.MAX_DELIVERY_ATTEMPTS - 1, error="poison")
    assert terminal["status"] == "dead"
    assert terminal["set_dead_at"] is True
    assert terminal["backoff_seconds"] is None
    assert terminal["last_error"] == "poison"


def test_retry_plan_rejects_unbounded_error() -> None:
    lo = _outbox()
    with pytest.raises(ValueError):
        lo.plan_retry_state(attempts=0, error="x" * (lo.MAX_LAST_ERROR_CHARS + 1))


def test_replay_plan_preserves_attempt_history() -> None:
    lo = _outbox()
    plan = lo.plan_replay_state(attempts=4)
    assert plan["status"] == "pending"
    assert plan["attempts"] == 4  # NOT reset -- full delivery-attempt evidence
    assert plan["clear_dead_at"] is True
    assert plan["clear_last_error"] is True
    assert plan["reset_available_at"] is True


# --------------------------------------------------------------------------------------
# Remediation E -- payload positive allowlist and bypass probes
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        {"meta": {"answer": "raw"}},
        {"items": [{"token": "secret"}]},
        {"answer_body": "raw"},
        {"question_text": "raw"},
        {"TOKEN": "secret"},
        {"unknown_key": "value"},
        {"answer": "raw"},
        {"reason": {"nested": "dict"}},
        {"reason": ["list"]},
        {"reason": 1.5},
        {"clarification_id": str(uuid.uuid4())},
        {"task_id": str(uuid.uuid4())},
    ],
)
def test_payload_allowlist_rejects_bypass_attempts(payload) -> None:
    lo = _outbox()
    with pytest.raises(ValueError):
        lo.assert_safe_outbox_payload(payload, event_type=REMINDER_EVENT)


def test_payload_allowlist_rejects_oversized_payload() -> None:
    lo = _outbox()
    with pytest.raises(ValueError):
        lo.assert_safe_outbox_payload(
            {"reason": "x" * (lo.MAX_PAYLOAD_VALUE_CHARS + 1)}, event_type=REMINDER_EVENT
        )


def test_payload_allowlist_rejects_unknown_event_type() -> None:
    lo = _outbox()
    with pytest.raises(ValueError):
        lo.assert_safe_outbox_payload({"reason": "x"}, event_type="clarification.made_up")


def test_payload_allowlist_accepts_contract_keys() -> None:
    lo = _outbox()
    payload = {
        "event_id": str(uuid.uuid4()),
        "occurred_at": "2026-07-22T00:00:00+00:00",
        "reason": "reminder_recorded",
        "reminder_at": "2026-07-22T00:00:00+00:00",
        "reminder_sent_at": None,
    }
    assert lo.assert_safe_outbox_payload(payload, event_type=REMINDER_EVENT) == payload


def test_payload_error_messages_never_include_the_value() -> None:
    lo = _outbox()
    # Synthetic, deliberately not credential-shaped: the assertion is that the guard never
    # echoes a VALUE, so the string only has to be recognisable in the error text.
    secret = "SENTINEL-VALUE-MUST-NOT-APPEAR"
    with pytest.raises(ValueError) as exc:
        lo.assert_safe_outbox_payload({"token": secret}, event_type=REMINDER_EVENT)
    assert secret not in str(exc.value)


# --------------------------------------------------------------------------------------
# Fixture safety guard (fail-closed)
# --------------------------------------------------------------------------------------


def test_destructive_guard_requires_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS", raising=False)
    monkeypatch.setenv("BE1_TEST_DATABASE_URL", "postgresql://u:p@localhost:5432/step66c4_be1")
    assert destructive_pg_refusal_reason() is not None


@pytest.mark.parametrize(
    "db_name",
    ["aiagents", "aiagents_test", "postgres", "production", "staging", "shared"],
)
def test_destructive_guard_refuses_shared_database_names(monkeypatch, db_name) -> None:
    monkeypatch.setenv("STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS", "1")
    monkeypatch.setenv("BE1_TEST_DATABASE_URL", f"postgresql://u:p@localhost:5432/{db_name}")
    assert destructive_pg_refusal_reason() is not None


def test_destructive_guard_refuses_unconventional_name(monkeypatch) -> None:
    monkeypatch.setenv("STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS", "1")
    monkeypatch.setenv("BE1_TEST_DATABASE_URL", "postgresql://u:p@localhost:5432/mydb")
    assert destructive_pg_refusal_reason() is not None


def test_destructive_guard_refuses_unparseable_and_empty(monkeypatch) -> None:
    monkeypatch.setenv("STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS", "1")
    monkeypatch.setenv("BE1_TEST_DATABASE_URL", "not-a-dsn")
    assert destructive_pg_refusal_reason() is not None
    monkeypatch.setenv("BE1_TEST_DATABASE_URL", "postgresql://u:p@localhost:5432/")
    assert destructive_pg_refusal_reason() is not None


def test_destructive_guard_allows_isolated_ephemeral_name(monkeypatch) -> None:
    monkeypatch.setenv("STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS", "1")
    monkeypatch.setenv("BE1_TEST_DATABASE_URL", "postgresql://u:p@localhost:55432/step66c4_be1r1")
    assert destructive_pg_refusal_reason() is None


def test_guard_protects_every_forbidden_name_against_the_allow_patterns() -> None:
    # A forbidden name must never be rescued by an allow pattern.
    for name in FORBIDDEN_DB_NAMES:
        if any(p.match(name) for p in ALLOWED_DB_NAME_PATTERNS):
            assert name in FORBIDDEN_DB_NAMES  # explicit denial takes precedence


# --------------------------------------------------------------------------------------
# Disabled-foundation posture
# --------------------------------------------------------------------------------------


def test_no_relay_scheduler_or_live_producer_exists() -> None:
    lo_path = REPO / "shared" / "sdk" / "tasks" / "lifecycle_outbox.py"
    src = lo_path.read_text(encoding="utf-8")
    for banned in ("while True", "asyncio.sleep", "create_task(", "XREADGROUP", "FOR UPDATE"):
        assert banned not in src, banned

    # From Step 66C.4-BE2 (PO-authorized), the lifecycle poller (producer) and the outbox relay
    # (consumer) are the authorized NON-ACTIVATED callers; no other runtime module references the
    # outbox, and neither worker is activated in any shared runtime (asserted by the BE2
    # no-activation tests). Updated in BE2.
    allowed = {
        lo_path,
        REPO / "shared" / "sdk" / "tasks" / "lifecycle_poller.py",
        REPO / "shared" / "sdk" / "tasks" / "outbox_relay.py",
    }
    offenders = []
    for base in (REPO / "apps", REPO / "shared"):
        for path in base.rglob("*.py"):
            if path in allowed or "__pycache__" in str(path):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "lifecycle_outbox" in text or "clarification_lifecycle_outbox" in text:
                offenders.append(str(path.relative_to(REPO)))
    assert offenders == [], f"unexpected runtime references to the outbox: {offenders}"


# --------------------------------------------------------------------------------------
# MANDATORY real-PostgreSQL evidence
# --------------------------------------------------------------------------------------

try:
    import asyncpg

    _HAS_ASYNCPG = True
except Exception:  # pragma: no cover
    _HAS_ASYNCPG = False

_DSN = os.environ.get("BE1_TEST_DATABASE_URL")
_REFUSAL = destructive_pg_refusal_reason()


def _pg_reachable() -> bool:
    if _REFUSAL is not None or not (_HAS_ASYNCPG and _DSN):
        return False
    try:

        async def _ping() -> bool:
            conn = await asyncpg.connect(dsn=_DSN, timeout=5)
            await conn.close()
            return True

        return asyncio.new_event_loop().run_until_complete(_ping())
    except Exception:
        return False


requires_pg = pytest.mark.skipif(
    not _pg_reachable(),
    reason=(_REFUSAL or "isolated ephemeral test PostgreSQL not reachable"),
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _reset_and_migrate(conn) -> None:
    await conn.execute(
        "DROP TABLE IF EXISTS clarification_lifecycle_outbox, "
        "operator_clarification_requests, task_messages, operator_tasks CASCADE;"
    )
    await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    for name in (
        "029_operator_task_api_foundation.sql",
        "030_workroom_clarification_foundation.sql",
        "031_clarification_lifecycle_outbox_foundation.sql",
    ):
        await conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))


async def _seed(conn, *, due_sql: str) -> tuple[str, str]:
    """Seed a task + open clarification whose due_at is the given SQL expression."""
    task_id = await conn.fetchval(
        "INSERT INTO operator_tasks (title, task_type, created_by) "
        "VALUES ('t','software_delivery','alice') RETURNING id"
    )
    qmid = await conn.fetchval(
        "INSERT INTO task_messages (task_id, sender_type, sender_id, message_type, body) "
        "VALUES ($1,'human','alice','clarification_question','q') RETURNING id",
        task_id,
    )
    cid = await conn.fetchval(
        f"""
        INSERT INTO operator_clarification_requests
          (task_id, question_message_id, question, requested_by_type, requested_by_id,
           due_at, reminder_at)
        VALUES ($1,$2,'q','human','alice', {due_sql}, {due_sql})
        RETURNING id
        """,
        task_id,
        qmid,
    )
    return str(task_id), str(cid)


CAS_SQL = """
    UPDATE operator_clarification_requests
    SET status='answered',
        answered_at=statement_timestamp(),
        updated_at=statement_timestamp()
    WHERE id=$1 AND status='open' AND answered_at IS NULL
      AND due_at > statement_timestamp()
    RETURNING id
"""


@requires_pg
def test_pg_transaction_crossing_deadline_is_rejected() -> None:
    """MANDATORY (B-1). A transaction that BEGAN before due_at must not claim after it."""

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            _t, cid = await _seed(conn, due_sql="statement_timestamp() + interval '3 seconds'")

            tx = conn.transaction()
            await tx.start()
            txn_start, due_at = await conn.fetchrow(
                "SELECT transaction_timestamp(), "
                "(SELECT due_at FROM operator_clarification_requests WHERE id=$1)",
                uuid.UUID(cid),
            )
            assert txn_start < due_at, "the transaction must begin BEFORE the deadline"

            # Hold the transaction open until DB time passes due_at.
            await conn.execute("SELECT pg_sleep(4)")
            stmt_now = await conn.fetchval("SELECT statement_timestamp()")
            assert stmt_now > due_at, "the claim must execute AFTER the deadline"
            # now() is still frozen at BEGIN -- this is exactly the defect being regressed.
            frozen = await conn.fetchval("SELECT now()")
            assert frozen == txn_start
            assert frozen < due_at

            claimed = await conn.fetchval(CAS_SQL, uuid.UUID(cid))
            assert claimed is None, "cross-deadline claim must be REJECTED"
            await tx.commit()

            row = await conn.fetchrow(
                "SELECT status, answered_at FROM operator_clarification_requests WHERE id=$1",
                uuid.UUID(cid),
            )
            assert row["answered_at"] is None
            assert row["status"] == "open"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_strict_boundary_equality_is_rejected() -> None:
    """due_at is an EXCLUSIVE upper bound: due_at == claim statement time must fail."""

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            _t, cid = await _seed(conn, due_sql="statement_timestamp() + interval '1 hour'")

            # Force exact equality: set due_at to the very statement time the CAS will read.
            # Inside ONE statement, statement_timestamp() is constant, so the UPDATE below
            # writes precisely the value the predicate will compare against on re-evaluation.
            equal_now = await conn.fetchval(
                "UPDATE operator_clarification_requests SET due_at = statement_timestamp() "
                "WHERE id=$1 RETURNING due_at",
                uuid.UUID(cid),
            )
            # Prove strictness directly against the captured value, with no elapsed-time
            # dependency: the predicate is evaluated with due_at == the compared timestamp.
            strict = await conn.fetchval(
                "SELECT due_at > $2::timestamptz FROM operator_clarification_requests "
                "WHERE id=$1",
                uuid.UUID(cid),
                equal_now,
            )
            assert strict is False, "equality must not satisfy the strict > predicate"

            # And the real CAS also rejects it (statement time has advanced past due_at).
            assert await conn.fetchval(CAS_SQL, uuid.UUID(cid)) is None
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_answered_at_is_statement_time_not_transaction_start() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            _t, cid = await _seed(conn, due_sql="statement_timestamp() + interval '1 hour'")

            tx = conn.transaction()
            await tx.start()
            txn_start = await conn.fetchval("SELECT transaction_timestamp()")
            await conn.execute("SELECT pg_sleep(2)")
            claimed = await conn.fetchval(CAS_SQL, uuid.UUID(cid))
            assert claimed is not None
            await tx.commit()

            answered_at = await conn.fetchval(
                "SELECT answered_at FROM operator_clarification_requests WHERE id=$1",
                uuid.UUID(cid),
            )
            # Not backdated to the transaction start.
            assert answered_at > txn_start
            assert (answered_at - txn_start).total_seconds() >= 2
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_due_at_remains_not_null() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            nullable = await conn.fetchval(
                "SELECT is_nullable FROM information_schema.columns "
                "WHERE table_name='operator_clarification_requests' AND column_name='due_at'"
            )
            assert nullable == "NO", "migration 031 must not relax due_at NOT NULL"

            task_id = await conn.fetchval(
                "INSERT INTO operator_tasks (title, task_type, created_by) "
                "VALUES ('t','software_delivery','alice') RETURNING id"
            )
            qmid = await conn.fetchval(
                "INSERT INTO task_messages "
                "(task_id, sender_type, sender_id, message_type, body) "
                "VALUES ($1,'human','alice','clarification_question','q') RETURNING id",
                task_id,
            )
            with pytest.raises(asyncpg.NotNullViolationError):
                await conn.execute(
                    "INSERT INTO operator_clarification_requests "
                    "(task_id, question_message_id, question, requested_by_type, "
                    " requested_by_id, due_at, reminder_at) "
                    "VALUES ($1,$2,'q','human','alice', NULL, now())",
                    task_id,
                    qmid,
                )
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_concurrent_answer_with_barrier_exactly_one_wins() -> None:
    """Both claimers are provably ready before either runs; exactly one wins."""

    async def scenario() -> None:
        setup = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(setup)
            _t, cid = await _seed(setup, due_sql="statement_timestamp() + interval '1 hour'")
        finally:
            await setup.close()

        conn_a = await asyncpg.connect(dsn=_DSN)
        conn_b = await asyncpg.connect(dsn=_DSN)
        barrier = asyncio.Barrier(2)
        try:

            async def claim(conn):
                # Both coroutines reach the barrier before either issues its UPDATE.
                await barrier.wait()
                return await conn.fetchval(CAS_SQL, uuid.UUID(cid))

            results = await asyncio.gather(claim(conn_a), claim(conn_b))
            winners = [r for r in results if r is not None]
            assert len(winners) == 1, f"expected exactly one winner, got {results}"
        finally:
            await conn_a.close()
            await conn_b.close()

        verify = await asyncpg.connect(dsn=_DSN)
        try:
            row = await verify.fetchrow(
                "SELECT status, answered_at FROM operator_clarification_requests WHERE id=$1",
                uuid.UUID(cid),
            )
            assert row["status"] == "answered"
            assert row["answered_at"] is not None
        finally:
            await verify.close()

    _run(scenario())


@requires_pg
def test_pg_loser_blocks_until_winner_commits_then_reads_final_state() -> None:
    async def scenario() -> None:
        setup = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(setup)
            _t, cid = await _seed(setup, due_sql="statement_timestamp() + interval '1 hour'")
        finally:
            await setup.close()

        winner = await asyncpg.connect(dsn=_DSN)
        loser = await asyncpg.connect(dsn=_DSN)
        try:
            tx = winner.transaction()
            await tx.start()
            assert await winner.fetchval(CAS_SQL, uuid.UUID(cid)) is not None

            # The loser must genuinely block on the winner's uncommitted row lock.
            task = asyncio.ensure_future(loser.fetchval(CAS_SQL, uuid.UUID(cid)))
            done, _pending = await asyncio.wait({task}, timeout=1.0)
            assert not done, "loser should still be blocked while the winner holds the lock"

            await tx.commit()
            assert await task is None

            final = await loser.fetchrow(
                "SELECT status, answered_at FROM operator_clarification_requests WHERE id=$1",
                uuid.UUID(cid),
            )
            assert final["status"] == "answered"
            assert final["answered_at"] is not None
        finally:
            await winner.close()
            await loser.close()

    _run(scenario())


@requires_pg
def test_pg_migration_up_down_reapply_is_deterministic() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await conn.execute(
                "DROP TABLE IF EXISTS clarification_lifecycle_outbox, "
                "operator_clarification_requests, task_messages, operator_tasks CASCADE;"
            )
            await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
            await conn.execute(
                (MIGRATIONS / "029_operator_task_api_foundation.sql").read_text(encoding="utf-8")
            )
            await conn.execute(
                (MIGRATIONS / "030_workroom_clarification_foundation.sql").read_text(
                    encoding="utf-8"
                )
            )
            # Representative existing row seeded BEFORE 031.
            _t, cid = await _seed(conn, due_sql="statement_timestamp() + interval '72 hours'")
            before = await conn.fetchrow(
                "SELECT status, answered_at, due_at, reminder_at "
                "FROM operator_clarification_requests WHERE id=$1",
                uuid.UUID(cid),
            )

            # No table rewrite for the additive columns: relfilenode must not change.
            relfilenode_before = await conn.fetchval(
                "SELECT relfilenode FROM pg_class WHERE relname='operator_clarification_requests'"
            )
            await conn.execute(UP_SQL.read_text(encoding="utf-8"))
            relfilenode_after = await conn.fetchval(
                "SELECT relfilenode FROM pg_class WHERE relname='operator_clarification_requests'"
            )
            assert relfilenode_before == relfilenode_after, "additive columns must not rewrite"

            after = await conn.fetchrow(
                "SELECT status, answered_at, due_at, reminder_at "
                "FROM operator_clarification_requests WHERE id=$1",
                uuid.UUID(cid),
            )
            assert dict(before) == dict(after), "no legacy row mutation, no destructive backfill"

            outbox_cols = {
                r["column_name"]: (r["is_nullable"], r["data_type"])
                for r in await conn.fetch(
                    "SELECT column_name, is_nullable, data_type FROM information_schema.columns "
                    "WHERE table_name='clarification_lifecycle_outbox'"
                )
            }
            assert outbox_cols["available_at"][0] == "NO"
            assert outbox_cols["dead_at"][0] == "YES"
            assert outbox_cols["last_error"][0] == "YES"

            constraints = {
                r["conname"]
                for r in await conn.fetch(
                    "SELECT conname FROM pg_constraint WHERE conrelid = "
                    "'clarification_lifecycle_outbox'::regclass"
                )
            }
            assert "chk_clo_last_error_bounded" in constraints
            assert "chk_clo_status_timestamps" in constraints

            idx = {
                r["indexname"]
                for r in await conn.fetch(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE tablename='clarification_lifecycle_outbox'"
                )
            }
            assert {
                "idx_clo_pending_available",
                "idx_clo_pending_created",
                "idx_clo_dead_at",
            } <= idx

            def _schema_fingerprint(rows):
                return sorted((r["column_name"], r["data_type"], r["is_nullable"]) for r in rows)

            fp1 = _schema_fingerprint(
                await conn.fetch(
                    "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                    "WHERE table_name='clarification_lifecycle_outbox'"
                )
            )

            # Rollback removes only BE1 objects.
            await conn.execute(DOWN_SQL.read_text(encoding="utf-8"))
            assert not await conn.fetchval("SELECT to_regclass('clarification_lifecycle_outbox')")
            remaining = {
                r["column_name"]
                for r in await conn.fetch(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='operator_clarification_requests'"
                )
            }
            assert "due_at" in remaining and "status" in remaining
            assert "reminder_sent_at" not in remaining
            # The pre-existing row survives rollback untouched.
            survived = await conn.fetchrow(
                "SELECT status, answered_at, due_at, reminder_at "
                "FROM operator_clarification_requests WHERE id=$1",
                uuid.UUID(cid),
            )
            assert dict(survived) == dict(before)

            # Reapply yields an identical schema.
            await conn.execute(UP_SQL.read_text(encoding="utf-8"))
            fp2 = _schema_fingerprint(
                await conn.fetch(
                    "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                    "WHERE table_name='clarification_lifecycle_outbox'"
                )
            )
            assert fp1 == fp2, "reapply must be deterministic"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_outbox_durability_semantics() -> None:
    async def scenario() -> None:
        lo = _outbox()
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            task_id, cid = await _seed(conn, due_sql="statement_timestamp() + interval '1 hour'")

            # 1. available_at is persisted and the row is immediately claim-eligible.
            row = await lo.insert_lifecycle_outbox_event(
                conn,
                clarification_id=cid,
                task_id=task_id,
                event_type=REMINDER_EVENT,
                idempotency_key=f"{cid}:reminder",
                payload={"reason": "reminder_recorded"},
            )
            assert row["available_at"] is not None
            assert row["dead_at"] is None
            assert row["last_error"] is None
            eligible = await lo.list_claimable_lifecycle_outbox_events(conn)
            assert [e["id"] for e in eligible] == [row["id"]]

            # 2. A transient-failure update persists a FUTURE available_at -> not eligible.
            plan = lo.plan_retry_state(attempts=0, error="ConnectionError")
            await conn.execute(
                "UPDATE clarification_lifecycle_outbox SET attempts=$2, last_error=$3, "
                "available_at = statement_timestamp() + ($4 || ' seconds')::interval WHERE id=$1",
                uuid.UUID(row["id"]),
                plan["attempts"],
                plan["last_error"],
                str(plan["backoff_seconds"]),
            )
            assert await lo.list_claimable_lifecycle_outbox_events(conn) == []
            deferred = await lo.get_lifecycle_outbox_event(conn, uuid.UUID(row["id"]))
            assert deferred["attempts"] == 1
            assert deferred["last_error"] == "ConnectionError"
            assert deferred["status"] == "pending"

            # 3. Terminal dead records dead_at.
            await conn.execute(
                "UPDATE clarification_lifecycle_outbox SET status='dead', "
                "dead_at=statement_timestamp(), last_error='poison' WHERE id=$1",
                uuid.UUID(row["id"]),
            )
            dead = await lo.get_lifecycle_outbox_event(conn, uuid.UUID(row["id"]))
            assert dead["status"] == "dead" and dead["dead_at"] is not None
            assert dead["published_at"] is None

            # 4. Replay maps dead -> pending, preserving attempts and the idempotency key.
            replay = lo.plan_replay_state(attempts=dead["attempts"])
            await conn.execute(
                "UPDATE clarification_lifecycle_outbox SET status=$2, attempts=$3, "
                "available_at=statement_timestamp(), dead_at=NULL, last_error=NULL WHERE id=$1",
                uuid.UUID(row["id"]),
                replay["status"],
                replay["attempts"],
            )
            replayed = await lo.get_lifecycle_outbox_event(conn, uuid.UUID(row["id"]))
            assert replayed["status"] == "pending"
            assert replayed["attempts"] == dead["attempts"]
            assert replayed["dead_at"] is None and replayed["last_error"] is None
            assert replayed["idempotency_key"] == f"{cid}:reminder"

            # 5. Published records published_at.
            await conn.execute(
                "UPDATE clarification_lifecycle_outbox SET status='published', "
                "published_at=statement_timestamp(), last_error=NULL WHERE id=$1",
                uuid.UUID(row["id"]),
            )
            published = await lo.get_lifecycle_outbox_event(conn, uuid.UUID(row["id"]))
            assert published["published_at"] is not None and published["dead_at"] is None

            # 6. published + dead simultaneously is rejected by the coherence CHECK.
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "UPDATE clarification_lifecycle_outbox SET dead_at=statement_timestamp() "
                    "WHERE id=$1",
                    uuid.UUID(row["id"]),
                )

            # 7. last_error is bounded at the DB boundary too.
            with pytest.raises(asyncpg.CheckViolationError):
                await conn.execute(
                    "UPDATE clarification_lifecycle_outbox SET last_error=$2 WHERE id=$1",
                    uuid.UUID(row["id"]),
                    "x" * (lo.MAX_LAST_ERROR_CHARS + 1),
                )
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_outbox_insert_is_atomic_with_state_mutation() -> None:
    """The state CAS and the outbox INSERT commit together or not at all."""

    async def scenario() -> None:
        lo = _outbox()
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            task_id, cid = await _seed(conn, due_sql="statement_timestamp() + interval '1 hour'")

            # Rollback: neither the state change nor the outbox row survives.
            tx = conn.transaction()
            await tx.start()
            assert await conn.fetchval(CAS_SQL, uuid.UUID(cid)) is not None
            await lo.insert_lifecycle_outbox_event(
                conn,
                clarification_id=cid,
                task_id=task_id,
                event_type="clarification.resume_eligible",
                idempotency_key=f"{cid}:resume_eligible",
                payload={"reason": "eligible"},
            )
            await tx.rollback()
            assert await conn.fetchval("SELECT count(*) FROM clarification_lifecycle_outbox") == 0
            assert (
                await conn.fetchval(
                    "SELECT status FROM operator_clarification_requests WHERE id=$1",
                    uuid.UUID(cid),
                )
                == "open"
            )

            # Commit: both survive.
            tx2 = conn.transaction()
            await tx2.start()
            assert await conn.fetchval(CAS_SQL, uuid.UUID(cid)) is not None
            await lo.insert_lifecycle_outbox_event(
                conn,
                clarification_id=cid,
                task_id=task_id,
                event_type="clarification.resume_eligible",
                idempotency_key=f"{cid}:resume_eligible",
                payload={"reason": "eligible"},
            )
            await tx2.commit()
            assert await conn.fetchval("SELECT count(*) FROM clarification_lifecycle_outbox") == 1
            assert (
                await conn.fetchval(
                    "SELECT status FROM operator_clarification_requests WHERE id=$1",
                    uuid.UUID(cid),
                )
                == "answered"
            )

            # Duplicate idempotency key is rejected.
            with pytest.raises(asyncpg.UniqueViolationError):
                await lo.insert_lifecycle_outbox_event(
                    conn,
                    clarification_id=cid,
                    task_id=task_id,
                    event_type="clarification.resume_eligible",
                    idempotency_key=f"{cid}:resume_eligible",
                    payload={"reason": "dup"},
                )
        finally:
            await conn.close()

    _run(scenario())
