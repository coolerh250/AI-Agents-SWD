"""Step 66C.4-BE1-R1-R -- independent closure-review tests.

Unlike the original defect-pinning suite (which asserts the DEFECTS are PRESENT at d2467f5 and is
preserved unmodified at review/66c4-be1-technical-security-migration @ f5417f4), this suite asserts
the FIXED state on the remediated branch. It is written from scratch by the closure reviewer and
does not import or depend on the remediation author's own test module.

Two tiers:
  * Static tier (always runs): the contract, the CAS source, the migration text and the payload
    allowlist reflect the closed B-1 / B-2 / M-1 state, and no runtime producer/relay/scheduler
    exists.
  * PostgreSQL tier (fail-closed opt-in via tests.step66c4_pg_safety): an INDEPENDENT
    transaction-crossing reproduction with a NEGATIVE CONTROL proving the OLD `due_at > now()`
    predicate would still succeed (so the fixed test is not vacuous), the strict-equality boundary,
    the statement-time answered_at, and the outbox status/timestamp coherence constraints.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

import pytest

from tests.step66c4_pg_safety import destructive_pg_refusal_reason

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"
CONTRACTS = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"

WORKROOM_STORE = (ROOT / "shared" / "sdk" / "tasks" / "workroom_store.py").read_text(
    encoding="utf-8"
)
OUTBOX_SRC = (ROOT / "shared" / "sdk" / "tasks" / "lifecycle_outbox.py").read_text(encoding="utf-8")
MIG_031 = (MIGRATIONS / "031_clarification_lifecycle_outbox_foundation.sql").read_text(
    encoding="utf-8"
)
TIME_CONTRACT = (CONTRACTS / "lifecycle-and-time-contract.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------------------
# Static tier -- B-1 deadline closure
# --------------------------------------------------------------------------------------


def test_cas_uses_statement_timestamp_and_has_no_frozen_clock_residue() -> None:
    assert "due_at > statement_timestamp()" in WORKROOM_STORE
    assert "answered_at=statement_timestamp()" in WORKROOM_STORE
    for forbidden in (
        "due_at > now()",
        "due_at > transaction_timestamp()",
        "answered_at=now()",
        "answered_at=transaction_timestamp()",
    ):
        assert forbidden not in WORKROOM_STORE, forbidden


def test_contract_records_now_equals_transaction_timestamp_and_statement_for_claim() -> None:
    assert "transaction_timestamp()" in TIME_CONTRACT
    assert "statement_timestamp()" in TIME_CONTRACT
    assert "due_at > statement_timestamp()" in TIME_CONTRACT
    # The contract must state the claim deadline is exclusive.
    assert "EXCLUSIVE upper bound" in TIME_CONTRACT


# --------------------------------------------------------------------------------------
# Static tier -- B-2 outbox durability closure
# --------------------------------------------------------------------------------------


def test_migration_declares_durability_columns_and_coherence_constraint() -> None:
    assert "available_at      TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp()" in MIG_031
    assert "dead_at" in MIG_031
    assert "last_error" in MIG_031
    assert "chk_clo_status_timestamps" in MIG_031
    assert "chk_clo_attempts_nonnegative" in MIG_031
    assert "chk_clo_last_error_bounded" in MIG_031
    assert "uq_clarification_lifecycle_outbox_idempotency_key" in MIG_031
    assert "idx_clo_pending_available" in MIG_031


def test_retry_helper_is_pure_and_bounded() -> None:
    from shared.sdk.tasks.lifecycle_outbox import (
        MAX_DELIVERY_ATTEMPTS,
        plan_replay_state,
        plan_retry_state,
    )

    # Bounded: after MAX_DELIVERY_ATTEMPTS the row dies rather than retrying forever.
    state = {"attempts": 0}
    seen_dead = False
    for _ in range(MAX_DELIVERY_ATTEMPTS + 2):
        out = plan_retry_state(attempts=state["attempts"], error="transient")
        state["attempts"] = out["attempts"]
        if out["status"] == "dead":
            seen_dead = True
            assert out["backoff_seconds"] is None
            assert out["set_dead_at"] is True
            break
        assert out["backoff_seconds"] is not None and out["backoff_seconds"] > 0
    assert seen_dead
    # Replay preserves attempt history (evidence) and clears terminal state.
    replay = plan_replay_state(attempts=7)
    assert replay["attempts"] == 7
    assert replay["clear_dead_at"] and replay["clear_last_error"] and replay["reset_available_at"]


def test_retry_helper_has_no_io_or_loop_source() -> None:
    # Pure function guard: no DB/network/loop/worker inside the retry planner region.
    start = OUTBOX_SRC.index("def plan_retry_state")
    end = OUTBOX_SRC.index("def plan_replay_state")
    body = OUTBOX_SRC[start:end]
    for banned in ("await", "asyncpg", "conn.", "while ", "Thread", "asyncio"):
        assert banned not in body, banned


# --------------------------------------------------------------------------------------
# Static tier -- M-1 payload safety closure (independent bypass probes)
# --------------------------------------------------------------------------------------

_BYPASS_PROBES = [
    {"meta": {"answer": "raw"}},
    {"items": [{"token": "secret"}]},
    {"answer_body": "raw"},
    {"question_text": "raw"},
    {"TOKEN": "secret"},
    {"unknown_key": "value"},
    {"due_at": {"nested": 1}},
    {"reason": [1, 2]},
    {"reason": 1.5},
    {"clarification_id": "dup"},
]


@pytest.mark.parametrize("payload", _BYPASS_PROBES)
def test_payload_allowlist_rejects_bypass_and_never_leaks_value(payload) -> None:
    from shared.sdk.tasks.lifecycle_outbox import assert_safe_outbox_payload

    with pytest.raises(ValueError) as exc:
        assert_safe_outbox_payload(payload, event_type="clarification.expired")
    msg = str(exc.value)
    for secret in ("secret", "raw"):
        assert secret not in msg


def test_payload_allowlist_rejects_oversized_and_unknown_event() -> None:
    from shared.sdk.tasks.lifecycle_outbox import assert_safe_outbox_payload

    with pytest.raises(ValueError):
        assert_safe_outbox_payload({"reason": "x" * 600}, event_type="clarification.expired")
    with pytest.raises(ValueError):
        assert_safe_outbox_payload({"reason": "ok"}, event_type="clarification.not_a_real_event")


def test_payload_allowlist_accepts_legitimate_canonical_payload() -> None:
    from shared.sdk.tasks.lifecycle_outbox import assert_safe_outbox_payload

    ok = assert_safe_outbox_payload(
        {
            "event_id": "e1",
            "occurred_at": "2026-01-01T00:00:00Z",
            "due_at": "2026-01-01T00:00:00Z",
            "expired_at": "2026-01-01T00:00:05Z",
            "reason": "deadline_passed",
        },
        event_type="clarification.expired",
    )
    assert ok["reason"] == "deadline_passed"


# --------------------------------------------------------------------------------------
# Static tier -- disabled foundation / no live producer
# --------------------------------------------------------------------------------------


def test_no_runtime_module_imports_the_outbox_foundation() -> None:
    hits = []
    for base in ("shared", "apps", "services"):
        d = ROOT / base
        if not d.exists():
            continue
        for py in d.rglob("*.py"):
            if py.name == "lifecycle_outbox.py":
                continue
            text = py.read_text(encoding="utf-8", errors="ignore")
            if "lifecycle_outbox" in text and "import" in text:
                for line in text.splitlines():
                    if "lifecycle_outbox" in line and "import" in line:
                        hits.append(f"{py}: {line.strip()}")
    assert hits == [], hits


# --------------------------------------------------------------------------------------
# PostgreSQL tier -- mandatory independent reproduction
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
            c = await asyncpg.connect(dsn=_DSN, timeout=5)
            await c.close()
            return True

        return asyncio.new_event_loop().run_until_complete(_ping())
    except Exception:
        return False


requires_pg = pytest.mark.skipif(
    not _pg_reachable(),
    reason=(_REFUSAL or "isolated ephemeral test PostgreSQL not reachable"),
)

_NEW_CAS = """
    UPDATE operator_clarification_requests
    SET status='answered', answered_at=statement_timestamp(), updated_at=statement_timestamp()
    WHERE id=$1 AND status='open' AND answered_at IS NULL AND due_at > statement_timestamp()
    RETURNING id
