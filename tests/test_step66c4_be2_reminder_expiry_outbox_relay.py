"""Step 66C.4-BE2 -- reminder/expiry poller and transactional outbox relay tests.

Layers:
  * DB-less unit tests: retry/replay plan wiring, delivery-semantics wording, disabled-foundation
    posture, event-name canonicity.
  * Real-PostgreSQL 16 integration: reminder/expiry claim + atomic state/outbox, concurrency,
    rollback, restart. Gated by the fail-closed guard (BE1_TEST_DATABASE_URL).
  * Real-Redis 7 integration: relay publish/retry/dead/replay, restart recovery, ack-failure
    identity. Gated by BE2_TEST_REDIS_URL.

Nothing is deployed. All PostgreSQL/Redis work runs against isolated ephemeral containers.
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

REMINDER_EVENT = "clarification.reminder_recorded"
EXPIRED_EVENT = "clarification.expired"


def _poller_mod():
    from shared.sdk.tasks import lifecycle_poller

    return lifecycle_poller


def _relay_mod():
    from shared.sdk.tasks import outbox_relay

    return outbox_relay


# --------------------------------------------------------------------------------------
# DB-less unit tests
# --------------------------------------------------------------------------------------


def test_event_names_are_canonical_dotted() -> None:
    lp = _poller_mod()
    assert lp.REMINDER_EVENT_TYPE == REMINDER_EVENT
    assert lp.EXPIRED_EVENT_TYPE == EXPIRED_EVENT
    from shared.sdk.tasks import lifecycle_outbox

    assert REMINDER_EVENT in lifecycle_outbox.ALLOWED_EVENT_TYPES
    assert EXPIRED_EVENT in lifecycle_outbox.ALLOWED_EVENT_TYPES


def test_idempotency_keys_are_deterministic() -> None:
    lp = _poller_mod()
    cid = "11111111-1111-1111-1111-111111111111"
    assert lp._reminder_key(cid) == f"{cid}:reminder"
    assert lp._expired_key(cid) == f"{cid}:expired"


def test_relay_uses_retry_plan_and_bounds_error() -> None:
    orm = _relay_mod()
    # Bounded error is the exception CLASS name only (never a message that could carry a secret).
    reason = orm._bounded_error(ValueError("dsn=postgres://user:secret@host/db token=abc"))
    assert reason == "ValueError"
    assert "secret" not in reason and "token" not in reason


def test_relay_does_not_claim_exactly_once() -> None:
    # The module must document at-least-once and must NOT claim exactly-once.
    src = (REPO / "shared" / "sdk" / "tasks" / "outbox_relay.py").read_text(encoding="utf-8")
    assert "AT-LEAST-ONCE" in src
    assert "EXACTLY-ONCE is NOT claimed" in src


def test_workers_do_not_import_each_other() -> None:
    poller_src = (REPO / "shared" / "sdk" / "tasks" / "lifecycle_poller.py").read_text(
        encoding="utf-8"
    )
    relay_src = (REPO / "shared" / "sdk" / "tasks" / "outbox_relay.py").read_text(encoding="utf-8")
    # No import coupling in either direction (prose mentions are fine).
    assert "import outbox_relay" not in poller_src
    assert "tasks.outbox_relay" not in poller_src
    assert "import lifecycle_poller" not in relay_src
    assert "tasks.lifecycle_poller" not in relay_src


def test_no_startup_background_task_on_import() -> None:
    # Importing the modules must not start a loop, open a connection, or create a task.
    for name in ("lifecycle_poller", "outbox_relay"):
        src = (REPO / "shared" / "sdk" / "tasks" / f"{name}.py").read_text(encoding="utf-8")
        # No module-level asyncio.create_task / run.
        assert "\nasyncio.create_task(" not in src
        assert "\nasyncio.run(" not in src


def test_entrypoints_not_registered_in_any_compose_or_workflow() -> None:
    # BE2 must not add or reference the workers in shared runtime definitions.
    for rel in ("infra", "helm", "k8s", ".github/workflows"):
        base = REPO / rel
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file():
                txt = path.read_text(encoding="utf-8", errors="ignore")
                assert "clarification-lifecycle-worker" not in txt, path
                assert "clarification-outbox-relay" not in txt, path
                assert "lifecycle_poller" not in txt and "outbox_relay" not in txt, path


# --------------------------------------------------------------------------------------
# Real-PostgreSQL / Real-Redis integration
# --------------------------------------------------------------------------------------

try:
    import asyncpg

    _HAS_ASYNCPG = True
except Exception:  # pragma: no cover
    _HAS_ASYNCPG = False

_DSN = os.environ.get("BE1_TEST_DATABASE_URL")
_REDIS = os.environ.get("BE2_TEST_REDIS_URL")
_REFUSAL = destructive_pg_refusal_reason()


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
requires_redis = pytest.mark.skipif(
    not _REDIS, reason="isolated ephemeral Redis 7 not reachable (set BE2_TEST_REDIS_URL)"
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


async def _seed_task(conn, *, status: str = "clarification_needed") -> str:
    return str(
        await conn.fetchval(
            "INSERT INTO operator_tasks (title, task_type, created_by, status) "
            "VALUES ('t','software_delivery','alice',$1) RETURNING id",
            status,
        )
    )


async def _seed_clarification(
    conn,
    task_id: str,
    *,
    reminder_sql: str,
    due_sql: str,
    status: str = "open",
    answered: bool = False,
    reminder_sent: bool = False,
) -> str:
    qmid = await conn.fetchval(
        "INSERT INTO task_messages (task_id, sender_type, sender_id, message_type, body) "
        "VALUES ($1,'human','alice','clarification_question','q') RETURNING id",
        uuid.UUID(task_id),
    )
    cid = await conn.fetchval(
        f"""
        INSERT INTO operator_clarification_requests
          (task_id, question_message_id, question, requested_by_type, requested_by_id,
           status, due_at, reminder_at, answered_at, reminder_sent_at)
        VALUES ($1,$2,'q','human','alice',$3, {due_sql}, {reminder_sql},
                {'statement_timestamp()' if answered else 'NULL'},
                {'statement_timestamp()' if reminder_sent else 'NULL'})
        RETURNING id
        """,
        uuid.UUID(task_id),
        qmid,
        status,
    )
    return str(cid)


class _FailingBus:
    """Event bus whose publish always raises -> publish_audit_event returns None (drop)."""

    def __init__(self) -> None:
        self.calls = 0

    async def publish_event(self, stream, event):
        self.calls += 1
        raise ConnectionError("redis down")

    async def close(self):
        pass


# ---- Reminder poller ----------------------------------------------------------------


@requires_pg
def test_pg_reminder_due_records_state_and_outbox_atomically() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            t = await _seed_task(conn)
            cid = await _seed_clarification(
                conn,
                t,
                reminder_sql="statement_timestamp() - interval '1 hour'",
                due_sql="statement_timestamp() + interval '1 hour'",
            )
            poller = _poller_mod().ClarificationLifecyclePoller(_DSN)
            n = await poller.run_reminder_cycle(conn)
            assert n == 1
            row = await conn.fetchrow(
                "SELECT reminder_sent_at, status FROM operator_clarification_requests WHERE id=$1",
                uuid.UUID(cid),
            )
            assert row["reminder_sent_at"] is not None and row["status"] == "open"
            ob = await conn.fetchrow(
                "SELECT event_type, idempotency_key, status FROM clarification_lifecycle_outbox "
                "WHERE clarification_id=$1",
                uuid.UUID(cid),
            )
            assert ob["event_type"] == REMINDER_EVENT
            assert ob["idempotency_key"] == f"{cid}:reminder"
            assert ob["status"] == "pending"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_reminder_not_due_and_answered_and_expired_are_skipped() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            t = await _seed_task(conn)
            future = await _seed_clarification(
                conn,
                t,
                reminder_sql="statement_timestamp() + interval '1 hour'",
                due_sql="statement_timestamp() + interval '2 hours'",
            )
            answered = await _seed_clarification(
                conn,
                t,
                reminder_sql="statement_timestamp() - interval '1 hour'",
                due_sql="statement_timestamp() + interval '1 hour'",
                status="answered",
                answered=True,
            )
            expired = await _seed_clarification(
                conn,
                t,
                reminder_sql="statement_timestamp() - interval '1 hour'",
                due_sql="statement_timestamp() + interval '1 hour'",
                status="expired",
            )
            poller = _poller_mod().ClarificationLifecyclePoller(_DSN)
            assert await poller.run_reminder_cycle(conn) == 0
            for cid in (future, answered, expired):
                got = await conn.fetchval(
                    "SELECT reminder_sent_at FROM operator_clarification_requests WHERE id=$1",
                    uuid.UUID(cid),
                )
                assert got is None
            assert await conn.fetchval("SELECT count(*) FROM clarification_lifecycle_outbox") == 0
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_past_due_row_is_expired_not_reminded() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            t = await _seed_task(conn)
            cid = await _seed_clarification(
                conn,
                t,
                reminder_sql="statement_timestamp() - interval '2 hours'",
                due_sql="statement_timestamp() - interval '1 hour'",
            )
            poller = _poller_mod().ClarificationLifecyclePoller(_DSN)
            # Reminder guard excludes past-due rows.
            assert await poller.run_reminder_cycle(conn) == 0
            assert (
                await conn.fetchval(
                    "SELECT reminder_sent_at FROM operator_clarification_requests WHERE id=$1",
                    uuid.UUID(cid),
                )
                is None
            )
            # Expiry claims it.
            assert await poller.run_expiry_cycle(conn) == 1
            assert (
                await conn.fetchval(
                    "SELECT status FROM operator_clarification_requests WHERE id=$1",
                    uuid.UUID(cid),
                )
                == "expired"
            )
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_reminder_duplicate_poll_records_once() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            t = await _seed_task(conn)
            cid = await _seed_clarification(
                conn,
                t,
                reminder_sql="statement_timestamp() - interval '1 hour'",
                due_sql="statement_timestamp() + interval '1 hour'",
            )
            poller = _poller_mod().ClarificationLifecyclePoller(_DSN)
            assert await poller.run_reminder_cycle(conn) == 1
            assert await poller.run_reminder_cycle(conn) == 0  # guard: reminder_sent_at set
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM clarification_lifecycle_outbox WHERE clarification_id=$1",
                    uuid.UUID(cid),
                )
                == 1
            )
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_two_workers_reminder_exactly_one_claim() -> None:
    async def scenario() -> None:
        setup = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(setup)
            t = await _seed_task(setup)
            await _seed_clarification(
                setup,
                t,
                reminder_sql="statement_timestamp() - interval '1 hour'",
                due_sql="statement_timestamp() + interval '1 hour'",
            )
        finally:
            await setup.close()

        p1 = _poller_mod().ClarificationLifecyclePoller(_DSN)
        p2 = _poller_mod().ClarificationLifecyclePoller(_DSN)
        results = await asyncio.gather(p1.run_reminder_cycle(), p2.run_reminder_cycle())
        assert sorted(results) == [0, 1]

        verify = await asyncpg.connect(dsn=_DSN)
        try:
            assert await verify.fetchval("SELECT count(*) FROM clarification_lifecycle_outbox") == 1
        finally:
            await verify.close()

    _run(scenario())


@requires_pg
def test_pg_reminder_rollback_leaves_no_state_or_outbox() -> None:
    async def scenario() -> None:
        lp = _poller_mod()
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            t = await _seed_task(conn)
            cid = await _seed_clarification(
                conn,
                t,
                reminder_sql="statement_timestamp() - interval '1 hour'",
                due_sql="statement_timestamp() + interval '1 hour'",
            )
            poller = lp.ClarificationLifecyclePoller(_DSN)

            async def boom(*a, **k):
                raise RuntimeError("injected outbox failure")

            orig = lp.insert_lifecycle_outbox_event
            lp.insert_lifecycle_outbox_event = boom
            try:
                with pytest.raises(RuntimeError):
                    await poller.run_reminder_cycle(conn)
            finally:
                lp.insert_lifecycle_outbox_event = orig

            row = await conn.fetchrow(
                "SELECT reminder_sent_at, status FROM operator_clarification_requests WHERE id=$1",
                uuid.UUID(cid),
            )
            assert row["reminder_sent_at"] is None and row["status"] == "open"
            assert await conn.fetchval("SELECT count(*) FROM clarification_lifecycle_outbox") == 0
        finally:
            await conn.close()

    _run(scenario())


# ---- Expiry poller ------------------------------------------------------------------


@requires_pg
def test_pg_expiry_transitions_clarification_task_and_outbox_atomically() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            t = await _seed_task(conn)
            cid = await _seed_clarification(
                conn,
                t,
                reminder_sql="statement_timestamp() - interval '2 hours'",
                due_sql="statement_timestamp() - interval '1 hour'",
            )
            poller = _poller_mod().ClarificationLifecyclePoller(_DSN)
            assert await poller.run_expiry_cycle(conn) == 1
            clar = await conn.fetchrow(
                "SELECT status, expired_at FROM operator_clarification_requests WHERE id=$1",
                uuid.UUID(cid),
            )
            assert clar["status"] == "expired" and clar["expired_at"] is not None
            task_status = await conn.fetchval(
                "SELECT status FROM operator_tasks WHERE id=$1", uuid.UUID(t)
            )
            assert task_status == "clarification_expired"
            ob = await conn.fetchrow(
                "SELECT event_type, idempotency_key FROM clarification_lifecycle_outbox "
                "WHERE clarification_id=$1",
                uuid.UUID(cid),
            )
            assert ob["event_type"] == EXPIRED_EVENT and ob["idempotency_key"] == f"{cid}:expired"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_expiry_skips_answered_and_suppresses_terminal_parent() -> None:
    """Step 66C.4-BE2-R1 B-1: a due clarification whose parent task is already terminal is
    SUPPRESSED -- clarification unchanged, task unchanged, NO outbox row (was: expired + emitted)."""

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            t_terminal = await _seed_task(conn, status="canceled")
            cid = await _seed_clarification(
                conn,
                t_terminal,
                reminder_sql="statement_timestamp() - interval '2 hours'",
                due_sql="statement_timestamp() - interval '1 hour'",
            )
            answered = await _seed_clarification(
                conn,
                t_terminal,
                reminder_sql="statement_timestamp() - interval '2 hours'",
                due_sql="statement_timestamp() - interval '1 hour'",
                status="answered",
                answered=True,
            )
            poller = _poller_mod().ClarificationLifecyclePoller(_DSN)
            # Terminal parent -> the open past-due clarification is suppressed, nothing committed.
            assert await poller.run_expiry_cycle(conn) == 0
            assert (
                await conn.fetchval(
                    "SELECT status FROM operator_clarification_requests WHERE id=$1",
                    uuid.UUID(cid),
                )
                == "open"  # NOT expired -- parent already terminal
            )
            assert (
                await conn.fetchval(
                    "SELECT status FROM operator_clarification_requests WHERE id=$1",
                    uuid.UUID(answered),
                )
                == "answered"
            )
            # The canceled task must NOT be clobbered, and NO clarification.expired row is emitted.
            assert (
                await conn.fetchval(
                    "SELECT status FROM operator_tasks WHERE id=$1", uuid.UUID(t_terminal)
                )
                == "canceled"
            )
            assert await conn.fetchval("SELECT count(*) FROM clarification_lifecycle_outbox") == 0
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_expiry_task_update_failure_rolls_back_clarification_and_outbox() -> None:
    """Mandatory (§19.8): a task-update failure rolls back the clarification and the outbox."""

    class _TaskUpdateFailingConn:
        def __init__(self, real):
            self._real = real

        def transaction(self):
            return self._real.transaction()

        async def fetchrow(self, *a, **k):
            return await self._real.fetchrow(*a, **k)

        async def fetchval(self, *a, **k):
            return await self._real.fetchval(*a, **k)

        async def execute(self, sql, *a, **k):
            if "operator_tasks" in sql:
                raise RuntimeError("injected task-update failure")
            return await self._real.execute(sql, *a, **k)

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            t = await _seed_task(conn)
            cid = await _seed_clarification(
                conn,
                t,
                reminder_sql="statement_timestamp() - interval '2 hours'",
                due_sql="statement_timestamp() - interval '1 hour'",
            )
            poller = _poller_mod().ClarificationLifecyclePoller(_DSN)
            proxy = _TaskUpdateFailingConn(conn)
            with pytest.raises(RuntimeError):
                await poller.run_expiry_cycle(proxy)
            clar = await conn.fetchval(
                "SELECT status FROM operator_clarification_requests WHERE id=$1", uuid.UUID(cid)
            )
            assert clar == "open"  # rolled back
            assert await conn.fetchval("SELECT count(*) FROM clarification_lifecycle_outbox") == 0
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_two_workers_expiry_exactly_one_claim() -> None:
    async def scenario() -> None:
        setup = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(setup)
            t = await _seed_task(setup)
            await _seed_clarification(
                setup,
                t,
                reminder_sql="statement_timestamp() - interval '2 hours'",
                due_sql="statement_timestamp() - interval '1 hour'",
            )
        finally:
            await setup.close()
        p1 = _poller_mod().ClarificationLifecyclePoller(_DSN)
        p2 = _poller_mod().ClarificationLifecyclePoller(_DSN)
        results = await asyncio.gather(p1.run_expiry_cycle(), p2.run_expiry_cycle())
        assert sorted(results) == [0, 1]

    _run(scenario())


@requires_pg
def test_pg_poller_restart_processes_due_records() -> None:
    async def scenario() -> None:
        seed = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(seed)
            t = await _seed_task(seed)
            await _seed_clarification(
                seed,
                t,
                reminder_sql="statement_timestamp() - interval '1 hour'",
                due_sql="statement_timestamp() + interval '1 hour'",
            )
        finally:
            await seed.close()
        # A brand-new poller instance (fresh "process") picks up the due record.
        poller = _poller_mod().ClarificationLifecyclePoller(_DSN)
        out = await poller.run_once()
        assert out == {"expired": 0, "reminded": 1}

    _run(scenario())


# ---- Relay --------------------------------------------------------------------------


async def _seed_pending_outbox(conn, *, available_sql: str = "statement_timestamp()") -> str:
    t = await _seed_task(conn)
    cid = await _seed_clarification(
        conn,
        t,
        reminder_sql="statement_timestamp() - interval '1 hour'",
        due_sql="statement_timestamp() + interval '1 hour'",
    )
    from shared.sdk.tasks.lifecycle_outbox import insert_lifecycle_outbox_event

    row = await insert_lifecycle_outbox_event(
        conn,
        clarification_id=cid,
        task_id=t,
        event_type=REMINDER_EVENT,
        idempotency_key=f"{cid}:reminder",
        payload={"reason": "reminder_recorded"},
    )
    if available_sql != "statement_timestamp()":
        await conn.execute(
            f"UPDATE clarification_lifecycle_outbox SET available_at={available_sql} WHERE id=$1",
            uuid.UUID(row["id"]),
        )
    return row["id"]


@requires_pg
@requires_redis
def test_pg_redis_relay_publishes_pending_row() -> None:
    from shared.sdk.event_bus.redis_streams import RedisStreamEventBus

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        bus = RedisStreamEventBus(_REDIS)
        try:
            await _reset_and_migrate(conn)
            eid = await _seed_pending_outbox(conn)
            relay = _relay_mod().ClarificationOutboxRelay(_DSN, event_bus=bus)
            assert await relay.publish_one(conn) == "published"
            row = await conn.fetchrow(
                "SELECT status, published_at, last_error FROM clarification_lifecycle_outbox "
                "WHERE id=$1",
                uuid.UUID(eid),
            )
            assert row["status"] == "published"
            assert row["published_at"] is not None and row["last_error"] is None
        finally:
            await bus.close()
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_relay_skips_row_not_yet_available() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            await _seed_pending_outbox(
                conn, available_sql="statement_timestamp() + interval '1 hour'"
            )
            relay = _relay_mod().ClarificationOutboxRelay(_DSN, event_bus=_FailingBus())
            assert await relay.publish_one(conn) is None
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_relay_transient_failure_schedules_backoff_without_exhausting() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            eid = await _seed_pending_outbox(conn)
            relay = _relay_mod().ClarificationOutboxRelay(_DSN, event_bus=_FailingBus())
            # One cycle must schedule exactly one retry, not burn the whole budget.
            counts = await relay.run_once(conn)
            assert counts == {"published": 0, "retry": 1, "dead": 0}
            row = await conn.fetchrow(
                "SELECT status, attempts, available_at, last_error, "
                "available_at > statement_timestamp() AS future "
                "FROM clarification_lifecycle_outbox WHERE id=$1",
                uuid.UUID(eid),
            )
            assert row["status"] == "pending"
            assert row["attempts"] == 1
            assert row["future"] is True  # persisted backoff in the future
            assert row["last_error"] == "publish_dropped"  # bounded, no raw value
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
@requires_redis
def test_pg_redis_relay_retry_then_success() -> None:
    from shared.sdk.event_bus.redis_streams import RedisStreamEventBus

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            eid = await _seed_pending_outbox(conn)
            # Fail once.
            fail_relay = _relay_mod().ClarificationOutboxRelay(_DSN, event_bus=_FailingBus())
            assert await fail_relay.publish_one(conn) == "retry"
            # Make it eligible again, then a working relay publishes it.
            await conn.execute(
                "UPDATE clarification_lifecycle_outbox SET available_at=statement_timestamp() "
                "WHERE id=$1",
                uuid.UUID(eid),
            )
            bus = RedisStreamEventBus(_REDIS)
            try:
                ok_relay = _relay_mod().ClarificationOutboxRelay(_DSN, event_bus=bus)
                assert await ok_relay.publish_one(conn) == "published"
            finally:
                await bus.close()
            row = await conn.fetchrow(
                "SELECT status, attempts FROM clarification_lifecycle_outbox WHERE id=$1",
                uuid.UUID(eid),
            )
            assert row["status"] == "published"
            assert row["attempts"] == 1  # attempts preserved across the retry
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_relay_exhausts_to_dead_after_bounded_attempts() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            eid = await _seed_pending_outbox(conn)
            relay = _relay_mod().ClarificationOutboxRelay(_DSN, event_bus=_FailingBus())
            outcomes = []
            for _ in range(6):
                # Force the row eligible each round so we can drive attempts deterministically.
                await conn.execute(
                    "UPDATE clarification_lifecycle_outbox SET available_at=statement_timestamp() "
                    "WHERE id=$1 AND status='pending'",
                    uuid.UUID(eid),
                )
                out = await relay.publish_one(conn)
                if out is None:
                    break
                outcomes.append(out)
            assert outcomes[-1] == "dead"
            assert outcomes.count("dead") == 1
            row = await conn.fetchrow(
                "SELECT status, dead_at, published_at, attempts, last_error "
                "FROM clarification_lifecycle_outbox WHERE id=$1",
                uuid.UUID(eid),
            )
            assert row["status"] == "dead"
            assert row["dead_at"] is not None and row["published_at"] is None
            assert row["attempts"] == 5  # MAX_PUBLISH_ATTEMPTS (Step 66C.4-BE2-R1 decision 1.2)
            assert len(row["last_error"]) <= 500 and "redis" not in row["last_error"].lower()
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
@requires_redis
def test_pg_redis_two_relays_one_claim() -> None:
    from shared.sdk.event_bus.redis_streams import RedisStreamEventBus

    async def scenario() -> None:
        seed = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(seed)
            await _seed_pending_outbox(seed)
        finally:
            await seed.close()
        bus1 = RedisStreamEventBus(_REDIS)
        bus2 = RedisStreamEventBus(_REDIS)
        try:
            r1 = _relay_mod().ClarificationOutboxRelay(_DSN, event_bus=bus1)
            r2 = _relay_mod().ClarificationOutboxRelay(_DSN, event_bus=bus2)
            results = await asyncio.gather(r1.publish_one(), r2.publish_one())
            assert sorted(str(x) for x in results) == ["None", "published"]
        finally:
            await bus1.close()
            await bus2.close()
        verify = await asyncpg.connect(dsn=_DSN)
        try:
            assert (
                await verify.fetchval(
                    "SELECT count(*) FROM clarification_lifecycle_outbox WHERE status='published'"
                )
                == 1
            )
        finally:
            await verify.close()

    _run(scenario())


@requires_pg
def test_pg_relay_crash_before_commit_leaves_row_recoverable() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            eid = await _seed_pending_outbox(conn)

            class _CommitCrashBus:
                async def publish_event(self, stream, event):
                    return "1-0"  # publish "succeeds"

                async def close(self):
                    pass

            relay = _relay_mod().ClarificationOutboxRelay(_DSN, event_bus=_CommitCrashBus())
            # Simulate a crash after processing but before commit: claim in our own txn, process,
            # then roll back instead of commit.
            tx = conn.transaction()
            await tx.start()
            row = await conn.fetchrow(
                "SELECT * FROM clarification_lifecycle_outbox WHERE status='pending' "
                "AND available_at <= statement_timestamp() FOR UPDATE SKIP LOCKED LIMIT 1"
            )
            await relay._process_claimed(conn, dict(row))
            await tx.rollback()  # crash before commit
            # The row is untouched and still claimable.
            after = await conn.fetchrow(
                "SELECT status, attempts, published_at FROM clarification_lifecycle_outbox "
                "WHERE id=$1",
                uuid.UUID(eid),
            )
            assert after["status"] == "pending"
            assert after["attempts"] == 0 and after["published_at"] is None
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
@requires_redis
def test_pg_redis_restart_recovers_pending_backlog() -> None:
    from shared.sdk.event_bus.redis_streams import RedisStreamEventBus

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            # Three pending rows fail under an outage.
            ids = []
            for _ in range(3):
                ids.append(await _seed_pending_outbox(conn))
            down = _relay_mod().ClarificationOutboxRelay(_DSN, event_bus=_FailingBus())
            await down.run_once(conn)
            pending = await conn.fetchval(
                "SELECT count(*) FROM clarification_lifecycle_outbox WHERE status='pending'"
            )
            assert pending == 3  # nothing lost during the outage
            # Redis recovers; a fresh relay (restart) drains the backlog once eligible.
            await conn.execute(
                "UPDATE clarification_lifecycle_outbox SET available_at=statement_timestamp()"
            )
            bus = RedisStreamEventBus(_REDIS)
            try:
                up = _relay_mod().ClarificationOutboxRelay(_DSN, event_bus=bus)
                counts = await up.run_once(conn)
            finally:
                await bus.close()
            assert counts["published"] == 3
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
@requires_redis
def test_pg_redis_ack_failure_reuses_event_identity() -> None:
    """Publish-succeeds-but-ack-fails allows re-publish with the SAME event_id/idempotency_key."""
    from shared.sdk.event_bus.redis_streams import RedisStreamEventBus

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        bus = RedisStreamEventBus(_REDIS)
        try:
            await _reset_and_migrate(conn)
            eid = await _seed_pending_outbox(conn)
            row = dict(
                await conn.fetchrow(
                    "SELECT * FROM clarification_lifecycle_outbox WHERE id=$1", uuid.UUID(eid)
                )
            )
            relay = _relay_mod().ClarificationOutboxRelay(_DSN, event_bus=bus)
            # Two publications of the same row (as would happen if a DB ack was lost).
            captured = []
            orig = bus.publish_event

            async def capture(stream, event):
                captured.append(event)
                return await orig(stream, event)

            bus.publish_event = capture
            await relay._publish(row)
            await relay._publish(row)
            assert len(captured) == 2
            refs1 = captured[0]["artifact_refs"]
            refs2 = captured[1]["artifact_refs"]
            assert refs1["event_id"] == refs2["event_id"] == eid
            assert (
                refs1["idempotency_key"]
                == refs2["idempotency_key"]
                == f"{row['clarification_id']}:reminder"
            )
        finally:
            await bus.close()
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_operator_replay_foundation_dead_to_pending() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            eid = await _seed_pending_outbox(conn)
            # Drive it to dead.
            await conn.execute(
                "UPDATE clarification_lifecycle_outbox SET status='dead', "
                "dead_at=statement_timestamp(), attempts=4, last_error='publish_dropped' WHERE id=$1",
                uuid.UUID(eid),
            )
            relay = _relay_mod().ClarificationOutboxRelay(_DSN, event_bus=_FailingBus())
            assert await relay.replay_dead(eid, conn) is True
            row = await conn.fetchrow(
                "SELECT status, attempts, dead_at, last_error, idempotency_key, "
                "available_at <= statement_timestamp() AS eligible "
                "FROM clarification_lifecycle_outbox WHERE id=$1",
                uuid.UUID(eid),
            )
            assert row["status"] == "pending"
            assert row["attempts"] == 4  # NOT reset -- full history preserved
            assert row["dead_at"] is None and row["last_error"] is None
            assert row["eligible"] is True
            assert row["idempotency_key"].endswith(":reminder")  # identity preserved
            # Replaying a non-dead row is a no-op.
            assert await relay.replay_dead(eid, conn) is False
        finally:
            await conn.close()

    _run(scenario())
