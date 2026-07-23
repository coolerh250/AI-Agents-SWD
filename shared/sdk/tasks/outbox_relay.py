"""Step 66C.4-BE2 -- transactional outbox relay for clarification lifecycle events.

DISABLED-BY-DEFAULT worker. Importing this module starts nothing. The relay runs only when an
entrypoint explicitly calls `run_once`, `publish_one`, or `run`.

Delivery model (canonical api-and-event-contract.md 11.3): AT-LEAST-ONCE with a deterministic
idempotency identity (idempotency_key + event_id) that lets downstream consumers deduplicate.
EXACTLY-ONCE is NOT claimed and NOT achievable.

Single durable destination (Step 66C.4-BE2 decision, recorded in be2-outbox-relay-record.md):
  The relay publishes each outbox row to the canonical audit stream via the existing
  `publish_audit_event` SDK entry point. That call returns the XADD id on success and None on a
  drop, which is a reliable per-publish success/failure signal -- exactly what a relay needs and
  what the best-effort publisher cannot provide to a hot path. The existing audit-worker consumes
  stream.audit and produces the durable audit projection (audit_logs) DOWNSTREAM. This is one
  durable destination with downstream projection (the model 11 of the stage prompt prefers); the
  relay does NOT fan out to multiple independent destinations, so there is no per-destination
  partial-success state to track and no transport is rewritten. The event_id (outbox row id) and
  idempotency_key travel in artifact_refs so a downstream consumer can dedupe.

Claim model (canonical, binding): a row is claimed with SELECT ... FOR UPDATE SKIP LOCKED inside
the relay's own transaction and the claim is never held across a process/transaction boundary, so
no claim-owner/lease column is needed and a worker crash rolls the claim back.

Retry/dead (canonical, from BE1 plan_retry_state): persisted backoff in available_at, bounded
attempts, terminal dead with dead_at + bounded last_error. Nothing is retried in a tight loop --
a transient failure schedules a FUTURE available_at and the row is not eligible again until then.
There are MAX_RETRIES=4 scheduled retries across MAX_PUBLISH_ATTEMPTS=5 total attempts; every one
of the (30, 120, 600, 3600)s backoffs is reached before the 5th failure moves the row to dead.

Bounded publish (Step 66C.4-BE2-R1 B-2): the publish runs under a hard total timeout
(publish_timeout_seconds, default 5s, range [1, 30]) AND the relay's Redis client is built with
bounded socket_timeout / socket_connect_timeout, so a hung broker can never pin the DB
transaction, its row lock, or the connection. A timeout is a TRANSIENT failure (retry), never
"published". An asyncio.CancelledError (shutdown) is re-raised, not swallowed, so the transaction
rolls back and the row stays pending -- recoverable later with the same event_id/idempotency_key.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from typing import Any

import asyncpg

from shared.sdk.audit.publisher import publish_audit_event
from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from shared.sdk.tasks import lifecycle_metrics as m
from shared.sdk.tasks.lifecycle_outbox import (
    MAX_LAST_ERROR_CHARS,
    plan_replay_state,
    plan_retry_state,
)
from shared.sdk.tasks.store import DEFAULT_DATABASE_URL

logger = logging.getLogger("clarification.outbox.relay")

DEFAULT_POLL_INTERVAL_SECONDS = 5.0
DEFAULT_BATCH_SIZE = 50
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 30.0

# Bounded total publish timeout (Step 66C.4-BE2-R1 PO decision 1.3). The publish await is capped
# so a hung broker can never pin the DB transaction / row lock / connection indefinitely (B-2).
# Configurable in [1, 30]s; out-of-range is REJECTED at construction, never silently clamped.
DEFAULT_PUBLISH_TIMEOUT_SECONDS = 5.0
MIN_PUBLISH_TIMEOUT_SECONDS = 1.0
MAX_PUBLISH_TIMEOUT_SECONDS = 30.0
PUBLISH_TIMEOUT_ENV = "CLARIFICATION_OUTBOX_PUBLISH_TIMEOUT_SECONDS"
# Safe, secret-free failure reason for a bounded-timeout publish (never a DSN/host/payload).
PUBLISH_TIMEOUT_REASON = "redis_publish_timeout"


def _resolve_publish_timeout(value: float | None) -> float:
    """Validate the total publish timeout. Reject (never clamp) an out-of-range value so the
    operator always knows the effective bound. Falls back to the env var, then the 5s default."""
    if value is None:
        env = os.environ.get(PUBLISH_TIMEOUT_ENV)
        value = float(env) if env else DEFAULT_PUBLISH_TIMEOUT_SECONDS
    if value < MIN_PUBLISH_TIMEOUT_SECONDS or value > MAX_PUBLISH_TIMEOUT_SECONDS:
        raise ValueError(
            "publish_timeout_seconds must be within "
            f"[{MIN_PUBLISH_TIMEOUT_SECONDS}, {MAX_PUBLISH_TIMEOUT_SECONDS}] seconds"
        )
    return value


# Bounded, safe result labels used in audit summaries (never a raw payload).
_EVENT_RESULT = {
    "clarification.reminder_recorded": "recorded",
    "clarification.expired": "expired",
}


def _bounded_error(exc: BaseException) -> str:
    """A bounded, secret-free failure reason: the exception CLASS name only, never its message
    (which could echo a DSN, a payload, or a token). Bounded to the DB/last_error limit."""
    return type(exc).__name__[:MAX_LAST_ERROR_CHARS]


class PublishResult:
    """Outcome of a single publish attempt. `ok` is a definite success/failure determination."""

    __slots__ = ("ok", "reason")

    def __init__(self, ok: bool, reason: str | None = None) -> None:
        self.ok = ok
        self.reason = reason


class ClarificationOutboxRelay:
    """Publishes pending outbox rows to the canonical durable destination with persisted retry.

    Separate failure domain from the poller: this class never claims clarification rows and never
    imports the poller. It exposes one-shot cycles for tests and a `run` loop for a (separately
    invoked) entrypoint.
    """

    def __init__(
        self,
        database_url: str | None = None,
        *,
        event_bus: RedisStreamEventBus | None = None,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        batch_size: int = DEFAULT_BATCH_SIZE,
        shutdown_timeout_seconds: float = DEFAULT_SHUTDOWN_TIMEOUT_SECONDS,
        publish_timeout_seconds: float | None = None,
    ) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
        self.publish_timeout_seconds = _resolve_publish_timeout(publish_timeout_seconds)
        # The default bus is built with bounded socket timeouts so the transport layer itself
        # never blocks forever; the asyncio.wait_for in _publish adds a hard total cap on top.
        # An injected bus (tests) is used as-is.
        self.bus = event_bus or RedisStreamEventBus(
            socket_timeout=self.publish_timeout_seconds,
            socket_connect_timeout=self.publish_timeout_seconds,
        )
        self.poll_interval_seconds = poll_interval_seconds
        self.batch_size = batch_size
        self.shutdown_timeout_seconds = shutdown_timeout_seconds
        self.running = False
        self.published_count = 0
        self.dead_count = 0
        self.retry_count = 0

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    def status(self) -> dict[str, Any]:
        return {
            "service": "clarification-outbox-relay",
            "running": self.running,
            "poll_interval_seconds": self.poll_interval_seconds,
            "batch_size": self.batch_size,
            "published_count": self.published_count,
            "dead_count": self.dead_count,
            "retry_count": self.retry_count,
        }

    # -- publication -------------------------------------------------------------------

    async def _publish(self, row: dict[str, Any]) -> PublishResult:
        """Publish one outbox row to the canonical durable destination.

        Returns a definite ok/fail. `publish_audit_event` returns the XADD id on success and None
        on a drop; a raised exception (e.g. Redis unavailable) is a failure too. Downstream dedupe
        identity (event_id + idempotency_key) travels in artifact_refs.
        """
        event_type = row["event_type"]
        try:
            # Hard total cap on the publish (B-2): a hung broker must never pin the caller's DB
            # transaction/row lock. On timeout the coroutine is cancelled and the row is treated
            # as a TRANSIENT failure (retry), NOT as published.
            message_id = await asyncio.wait_for(
                publish_audit_event(
                    task_id=str(row["task_id"]),
                    workflow_id="",
                    agent="clarification-outbox-relay",
                    decision_type=event_type,
                    summary=f"clarification lifecycle {_EVENT_RESULT.get(event_type, 'event')}",
                    result=_EVENT_RESULT.get(event_type, "recorded"),
                    artifact_refs={
                        "event_id": str(row["id"]),
                        "clarification_id": str(row["clarification_id"]),
                        "idempotency_key": row["idempotency_key"],
                    },
                    event_bus=self.bus,
                    close_bus=False,
                ),
                timeout=self.publish_timeout_seconds,
            )
        except asyncio.TimeoutError:  # broker hang -> bounded transient failure
            return PublishResult(False, PUBLISH_TIMEOUT_REASON)
        except asyncio.CancelledError:
            # Shutdown/cancellation: do NOT swallow it as a transient error. Propagate so the
            # caller rolls back and the row stays pending (recoverable with the same identity).
            raise
        except Exception as exc:  # transport raised -> definite failure
            return PublishResult(False, _bounded_error(exc))
        if message_id is None:  # publisher dropped it -> definite failure
            return PublishResult(False, "publish_dropped")
        return PublishResult(True)

    # -- one row -----------------------------------------------------------------------

    async def publish_one(self, conn: asyncpg.Connection | None = None) -> str | None:
        """Claim and process one eligible pending row. Returns the outcome:
        'published' | 'retry' | 'dead' | None (nothing eligible)."""
        owns = conn is None
        connection = conn or await self._connect()
        tx = connection.transaction()
        await tx.start()
        try:
            row = await connection.fetchrow("""
                SELECT * FROM clarification_lifecycle_outbox
                WHERE status='pending' AND available_at <= statement_timestamp()
                ORDER BY available_at, created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """)
            if row is None:
                await tx.rollback()
                return None
            outcome = await self._process_claimed(connection, dict(row))
            await tx.commit()
            return outcome
        except BaseException:
            # BaseException (not just Exception) so an asyncio.CancelledError during publish also
            # rolls the transaction back before it propagates -- the row lock is released and the
            # row remains pending, recoverable later with the same event_id/idempotency_key.
            with contextlib.suppress(Exception):
                await tx.rollback()
            raise
        finally:
            if owns:
                await connection.close()

    async def _process_claimed(self, conn: asyncpg.Connection, row: dict[str, Any]) -> str:
        event_type = row["event_type"]
        result = await self._publish(row)
        if result.ok:
            await conn.execute(
                """
                UPDATE clarification_lifecycle_outbox
                SET status='published', published_at=statement_timestamp(), last_error=NULL
                WHERE id=$1
                """,
                row["id"],
            )
            self.published_count += 1
            m.OUTBOX_PUBLISH_SUCCESS_TOTAL.labels(event_type=event_type).inc()
            m.LAST_SUCCESSFUL_PUBLISH_TIMESTAMP.set(time.time())
            logger.info("outbox published event_id=%s event_type=%s", row["id"], event_type)
            return "published"

        # Definite failure -> persisted backoff or terminal dead (BE1 plan_retry_state).
        plan = plan_retry_state(attempts=int(row["attempts"]), error=result.reason)
        m.OUTBOX_PUBLISH_FAILURE_TOTAL.labels(event_type=event_type).inc()
        if plan["set_dead_at"]:
            await conn.execute(
                """
                UPDATE clarification_lifecycle_outbox
                SET status='dead', attempts=$2, dead_at=statement_timestamp(),
                    last_error=$3, published_at=NULL
                WHERE id=$1
                """,
                row["id"],
                plan["attempts"],
                plan["last_error"],
            )
            self.dead_count += 1
            m.OUTBOX_DEAD_TOTAL.labels(event_type=event_type).inc()
            logger.warning(
                "outbox dead event_id=%s event_type=%s attempts=%s reason=%s",
                row["id"],
                event_type,
                plan["attempts"],
                plan["last_error"],
            )
            return "dead"

        await conn.execute(
            """
            UPDATE clarification_lifecycle_outbox
            SET attempts=$2,
                available_at=statement_timestamp() + ($3 || ' seconds')::interval,
                last_error=$4
            WHERE id=$1
            """,
            row["id"],
            plan["attempts"],
            str(plan["backoff_seconds"]),
            plan["last_error"],
        )
        self.retry_count += 1
        m.OUTBOX_RETRY_SCHEDULED_TOTAL.labels(event_type=event_type).inc()
        logger.info(
            "outbox retry scheduled event_id=%s event_type=%s attempts=%s backoff=%ss",
            row["id"],
            event_type,
            plan["attempts"],
            plan["backoff_seconds"],
        )
        return "retry"

    # -- one-shot cycle ----------------------------------------------------------------

    async def run_once(self, conn: asyncpg.Connection | None = None) -> dict[str, int]:
        """Process up to batch_size eligible rows. Returns per-outcome counts."""
        owns = conn is None
        connection = conn or await self._connect()
        counts = {"published": 0, "retry": 0, "dead": 0}
        try:
            for _ in range(self.batch_size):
                outcome = await self.publish_one(connection)
                if outcome is None:
                    break
                counts[outcome] += 1
            await self._sample_backlog(connection)
            return counts
        except Exception:
            m.RELAY_CYCLE_FAILURES_TOTAL.inc()
            raise
        finally:
            if owns:
                await connection.close()

    async def _sample_backlog(self, conn: asyncpg.Connection) -> None:
        row = await conn.fetchrow("""
            SELECT count(*) AS pending,
                   COALESCE(EXTRACT(EPOCH FROM (statement_timestamp() - min(created_at))), 0)
                     AS oldest_age
            FROM clarification_lifecycle_outbox WHERE status='pending'
            """)
        if row is not None:
            m.OUTBOX_PENDING_COUNT.set(int(row["pending"]))
            m.OUTBOX_OLDEST_PENDING_AGE_SECONDS.set(float(row["oldest_age"]))

    # -- operator replay foundation ----------------------------------------------------

    async def replay_dead(self, event_id: str, conn: asyncpg.Connection | None = None) -> bool:
        """Internal replay foundation: return one dead row to pending (dead -> pending).

        NOT a public endpoint and NOT wired to any API or Admin Console control. Preserves event_id
        and idempotency_key, does NOT reset attempts, resets available_at, clears dead_at/last_error
        (per BE1 plan_replay_state). Returns True when a dead row was replayed.

        The replay's audit evidence is produced by the relay's normal publication path once the row
        becomes pending again (its idempotency_key is unchanged), so this method performs no live
        publication of its own.
        """
        owns = conn is None
        connection = conn or await self._connect()
        tx = connection.transaction()
        await tx.start()
        try:
            row = await connection.fetchrow(
                """
                SELECT attempts FROM clarification_lifecycle_outbox
                WHERE id=$1 AND status='dead'
                FOR UPDATE
                """,
                event_id,
            )
            if row is None:
                await tx.rollback()
                return False
            plan = plan_replay_state(attempts=int(row["attempts"]))
            await connection.execute(
                """
                UPDATE clarification_lifecycle_outbox
                SET status='pending', attempts=$2, available_at=statement_timestamp(),
                    dead_at=NULL, last_error=NULL
                WHERE id=$1
                """,
                event_id,
                plan["attempts"],
            )
            await tx.commit()
            m.OUTBOX_REPLAY_TOTAL.inc()
            logger.info("outbox replay dead->pending event_id=%s", event_id)
            return True
        except Exception:
            with contextlib.suppress(Exception):
                await tx.rollback()
            raise
        finally:
            if owns:
                await connection.close()

    # -- run loop ----------------------------------------------------------------------

    async def run(self, stop_event: asyncio.Event) -> None:
        """Relay every poll_interval_seconds until stop_event is set. Graceful: no new claim starts
        once stop_event is set; an in-flight transaction commits or rolls back first."""
        self.running = True
        try:
            while not stop_event.is_set():
                try:
                    await self.run_once()
                except asyncio.CancelledError:
                    break
                except Exception:
                    # Redis/DB transient error: persisted retry state means nothing is lost; the
                    # loop keeps running and eligible rows are retried on a later cycle.
                    pass
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self.poll_interval_seconds)
                except asyncio.TimeoutError:
                    pass
        finally:
            self.running = False

    async def close(self) -> None:
        await self.bus.close()
