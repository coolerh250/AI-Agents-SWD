"""Step 66C.4-BE2-R1-R -- INDEPENDENT closure-review tests.

Written by a fresh, independent review session (NOT the implementation/remediation author) to
re-verify -- from scratch -- that the two blocking findings from the Step 66C.4-BE2-R independent
review are genuinely closed at the feature tip, and that the Product Owner's retry (1.2) and
replay-boundary (1.4) decisions hold in the actual code:

  * B-1 expiry parent-task consistency: the expiry worker locks the parent task and reads its
    status BEFORE any mutation, transitions ONLY from clarification_needed with a guarded
    rowcount==1 update, SUPPRESSES a terminal parent (no mutation, no outbox), and surfaces any
    other parent as an observable reconciliation failure -- all-or-nothing, never a lone outbox row.
  * B-2 bounded relay publish: the publish runs under a hard total timeout (asyncio.wait_for) AND
    a bounded Redis socket/connect timeout, so a hung broker becomes a transient retry, never
    "published", and never pins the DB transaction / row lock / connection; a shutdown
    cancellation rolls the transaction back and re-raises.
  * Retry: every one of the (30,120,600,3600)s backoffs is REACHED, dead on the 5th attempt.
  * Replay: the dead->pending foundation stays internal-only (no public/runtime/startup caller).

DB-less unit tests run everywhere. Real-PostgreSQL 16 integration is gated on BE1_TEST_DATABASE_URL
(fail-closed). The real-Redis publish test is gated on REDIS_URL reachability. The broker-hang test
is gated on an operator-supplied container-name env var so no internal identifier is committed.
Nothing is deployed; the shared runtime is never touched.
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

import pytest

from step66c4_pg_safety import destructive_pg_refusal_reason

REPO = Path(__file__).resolve().parents[1]
MIGRATIONS = REPO / "migrations"

REMINDER_EVENT = "clarification.reminder_recorded"
EXPIRED_EVENT = "clarification.expired"

# Terminal statuses the operator_tasks CHECK constraint actually permits (aborted/completed are
# canonical-terminal but NOT DB-storable, so they are excluded from the DB-driven cases).
DB_TERMINAL_STATUSES = ("canceled", "rejected", "accepted", "archived", "failed")


def _poller_mod():
    from shared.sdk.tasks import lifecycle_poller

    return lifecycle_poller


def _relay_mod():
    from shared.sdk.tasks import outbox_relay

    return outbox_relay


# ======================================================================================
# DB-less unit re-verification
# ======================================================================================


def test_indep_terminal_set_covers_named_terminals_and_excludes_active() -> None:
    from shared.sdk.tasks.models import TERMINAL_TASK_STATUSES

    for st in ("canceled", "aborted", "completed", "failed", "accepted", "rejected", "archived"):
        assert st in TERMINAL_TASK_STATUSES, st
    for st in ("clarification_needed", "clarification_expired", "running", "blocked", "draft"):
        assert st not in TERMINAL_TASK_STATUSES, st


def test_indep_retry_schedule_reaches_every_backoff_then_dies_on_fifth() -> None:
    from shared.sdk.tasks import lifecycle_outbox as lo

    assert lo.RETRY_BACKOFF_SECONDS == (30, 120, 600, 3600)
    assert lo.MAX_RETRIES == 4 and lo.MAX_PUBLISH_ATTEMPTS == 5
    seq, attempts = [], 0
    for _ in range(12):
        plan = lo.plan_retry_state(attempts=attempts, error="boom")
        seq.append((plan["status"], plan["backoff_seconds"], plan["attempts"]))
        attempts = plan["attempts"]
        if plan["status"] == "dead":
            break
    assert seq == [
        ("pending", 30, 1),
        ("pending", 120, 2),
        ("pending", 600, 3),
        ("pending", 3600, 4),  # the previously-dead-code 3600 branch is reached
        ("dead", None, 5),
    ]


def test_indep_publish_timeout_out_of_range_rejected_not_clamped() -> None:
    orm = _relay_mod()
    assert orm.DEFAULT_PUBLISH_TIMEOUT_SECONDS == 5.0
    for good in (1, 5, 30):
        assert orm._resolve_publish_timeout(good) == good
    for bad in (0, 0.9, 30.01, 31, 100, -1):
        with pytest.raises(ValueError):
            orm._resolve_publish_timeout(bad)


def test_indep_default_bus_has_bounded_socket_and_connect_timeouts() -> None:
    relay = _relay_mod().ClarificationOutboxRelay("postgres://x")
    assert relay.publish_timeout_seconds == 5.0
    assert relay.bus._socket_timeout is not None
    assert relay.bus._socket_connect_timeout is not None


def test_indep_relay_source_has_total_wait_for_and_reraises_cancellation() -> None:
    src = (REPO / "shared" / "sdk" / "tasks" / "outbox_relay.py").read_text(encoding="utf-8")
    assert "asyncio.wait_for(" in src and "timeout=self.publish_timeout_seconds" in src
    # Cancellation is re-raised, not swallowed as a transient; the txn rolls back on BaseException.
    assert "except asyncio.CancelledError" in src
    assert "except BaseException" in src
    # A timeout is a transient retry with a bounded, secret-free reason (never "published").
    assert "PublishResult(False, PUBLISH_TIMEOUT_REASON)" in src


def test_indep_expiry_source_locks_parent_before_any_mutation() -> None:
    src = (REPO / "shared" / "sdk" / "tasks" / "lifecycle_poller.py").read_text(encoding="utf-8")
    lock_at = src.index("SELECT status FROM operator_tasks WHERE id=$1 FOR UPDATE")
    guarded_update_at = src.index("UPDATE operator_tasks\n")
    clar_expire_at = src.index("SET status='expired'")
    # The parent lock/read precedes both the guarded task update and the clarification expiry.
    assert lock_at < guarded_update_at < clar_expire_at
    assert "_rowcount(tag) != 1" in src
    assert "TERMINAL_TASK_STATUSES" in src


def test_indep_last_error_is_class_name_only_never_message() -> None:
    orm = _relay_mod()

    class _SecretLeak(Exception):
        pass

    reason = orm._bounded_error(_SecretLeak("postgresql://user:pw@host/db redis://secret"))
    assert reason == "_SecretLeak"
    assert "://" not in reason and "pw" not in reason and "secret" not in reason


def test_indep_redis_streams_change_is_additive_and_backward_compatible() -> None:
    src = (REPO / "shared" / "sdk" / "event_bus" / "redis_streams.py").read_text(encoding="utf-8")
    # New timeout kwargs are optional and default None (existing callers unchanged).
    assert "socket_timeout: float | None = None" in src
    assert "socket_connect_timeout: float | None = None" in src
    # A default-constructed bus adds neither kwarg to from_url, preserving prior behaviour.
    from shared.sdk.event_bus.redis_streams import RedisStreamEventBus

    b = RedisStreamEventBus("redis://localhost:1")
    assert b._socket_timeout is None and b._socket_connect_timeout is None
    # The publish/XADD path is unchanged: still a single xadd of the json-encoded event.
    assert "self.client.xadd(stream," in src


def test_indep_replay_dead_has_no_runtime_or_startup_caller() -> None:
    callers = []
    for base in (REPO / "apps", REPO / "shared"):
        for path in base.rglob("*.py"):
            if "__pycache__" in str(path) or path.name == "outbox_relay.py":
                continue
            if re.search(r"replay_dead\b", path.read_text(encoding="utf-8", errors="ignore")):
                callers.append(str(path.relative_to(REPO)))
    assert callers == [], callers


def test_indep_clarification_task_fk_makes_missing_parent_unreachable() -> None:
    # A due clarification can never reference a non-existent task: the FK guarantees the parent
    # row exists. If a parent is nonetheless unreadable, the poller's status branch (None is
    # neither terminal nor clarification_needed) routes it to reconcile -- proven in PG below.
    sql = (MIGRATIONS / "030_workroom_clarification_foundation.sql").read_text(encoding="utf-8")
    assert "REFERENCES operator_tasks" in sql
    assert "task_id" in sql


# ======================================================================================
# Real-PostgreSQL 16 integration
# ======================================================================================

try:
    import asyncpg

    _HAS_ASYNCPG = True
except Exception:  # pragma: no cover
    _HAS_ASYNCPG = False

_DSN = os.environ.get("BE1_TEST_DATABASE_URL")
_REDIS_URL = os.environ.get("REDIS_URL")
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


async def _seed_pending_outbox(conn, *, event_type: str = REMINDER_EVENT) -> str:
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
        event_type=event_type,
        idempotency_key=f"{cid}:{'reminder' if event_type == REMINDER_EVENT else 'expired'}",
        payload={"reason": "reminder_recorded" if event_type == REMINDER_EVENT else "expired"},
    )
    return row["id"]


def _counter(metric, **labels) -> float:
    return metric.labels(**labels)._value.get()


# ---- B-1 expiry consistency ----------------------------------------------------------


@requires_pg
def test_indep_pg_expiry_full_transition_from_clarification_needed() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            t = await _seed_task(conn)
            cid = await _seed_due_open_clarification(conn, t)
            assert await _poller_mod().ClarificationLifecyclePoller(_DSN).run_expiry_cycle(conn) == 1
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
def test_indep_pg_every_db_terminal_parent_suppressed_no_outbox() -> None:
    m = __import__("shared.sdk.tasks.lifecycle_metrics", fromlist=["x"])

    async def scenario(status: str) -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            t = await _seed_task(conn, status=status)
            cid = await _seed_due_open_clarification(conn, t)
            before = _counter(m.TERMINAL_PARENT_SUPPRESSED_TOTAL, poller="expiry")
            assert await _poller_mod().ClarificationLifecyclePoller(_DSN).run_expiry_cycle(conn) == 0
            assert _counter(m.TERMINAL_PARENT_SUPPRESSED_TOTAL, poller="expiry") - before == 1
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
def test_indep_pg_unexpected_nonterminal_parent_reconciles_without_mutation() -> None:
    m = __import__("shared.sdk.tasks.lifecycle_metrics", fromlist=["x"])

    async def scenario(status: str) -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            t = await _seed_task(conn, status=status)
            cid = await _seed_due_open_clarification(conn, t)
            before = _counter(m.RECONCILIATION_FAILURES_TOTAL, poller="expiry")
            assert await _poller_mod().ClarificationLifecyclePoller(_DSN).run_expiry_cycle(conn) == 0
            assert _counter(m.RECONCILIATION_FAILURES_TOTAL, poller="expiry") - before == 1
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

    for st in ("running", "blocked", "approved_for_execution"):
        _run(scenario(st))


@requires_pg
def test_indep_pg_guarded_rowcount_zero_rolls_back_all() -> None:
    """A guarded task UPDATE that reports 0 rows rolls back the whole transaction: clarification
    stays open, task unchanged, no outbox row. Reproduced with a proxy that reports 'UPDATE 0'
    (the only way to hit rowcount 0 while the row is lock-held is a fault-injection seam)."""

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
                await self._real.execute(sql, *a, **k)
                return "UPDATE 0"
            return await self._real.execute(sql, *a, **k)

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            t = await _seed_task(conn)
            cid = await _seed_due_open_clarification(conn, t)
            outcome = await _poller_mod().ClarificationLifecyclePoller(_DSN).run_expiry_cycle(
                _ZeroRowUpdateConn(conn)
            )
            assert outcome == 0
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
def test_indep_pg_unreadable_parent_status_reconciles() -> None:
    """Defensive path: if the parent status reads as NULL (structurally unreachable under the FK,
    but the code must not silently proceed), the poller reconciles -- no mutation, no outbox."""

    class _NullParentConn:
        def __init__(self, real):
            self._real = real

        def transaction(self):
            return self._real.transaction()

        async def fetchrow(self, *a, **k):
            return await self._real.fetchrow(*a, **k)

        async def fetchval(self, sql, *a, **k):
            if "SELECT status FROM operator_tasks" in sql:
                return None  # simulate an unreadable/missing parent
            return await self._real.fetchval(sql, *a, **k)

        async def execute(self, *a, **k):
            return await self._real.execute(*a, **k)

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            t = await _seed_task(conn)
            cid = await _seed_due_open_clarification(conn, t)
            outcome = await _poller_mod().ClarificationLifecyclePoller(_DSN).run_expiry_cycle(
                _NullParentConn(conn)
            )
            assert outcome == 0
            assert (
                await conn.fetchval(
                    "SELECT status FROM operator_clarification_requests WHERE id=$1", uuid.UUID(cid)
                )
                == "open"
            )
            assert await conn.fetchval("SELECT count(*) FROM clarification_lifecycle_outbox") == 0
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_indep_pg_two_workers_exactly_one_and_duplicate_poll_noop() -> None:
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
        assert sorted(results) == [0, 1]
        verify = await asyncpg.connect(dsn=_DSN)
        try:
            assert await verify.fetchval("SELECT count(*) FROM clarification_lifecycle_outbox") == 1
            assert await _poller_mod().ClarificationLifecyclePoller(_DSN).run_expiry_cycle() == 0
            assert await verify.fetchval("SELECT count(*) FROM clarification_lifecycle_outbox") == 1
        finally:
            await verify.close()

    _run(scenario())


# ---- B-2 bounded relay ---------------------------------------------------------------


class _HangingBus:
    """Publish blocks far longer than any allowed publish timeout."""

    def __init__(self) -> None:
        self.calls = 0

    async def publish_event(self, stream, event):
        self.calls += 1
        await asyncio.sleep(60)
        return "never"

    async def close(self):
        pass


class _AlwaysFailBus:
    """Every publish is a definite failure (poison-style): raises so publish_audit_event drops it."""

    async def publish_event(self, stream, event):
        raise RuntimeError("broker_refused")

    async def close(self):
        pass


@requires_pg
def test_indep_pg_broker_hang_bounded_timeout_persists_retry_and_releases_lock() -> None:
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
            assert elapsed < 5  # bounded well under the 60s hang
            row = await conn.fetchrow(
                "SELECT status, attempts, last_error, published_at, dead_at, "
                "available_at > statement_timestamp() AS future "
                "FROM clarification_lifecycle_outbox WHERE id=$1",
                uuid.UUID(eid),
            )
            assert row["status"] == "pending" and row["published_at"] is None
            assert row["dead_at"] is None and row["attempts"] == 1
            assert row["future"] is True
            assert row["last_error"] == "redis_publish_timeout"
            assert "redis" == row["last_error"][:5]  # bounded, no host/url/secret
            # Lock released: a separate connection can update the row within a short bound.
            other = await asyncpg.connect(dsn=_DSN)
            try:
                await asyncio.wait_for(
                    other.execute(
                        "UPDATE clarification_lifecycle_outbox SET last_error=last_error WHERE id=$1",
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
def test_indep_pg_shutdown_cancellation_rolls_back_and_reraises() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            eid = await _seed_pending_outbox(conn)
            relay = _relay_mod().ClarificationOutboxRelay(
                _DSN, event_bus=_HangingBus(), publish_timeout_seconds=30
            )
            task = asyncio.ensure_future(relay.publish_one(conn))
            await asyncio.sleep(0.4)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            verify = await asyncpg.connect(dsn=_DSN)
            try:
                row = await verify.fetchrow(
                    "SELECT status, attempts, published_at, dead_at "
                    "FROM clarification_lifecycle_outbox WHERE id=$1",
                    uuid.UUID(eid),
                )
                assert row["status"] == "pending" and row["attempts"] == 0
                assert row["published_at"] is None and row["dead_at"] is None
            finally:
                await verify.close()
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_indep_pg_multi_row_hang_each_bounded_pool_not_saturated() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            ids = [await _seed_pending_outbox(conn) for _ in range(3)]
            relay = _relay_mod().ClarificationOutboxRelay(
                _DSN, event_bus=_HangingBus(), publish_timeout_seconds=1
            )
            counts = await relay.run_once(conn)
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
            # The connection is reusable afterwards -- no leaked/pinned state.
            assert await conn.fetchval("SELECT 1") == 1
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_indep_pg_poison_bounded_progression_to_dead_and_restart_gated() -> None:
    """A persistently failing (poison) row consumes the full 5-attempt schedule and then dies --
    it never tight-loops. Between attempts the row is only re-eligible once available_at elapses,
    which is exactly what a restart honours (continues from persisted available_at)."""

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            eid = await _seed_pending_outbox(conn)
            relay = _relay_mod().ClarificationOutboxRelay(_DSN, event_bus=_AlwaysFailBus())
            outcomes = []
            for i in range(5):
                if i > 0:
                    # After a retry scheduled a FUTURE available_at, a fresh poll before the
                    # backoff elapses is a no-op -- a restart cannot tight-loop the poison row.
                    assert await relay.publish_one(conn) is None
                    # Simulate the persisted backoff elapsing; the row becomes eligible again.
                    await conn.execute(
                        "UPDATE clarification_lifecycle_outbox "
                        "SET available_at=statement_timestamp() - interval '1 second' WHERE id=$1",
                        uuid.UUID(eid),
                    )
                outcomes.append(await relay.publish_one(conn))
            assert outcomes == ["retry", "retry", "retry", "retry", "dead"]
            row = await conn.fetchrow(
                "SELECT status, attempts, dead_at, published_at, last_error "
                "FROM clarification_lifecycle_outbox WHERE id=$1",
                uuid.UUID(eid),
            )
            assert row["status"] == "dead" and row["attempts"] == 5
            assert row["dead_at"] is not None and row["published_at"] is None
            # A safe, bounded reason (publish_audit_event swallows the transport exception to None,
            # which the relay records as 'publish_dropped'); never a raw message/DSN/payload.
            assert row["last_error"] == "publish_dropped"
            assert "://" not in row["last_error"] and len(row["last_error"]) <= 500
        finally:
            await conn.close()

    _run(scenario())


# ---- B-2 real-Redis 7 ----------------------------------------------------------------


def _redis_ok() -> bool:
    if not _REDIS_URL:
        return False
    try:
        import redis.asyncio as aioredis

        async def _ping() -> bool:
            c = aioredis.from_url(_REDIS_URL, socket_timeout=5, socket_connect_timeout=5)
            await c.ping()
            await c.aclose()
            return True

        return asyncio.new_event_loop().run_until_complete(_ping())
    except Exception:
        return False


requires_redis = pytest.mark.skipif(
    not (_pg_ok() and _redis_ok()), reason="isolated ephemeral PostgreSQL 16 + Redis 7 not reachable"
)


@requires_redis
def test_indep_pg_real_redis_normal_publish_lands_on_stream_and_marks_published() -> None:
    from shared.sdk.event_bus.redis_streams import RedisStreamEventBus

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            eid = await _seed_pending_outbox(conn)
            bus = RedisStreamEventBus(_REDIS_URL, socket_timeout=5, socket_connect_timeout=5)
            before = await bus.client.xlen("stream.audit")
            relay = _relay_mod().ClarificationOutboxRelay(
                _DSN, event_bus=bus, publish_timeout_seconds=5
            )
            assert await relay.publish_one(conn) == "published"
            row = await conn.fetchrow(
                "SELECT status, published_at, dead_at, last_error "
                "FROM clarification_lifecycle_outbox WHERE id=$1",
                uuid.UUID(eid),
            )
            assert row["status"] == "published" and row["published_at"] is not None
            assert row["dead_at"] is None and row["last_error"] is None
            # The event actually landed on the canonical audit stream.
            assert await bus.client.xlen("stream.audit") == before + 1
            await bus.close()
        finally:
            await conn.close()

    _run(scenario())


@requires_redis
def test_indep_pg_real_redis_broker_pause_bounded_to_retry() -> None:
    """Real Redis 7 broker hang: pause the container so XADD stalls, confirm the publish returns
    near the configured bound (not the wall-clock forever) and the row persists a transient retry,
    never published. Gated on an operator-supplied container name so no internal id is committed."""
    container = os.environ.get("BE2R1R_REDIS_PAUSE_CONTAINER")
    if not container:
        pytest.skip("BE2R1R_REDIS_PAUSE_CONTAINER not set (docker-pause hang test opt-in)")
    from shared.sdk.event_bus.redis_streams import RedisStreamEventBus

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        paused = False
        try:
            await _reset_and_migrate(conn)
            eid = await _seed_pending_outbox(conn)
            bus = RedisStreamEventBus(_REDIS_URL, socket_timeout=2, socket_connect_timeout=2)
            await bus.client.ping()  # establish the connection before pausing
            relay = _relay_mod().ClarificationOutboxRelay(
                _DSN, event_bus=bus, publish_timeout_seconds=2
            )
            subprocess.run(["docker", "pause", container], check=True)
            paused = True
            started = time.monotonic()
            outcome = await relay.publish_one(conn)
            elapsed = time.monotonic() - started
            subprocess.run(["docker", "unpause", container], check=True)
            paused = False
            assert outcome == "retry"
            assert elapsed < 10  # bounded by the 2s socket/total timeout, not an unbounded hang
            row = await conn.fetchrow(
                "SELECT status, attempts, published_at, dead_at, last_error "
                "FROM clarification_lifecycle_outbox WHERE id=$1",
                uuid.UUID(eid),
            )
            assert row["status"] == "pending" and row["published_at"] is None
            assert row["dead_at"] is None and row["attempts"] == 1
            # Safe, bounded reason; either the total-timeout or the dropped-publish class.
            assert row["last_error"] in ("redis_publish_timeout", "publish_dropped")
            assert "://" not in (row["last_error"] or "")
            await bus.close()
        finally:
            if paused:
                subprocess.run(["docker", "unpause", container], check=False)
            await conn.close()

    _run(scenario())