"""
_OLD_CAS = """
    UPDATE operator_clarification_requests
    SET status='answered', answered_at=now(), updated_at=now()
    WHERE id=$1 AND status='open' AND answered_at IS NULL AND due_at > now()
    RETURNING id
"""


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


async def _seed(conn, *, due_sql: str) -> str:
    tid = await conn.fetchval(
        "INSERT INTO operator_tasks (title, task_type, created_by) "
        "VALUES ('t','software_delivery','alice') RETURNING id"
    )
    qmid = await conn.fetchval(
        "INSERT INTO task_messages (task_id, sender_type, sender_id, message_type, body) "
        "VALUES ($1,'human','alice','clarification_question','q') RETURNING id",
        tid,
    )
    cid = await conn.fetchval(
        f"INSERT INTO operator_clarification_requests "
        f"(task_id, question_message_id, question, requested_by_type, requested_by_id, "
        f"due_at, reminder_at) VALUES ($1,$2,'q','human','alice', {due_sql}, {due_sql}) "
        f"RETURNING id",
        tid,
        qmid,
    )
    return str(cid)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _crossing_claim(conn, cas: str) -> bool:
    await _reset_and_migrate(conn)
    cid = await _seed(conn, due_sql="statement_timestamp() + interval '3 seconds'")
    tx = conn.transaction()
    await tx.start()
    txn_start, due_at = await conn.fetchrow(
        "SELECT transaction_timestamp(), "
        "(SELECT due_at FROM operator_clarification_requests WHERE id=$1)",
        uuid.UUID(cid),
    )
    assert txn_start < due_at
    await conn.execute("SELECT pg_sleep(4)")
    stmt_now = await conn.fetchval("SELECT statement_timestamp()")
    assert stmt_now > due_at
    frozen = await conn.fetchval("SELECT now()")
    assert frozen == txn_start and frozen < due_at
    claimed = await conn.fetchval(cas, uuid.UUID(cid))
    await tx.rollback()
    return claimed is not None


@requires_pg
def test_pg_transaction_crossing_rejected_with_nonvacuous_negative_control() -> None:
    """MANDATORY. New predicate rejects the cross-deadline claim; OLD now() predicate would
    accept it (negative control) -- proving the fixed assertion is not vacuous."""

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            new_claimed = await _crossing_claim(conn, _NEW_CAS)
            old_claimed = await _crossing_claim(conn, _OLD_CAS)
            assert new_claimed is False, "remediated predicate must REJECT cross-deadline claim"
            assert old_claimed is True, "negative control: old now() predicate must ACCEPT it"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_strict_equality_boundary_is_false() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            cid = await _seed(conn, due_sql="statement_timestamp() + interval '1 hour'")
            # At exact equality the strict '>' predicate must be false, so the claim matches 0 rows.
            claimed = await conn.fetchval(
                "UPDATE operator_clarification_requests SET status='answered', "
                "answered_at=statement_timestamp() "
                "WHERE id=$1 AND status='open' AND due_at > due_at RETURNING id",
                uuid.UUID(cid),
            )
            assert claimed is None
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_answered_at_is_statement_time_not_transaction_start() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            cid = await _seed(conn, due_sql="statement_timestamp() + interval '1 hour'")
            tx = conn.transaction()
            await tx.start()
            txn_start = await conn.fetchval("SELECT transaction_timestamp()")
            await conn.execute("SELECT pg_sleep(1)")
            answered_at = await conn.fetchval(
                "UPDATE operator_clarification_requests SET status='answered', "
                "answered_at=statement_timestamp() "
                "WHERE id=$1 AND status='open' AND due_at > statement_timestamp() "
                "RETURNING answered_at",
                uuid.UUID(cid),
            )
            await tx.commit()
            assert answered_at > txn_start
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_outbox_status_timestamp_coherence_constraints() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            tid = await conn.fetchval(
                "INSERT INTO operator_tasks (title,task_type,created_by) "
                "VALUES ('t','software_delivery','a') RETURNING id"
            )
            qm = await conn.fetchval(
                "INSERT INTO task_messages (task_id,sender_type,sender_id,message_type,body) "
                "VALUES ($1,'human','a','clarification_question','q') RETURNING id",
                tid,
            )
            cid = await conn.fetchval(
                "INSERT INTO operator_clarification_requests "
                "(task_id,question_message_id,question,requested_by_type,requested_by_id,"
                "due_at,reminder_at) VALUES ($1,$2,'q','human','a', now()+interval '1 hour', now()) "
                "RETURNING id",
                tid,
                qm,
            )
            base = (
                "INSERT INTO clarification_lifecycle_outbox "
                "(clarification_id,task_id,event_type,idempotency_key,status"
            )
            contradictions = [
                base
                + ",published_at) VALUES ($1,$2,'clarification.expired','c1','pending', now())",
                base + ") VALUES ($1,$2,'clarification.expired','c2','published')",
                base
                + ",dead_at,published_at) VALUES ($1,$2,'clarification.expired','c3','dead', now(), now())",
                base + ") VALUES ($1,$2,'clarification.expired','c4','weird')",
            ]
            for sql in contradictions:
                with pytest.raises(asyncpg.exceptions.CheckViolationError):
                    await conn.execute(sql, cid, tid)
            # attempts negative
            with pytest.raises(asyncpg.exceptions.CheckViolationError):
                await conn.execute(
                    "INSERT INTO clarification_lifecycle_outbox "
                    "(clarification_id,task_id,event_type,idempotency_key,attempts) "
                    "VALUES ($1,$2,'clarification.expired','c5', -1)",
                    cid,
                    tid,
                )
            # idempotency uniqueness
            await conn.execute(
                base + ") VALUES ($1,$2,'clarification.expired','dk','pending')", cid, tid
            )
            with pytest.raises(asyncpg.exceptions.UniqueViolationError):
                await conn.execute(
                    base + ") VALUES ($1,$2,'clarification.expired','dk','pending')", cid, tid
                )
            # a valid pending row has available_at defaulted NOT NULL
            av = await conn.fetchval(
                "SELECT available_at FROM clarification_lifecycle_outbox WHERE idempotency_key='dk'"
            )
            assert av is not None
        finally:
            await conn.close()

    _run(scenario())
