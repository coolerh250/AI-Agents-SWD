"""Step 66C.4-BE2-R1 -- expiry consistency (B-1) and bounded relay timeout (B-2) remediation.

Covers the two independently-confirmed blocking findings plus the PO's binding retry and replay
decisions:

  * B-1: expiry locks the parent task, transitions ONLY from clarification_needed with a guarded
    rowcount==1 update, suppresses a terminal parent, and surfaces any other parent as a
    reconciliation failure -- all-or-nothing, never a lone outbox row.
  * B-2: the publish runs under a hard total timeout and a bounded Redis socket timeout; a hung
    broker becomes a transient retry, never "published", and never pins the DB transaction; a
    shutdown cancellation rolls back and re-raises.
  * Retry: MAX_RETRIES=4 across MAX_PUBLISH_ATTEMPTS=5, every backoff reached, dead on the 5th.
  * Replay: dead->pending foundation stays internal-only (no public/runtime/startup caller).

DB-less unit tests run everywhere. Real-PostgreSQL 16 integration is gated by the fail-closed
guard (BE1_TEST_DATABASE_URL). B-2 timeout/cancellation tests need only PostgreSQL plus an
injected fake bus, so they do not require a live Redis. Nothing is deployed.
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

# Terminal statuses that the operator_tasks CHECK constraint actually permits (a subset of the
# canonical TERMINAL_TASK_STATUSES; aborted/completed are canonical-terminal but not DB-storable).
DB_TERMINAL_STATUSES = ("canceled", "rejected", "accepted", "archived", "failed")


def _poller_mod():
    from shared.sdk.tasks import lifecycle_poller

    return lifecycle_poller


def _relay_mod():
    from shared.sdk.tasks import outbox_relay

    return outbox_relay


# --------------------------------------------------------------------------------------
# DB-less unit tests
# --------------------------------------------------------------------------------------


def test_terminal_task_status_set_is_canonical_and_includes_named_terminals() -> None:
    from shared.sdk.tasks.models import TERMINAL_TASK_STATUSES

    # PO decision 1.1 named canonical terminal statuses; all must be covered, including the
    # workflow-level names that operator_tasks cannot store.
    for st in ("canceled", "aborted", "completed", "failed", "accepted", "rejected", "archived"):
        assert st in TERMINAL_TASK_STATUSES, st
    # clarification_needed and running are NOT terminal.
    assert "clarification_needed" not in TERMINAL_TASK_STATUSES
    assert "running" not in TERMINAL_TASK_STATUSES


def test_retry_constants_are_exact_and_reach_every_backoff() -> None:
    from shared.sdk.tasks import lifecycle_outbox as lo

    assert lo.RETRY_BACKOFF_SECONDS == (30, 120, 600, 3600)
    assert lo.MAX_RETRIES == 4
    assert lo.MAX_PUBLISH_ATTEMPTS == 5
    # Drive the planner: 4 pending retries reaching 3600, then dead on the 5th failure.
    seq = []
    attempts = 0
    for _ in range(10):
        plan = lo.plan_retry_state(attempts=attempts, error="x")
        seq.append((plan["status"], plan["backoff_seconds"]))
        attempts = plan["attempts"]
        if plan["status"] == "dead":
            break
    assert seq == [
        ("pending", 30),
        ("pending", 120),
        ("pending", 600),
        ("pending", 3600),
        ("dead", None),
    ]


def test_publish_timeout_config_default_and_range() -> None:
    orm = _relay_mod()
    assert orm.DEFAULT_PUBLISH_TIMEOUT_SECONDS == 5.0
    assert orm._resolve_publish_timeout(None) == 5.0
    assert orm._resolve_publish_timeout(1) == 1
    assert orm._resolve_publish_timeout(30) == 30
    for bad in (0.99, 0, 30.01, 100, -1):
        with pytest.raises(ValueError):
            orm._resolve_publish_timeout(bad)


def test_relay_default_bus_has_bounded_socket_timeouts() -> None:
    relay = _relay_mod().ClarificationOutboxRelay("postgres://x")
    assert relay.publish_timeout_seconds == 5.0
    assert relay.bus._socket_timeout is not None
    assert relay.bus._socket_connect_timeout is not None


def test_relay_out_of_range_publish_timeout_rejected_at_construction() -> None:
    with pytest.raises(ValueError):
        _relay_mod().ClarificationOutboxRelay("postgres://x", publish_timeout_seconds=0.5)
    with pytest.raises(ValueError):
        _relay_mod().ClarificationOutboxRelay("postgres://x", publish_timeout_seconds=31)


def test_publish_wraps_call_in_bounded_wait_for_and_reraises_cancellation() -> None:
    src = (REPO / "shared" / "sdk" / "tasks" / "outbox_relay.py").read_text(encoding="utf-8")
    assert "asyncio.wait_for(" in src
    assert "timeout=self.publish_timeout_seconds" in src
    assert "except asyncio.CancelledError" in src and "raise" in src
    assert "PublishResult(False, PUBLISH_TIMEOUT_REASON)" in src
    # publish_one rolls back on BaseException so cancellation cannot leak a half-committed row.
    assert "except BaseException" in src


def test_expiry_guards_parent_task_and_asserts_rowcount() -> None:
    src = (REPO / "shared" / "sdk" / "tasks" / "lifecycle_poller.py").read_text(encoding="utf-8")
    # Parent task is locked and its status read before any mutation.
    assert "SELECT status FROM operator_tasks WHERE id=$1 FOR UPDATE" in src
    assert "TERMINAL_TASK_STATUSES" in src
    # Guarded update rowcount is inspected (was ignored before B-1 remediation).
    assert "_rowcount(tag) != 1" in src
    assert "reason_code=terminal_parent_suppressed" in src
    assert "reason_code=reconciliation_required" in src


def test_replay_dead_has_no_public_or_runtime_or_startup_caller() -> None:
    # Internal-only foundation: no API surface, no worker entrypoint, no startup registration
    # calls replay_dead or drives an automatic replay loop. Word-boundary match so the unrelated
    # retry-scheduler `replay_deadletter` is not a false positive.
    import re

    callers = []
    for base in (REPO / "apps", REPO / "shared"):
        for path in base.rglob("*.py"):
            if "__pycache__" in str(path):
                continue
            if path.name == "outbox_relay.py":
                continue  # the definition site itself
            txt = path.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"replay_dead\b", txt):
                callers.append(str(path.relative_to(REPO)))
    assert callers == [], callers


# --------------------------------------------------------------------------------------
# Real-PostgreSQL integration
# --------------------------------------------------------------------------------------

try:
    import asyncpg

    _HAS_ASYNCPG = True
except Exception:  # pragma: no cover
    _HAS_ASYNCPG = False

_DSN = os.environ.get("BE1_TEST_DATABASE_URL")
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


async def _seed_due_open_clarification(conn, task_id: str) -> str:
    qmid = await conn.fetchval(
        "INSERT INTO task_messages (task_id, sender_type, sender_id, message_type, body) "
        "VALUES ($1,'human','alice','clarification_question','q') RETURNING id",
        uuid.UUID(task_id),
    )
    cid = await conn.fetchval(
        """
        INSERT INTO operator_clarification_requests
          (task_id, question_message_id, question, requested_by_type, requested_by_id,
           status, due_at, reminder_at)
        VALUES ($1,$2,'q','human','alice','open',
                statement_timestamp() - interval '1 hour',
                statement_timestamp() - interval '2 hours')
        RETURNING id
        """,
        uuid.UUID(task_id),
        qmid,
    )
    return str(cid)


def _counter(metric, **labels) -> float:
    return metric.labels(**labels)._value.get()


# ---- B-1 expiry consistency ---------------------------------------------------------


@requires_pg
def test_pg_b1_expiry_from_clarification_needed_full_transition() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            t = await _seed_task(conn)
            cid = await _seed_due_open_clarification(conn, t)
            poller = _poller_mod().ClarificationLifecyclePoller(_DSN)
            assert await poller.run_expiry_cycle(conn) == 1
            clar = await conn.fetchrow(
                "SELECT status, expired_at FROM operator_clarification_requests WHERE id=$1",
                uuid.UUID(cid),
            )
            assert clar["status"] == "expired" and clar["expired_at"] is not None
            assert (
                await conn.fetchval("SELECT status FROM operator_tasks WHERE id=$1", uuid.UUID(t))
                == "clarification_expired"
            )
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
def test_pg_b1_terminal_parent_suppresses_all_mutations() -> None:
    m = __import__("shared.sdk.tasks.lifecycle_metrics", fromlist=["x"])

    async def scenario(status: str) -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            t = await _seed_task(conn, status=status)
            cid = await _seed_due_open_clarification(conn, t)
            poller = _poller_mod().ClarificationLifecyclePoller(_DSN)
            before = _counter(m.TERMINAL_PARENT_SUPPRESSED_TOTAL, poller="expiry")
            assert await poller.run_expiry_cycle(conn) == 0  # nothing committed
            after = _counter(m.TERMINAL_PARENT_SUPPRESSED_TOTAL, poller="expiry")
            assert after - before == 1  # observable suppression
            # No mutation anywhere, and NO clarification.expired outbox row.
            assert (
                await conn.fetchval(
                    "SELECT status FROM operator_clarification_requests WHERE id=$1", uuid.UUID(cid)
                )
                == "open"
            )
            assert (
                await conn.fetchval("SELECT status FROM operator_tasks WHERE id=$1", uuid.UUID(t))
                == status
            )
            assert await conn.fetchval("SELECT count(*) FROM clarification_lifecycle_outbox") == 0
        finally:
            await conn.close()

    for st in DB_TERMINAL_STATUSES:
        _run(scenario(st))


@requires_pg
def test_pg_b1_unexpected_nonterminal_parent_is_reconciliation_failure() -> None:
    m = __import__("shared.sdk.tasks.lifecycle_metrics", fromlist=["x"])

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            t = await _seed_task(conn, status="running")  # non-terminal, not clarification_needed
            cid = await _seed_due_open_clarification(conn, t)
            poller = _poller_mod().ClarificationLifecyclePoller(_DSN)
            before = _counter(m.RECONCILIATION_FAILURES_TOTAL, poller="expiry")
            assert await poller.run_expiry_cycle(conn) == 0
            after = _counter(m.RECONCILIATION_FAILURES_TOTAL, poller="expiry")
            assert after - before == 1
            assert (
                await conn.fetchval(
                    "SELECT status FROM operator_clarification_requests WHERE id=$1", uuid.UUID(cid)
                )
                == "open"
            )
            assert (
                await conn.fetchval("SELECT status FROM operator_tasks WHERE id=$1", uuid.UUID(t))
                == "running"
            )
            assert await conn.fetchval("SELECT count(*) FROM clarification_lifecycle_outbox") == 0
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_b1_guarded_update_rowcount_zero_rolls_back_everything() -> None:
    """A guarded task UPDATE that affects 0 rows rolls the whole transaction back: clarification
    stays open, task unchanged, no outbox row. Forced via a proxy that reports 'UPDATE 0'."""

    class _ZeroRowUpdateConn:
        def __init__(self, real):
            self._real = real

        def transaction(self):
            return self._real.transaction()

        async def fetchrow(self, *a, **k):
            return await self._real.fetchrow(*a, **k)

        async def fetchval(self, *a, **k):
            return await self._real.fetchval(*a, **k)

        async def execute(self, sql, *a, **k):
            if "UPDATE operator_tasks" in sql:
                # Run the real update (a no-op here) but report 0 affected rows.
                await self._real.execute(sql, *a, **k)
                return "UPDATE 0"
            return await self._real.execute(sql, *a, **k)

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            t = await _seed_task(conn)
            cid = await _seed_due_open_clarification(conn, t)
            poller = _poller_mod().ClarificationLifecyclePoller(_DSN)
            assert await poller.run_expiry_cycle(_ZeroRowUpdateConn(conn)) == 0
            assert (
                await conn.fetchval(
                    "SELECT status FROM operator_clarification_requests WHERE id=$1", uuid.UUID(cid)
                )
                == "open"
            )
            assert (
                await conn.fetchval("SELECT status FROM operator_tasks WHERE id=$1", uuid.UUID(t))
                == "clarification_needed"
            )
            assert await conn.fetchval("SELECT count(*) FROM clarification_lifecycle_outbox") == 0
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_b1_duplicate_poll_and_two_workers_exactly_one_expiry() -> None:
    async def scenario() -> None:
        setup = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(setup)
            t = await _seed_task(setup)
            await _seed_due_open_clarification(setup, t)
        finally:
            await setup.close()
        p1 = _poller_mod().ClarificationLifecyclePoller(_DSN)
        p2 = _poller_mod().ClarificationLifecyclePoller(_DSN)
        results = await asyncio.gather(p1.run_expiry_cycle(), p2.run_expiry_cycle())
        assert sorted(results) == [0, 1]  # exactly one worker committed
        verify = await asyncpg.connect(dsn=_DSN)
        try:
            assert await verify.fetchval("SELECT count(*) FROM clarification_lifecycle_outbox") == 1
            # A second, duplicate poll is harmless (row already expired).
            p3 = _poller_mod().ClarificationLifecyclePoller(_DSN)
            assert await p3.run_expiry_cycle() == 0
            assert await verify.fetchval("SELECT count(*) FROM clarification_lifecycle_outbox") == 1
        finally:
            await verify.close()

    _run(scenario())


# ---- B-2 bounded relay timeout ------------------------------------------------------


class _HangingBus:
    """A bus whose publish blocks far longer than any allowed publish timeout."""

    def __init__(self) -> None:
        self.calls = 0

    async def publish_event(self, stream, event):
        self.calls += 1
        await asyncio.sleep(30)
        return "never"

    async def close(self):
        pass


async def _seed_pending_outbox(conn) -> str:
    t = await _seed_task(conn)
    qmid = await conn.fetchval(
        "INSERT INTO task_messages (task_id, sender_type, sender_id, message_type, body) "
        "VALUES ($1,'human','alice','clarification_question','q') RETURNING id",
        uuid.UUID(t),
    )
    cid = await conn.fetchval(
        """
        INSERT INTO operator_clarification_requests
          (task_id, question_message_id, question, requested_by_type, requested_by_id,
           status, due_at, reminder_at)
        VALUES ($1,$2,'q','human','alice','open',
                statement_timestamp() + interval '1 hour',
                statement_timestamp() - interval '1 hour')
        RETURNING id
        """,
        uuid.UUID(t),
        qmid,
    )
    from shared.sdk.tasks.lifecycle_outbox import insert_lifecycle_outbox_event

    row = await insert_lifecycle_outbox_event(
        conn,
        clarification_id=str(cid),
        task_id=t,
        event_type=REMINDER_EVENT,
        idempotency_key=f"{cid}:reminder",
        payload={"reason": "reminder_recorded"},
    )
    return row["id"]


@requires_pg
def test_pg_b2_broker_hang_times_out_to_retry_without_pinning_txn() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            eid = await _seed_pending_outbox(conn)
            relay = _relay_mod().ClarificationOutboxRelay(
                _DSN, event_bus=_HangingBus(), publish_timeout_seconds=1
            )
            loop = asyncio.get_event_loop()
            started = loop.time()
            outcome = await relay.publish_one(conn)
            elapsed = loop.time() - started
            assert outcome == "retry"
            assert elapsed < 5  # bounded well under the 30s hang
            row = await conn.fetchrow(
                "SELECT status, attempts, last_error, "
                "available_at > statement_timestamp() AS future "
                "FROM clarification_lifecycle_outbox WHERE id=$1",
                uuid.UUID(eid),
            )
            assert row["status"] == "pending"  # NOT published
            assert row["attempts"] == 1
            assert row["future"] is True  # persisted backoff
            assert row["last_error"] == "redis_publish_timeout"
            # The transaction/row lock was released: a SEPARATE connection can update the row.
            other = await asyncpg.connect(dsn=_DSN)
            try:
                await asyncio.wait_for(
                    other.execute(
                        "UPDATE clarification_lifecycle_outbox SET last_error=last_error "
                        "WHERE id=$1",
                        uuid.UUID(eid),
                    ),
                    timeout=5,
                )
            finally:
                await other.close()
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_b2_shutdown_cancellation_rolls_back_and_reraises() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            eid = await _seed_pending_outbox(conn)
            # Long publish timeout so the cancellation (not a timeout) is what interrupts it.
            relay = _relay_mod().ClarificationOutboxRelay(
                _DSN, event_bus=_HangingBus(), publish_timeout_seconds=30
            )
            task = asyncio.ensure_future(relay.publish_one(conn))
            await asyncio.sleep(0.4)  # let it claim the row and start the (hanging) publish
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            # Rolled back: row unchanged and lock released (verified from a fresh connection).
            verify = await asyncpg.connect(dsn=_DSN)
            try:
                row = await verify.fetchrow(
                    "SELECT status, attempts, published_at FROM clarification_lifecycle_outbox "
                    "WHERE id=$1",
                    uuid.UUID(eid),
                )
                assert row["status"] == "pending"
                assert row["attempts"] == 0 and row["published_at"] is None
            finally:
                await verify.close()
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_b2_multiple_rows_all_processable_under_broker_hang() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            ids = [await _seed_pending_outbox(conn) for _ in range(3)]
            relay = _relay_mod().ClarificationOutboxRelay(
                _DSN, event_bus=_HangingBus(), publish_timeout_seconds=1
            )
            counts = await relay.run_once(conn)
            # Every row was claimed and timed out to a persisted retry; none stayed locked.
            assert counts == {"published": 0, "retry": 3, "dead": 0}
            rows = await conn.fetch(
                "SELECT status, attempts, last_error FROM clarification_lifecycle_outbox "
                "WHERE id = ANY($1::uuid[])",
                [uuid.UUID(i) for i in ids],
            )
            assert len(rows) == 3
            for r in rows:
                assert r["status"] == "pending" and r["attempts"] == 1
                assert r["last_error"] == "redis_publish_timeout"
        finally:
            await conn.close()

    _run(scenario())
