"""Step 66C.4-BE2 -- clarification lifecycle poller (reminder + expiry transitions).

DISABLED-BY-DEFAULT worker. Importing this module starts nothing: no background task, no
connection, no timer. The poller runs only when an entrypoint explicitly calls `run_once`,
`run_reminder_cycle`, `run_expiry_cycle`, or `run`.

Design (canonical lifecycle-and-time-contract.md, api-and-event-contract.md 11.2/11.3,
data-model-contract.md):

  * Reminder and expiry are dedicated DB-poll transitions. The database clock
    (statement_timestamp()) is authoritative; scheduler lag only delays materialization, never the
    deadline (BE1's answer CAS already enforces due_at > statement_timestamp()).
  * Each transition claims ONE row at a time with SELECT ... FOR UPDATE SKIP LOCKED, so multiple
    workers never process the same row and a crash before COMMIT rolls the claim back. No lease
    column, no leader election, no Redis lock.
  * The lifecycle state UPDATE(s) and the clarification_lifecycle_outbox INSERT commit in ONE
    transaction -- both or neither. The outbox insert goes through the BE1 repository
    (insert_lifecycle_outbox_event), which is transaction-aware.
  * The relay (outbox_relay.py) is what publishes the outbox row; the poller writes NO Redis event
    and sends NO external notification.

Reminder claim guard (canonical): status='open' AND answered_at IS NULL AND reminder_sent_at IS NULL
  AND reminder_at <= statement_timestamp() AND due_at > statement_timestamp(). A past-due row is NOT
  reminded here -- expiry handles it.
Expiry claim guard (canonical): status='open' AND answered_at IS NULL
  AND due_at <= statement_timestamp().

Expiry parent-task consistency (Step 66C.4-BE2-R1 B-1, PO decision 1.1): after claiming a due
clarification, expiry LOCKS the parent task (SELECT ... FOR UPDATE) and reads its status before
mutating anything. Only when the parent is 'clarification_needed' does the transaction expire the
clarification, move the task to 'clarification_expired' (guarded UPDATE whose affected rowcount
MUST be exactly 1, else the whole transaction rolls back), and insert the outbox row -- all or
nothing. A terminal parent (canceled/aborted/completed/failed/... per TERMINAL_TASK_STATUSES) is
SUPPRESSED with no mutation and a terminal_parent_suppressed metric. Any other (non-terminal,
non-clarification_needed) parent is a lifecycle-invariant mismatch: no mutation, a
reconciliation_failure metric, and a safe diagnostic -- never a silent, unobservable retry.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
import uuid
from typing import Any

import asyncpg

from shared.sdk.tasks import lifecycle_metrics as m
from shared.sdk.tasks.lifecycle_outbox import insert_lifecycle_outbox_event
from shared.sdk.tasks.models import TERMINAL_TASK_STATUSES
from shared.sdk.tasks.store import DEFAULT_DATABASE_URL

logger = logging.getLogger("clarification.lifecycle.poller")

REMINDER_EVENT_TYPE = "clarification.reminder_recorded"
EXPIRED_EVENT_TYPE = "clarification.expired"

# The only parent-task status from which expiry may transition the task (PO decision 1.1).
EXPIRABLE_PARENT_TASK_STATUS = "clarification_needed"

DEFAULT_POLL_INTERVAL_SECONDS = 60.0
DEFAULT_BATCH_SIZE = 50
DEFAULT_SHUTDOWN_TIMEOUT_SECONDS = 30.0


def _reminder_key(clarification_id: str) -> str:
    return f"{clarification_id}:reminder"


def _expired_key(clarification_id: str) -> str:
    return f"{clarification_id}:expired"


def _rowcount(command_tag: str) -> int:
    """Affected-row count from an asyncpg command tag (e.g. 'UPDATE 1'). -1 if unparseable."""
    try:
        return int(command_tag.split()[-1])
    except (ValueError, IndexError, AttributeError):
        return -1


class ClarificationLifecyclePoller:
    """Reminder + expiry lifecycle transitions over a dedicated DB poll.

    Separate failure domain from the relay: this class never publishes to Redis and never imports
    the relay. It exposes one-shot cycles for tests and a `run` loop for a (separately invoked)
    entrypoint.
    """

    def __init__(
        self,
        database_url: str | None = None,
        *,
        poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS,
        batch_size: int = DEFAULT_BATCH_SIZE,
        shutdown_timeout_seconds: float = DEFAULT_SHUTDOWN_TIMEOUT_SECONDS,
    ) -> None:
        self.database_url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
        self.poll_interval_seconds = poll_interval_seconds
        self.batch_size = batch_size
        self.shutdown_timeout_seconds = shutdown_timeout_seconds
        self.running = False
        self.reminder_claims = 0
        self.expiry_claims = 0
        self.last_error_code: str | None = None

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.database_url, timeout=5)

    def status(self) -> dict[str, Any]:
        return {
            "service": "clarification-lifecycle-poller",
            "running": self.running,
            "poll_interval_seconds": self.poll_interval_seconds,
            "batch_size": self.batch_size,
            "reminder_claims": self.reminder_claims,
            "expiry_claims": self.expiry_claims,
            "last_error_code": self.last_error_code,
        }

    # -- one-shot cycles ---------------------------------------------------------------

    async def run_reminder_cycle(self, conn: asyncpg.Connection | None = None) -> int:
        """Claim + transition up to batch_size due reminders. Returns the count committed."""
        return await self._run_cycle(poller="reminder", claim=self._claim_one_reminder, conn=conn)

    async def run_expiry_cycle(self, conn: asyncpg.Connection | None = None) -> int:
        """Claim + transition up to batch_size due expiries. Returns the count committed."""
        return await self._run_cycle(poller="expiry", claim=self._claim_one_expiry, conn=conn)

    async def run_once(self, conn: asyncpg.Connection | None = None) -> dict[str, int]:
        """Run one expiry cycle then one reminder cycle.

        Expiry runs first so a row that is already past due_at is expired rather than reminded
        (the reminder guard also excludes past-due rows, so ordering is belt-and-braces).
        """
        expired = await self.run_expiry_cycle(conn=conn)
        reminded = await self.run_reminder_cycle(conn=conn)
        return {"expired": expired, "reminded": reminded}

    async def _run_cycle(self, *, poller: str, claim, conn: asyncpg.Connection | None) -> int:
        owns = conn is None
        connection = conn or await self._connect()
        committed = 0
        skip: list[uuid.UUID] = []
        started = time.perf_counter()
        try:
            for _ in range(self.batch_size):
                outcome = await claim(connection, skip)
                if outcome is None:
                    break
                status, claim_id = outcome
                if status == "committed":
                    committed += 1
                elif status == "suppressed_terminal":
                    # Parent task already terminal: nothing mutated. Observable, and skipped this
                    # cycle so one due row cannot starve the batch.
                    skip.append(claim_id)
                    m.TERMINAL_PARENT_SUPPRESSED_TOTAL.labels(poller=poller).inc()
                elif status == "reconcile":
                    # Rolled back on a lifecycle-invariant mismatch (unexpected non-terminal
                    # parent, guarded-update rowcount != 1, or an outbox collision). Observable;
                    # not re-selected this cycle.
                    skip.append(claim_id)
                    m.RECONCILIATION_FAILURES_TOTAL.labels(poller=poller).inc()
            m.POLL_CYCLES_TOTAL.labels(poller=poller).inc()
            m.LAST_SUCCESSFUL_POLL_TIMESTAMP.labels(poller=poller).set(time.time())
            return committed
        except Exception as exc:
            self.last_error_code = type(exc).__name__
            m.POLL_CYCLE_FAILURES_TOTAL.labels(poller=poller).inc()
            logger.warning(
                "lifecycle poll cycle failed poller=%s error=%s", poller, type(exc).__name__
            )
            raise
        finally:
            m.POLL_DURATION_SECONDS.labels(poller=poller).observe(time.perf_counter() - started)
            if owns:
                await connection.close()

    # -- reminder ----------------------------------------------------------------------

    async def _claim_one_reminder(
        self, conn: asyncpg.Connection, skip: list[uuid.UUID]
    ) -> tuple[str, uuid.UUID] | None:
        tx = conn.transaction()
        await tx.start()
        try:
            row = await conn.fetchrow(
                """
                SELECT id, task_id
                FROM operator_clarification_requests
                WHERE status='open'
                  AND answered_at IS NULL
                  AND reminder_sent_at IS NULL
                  AND reminder_at <= statement_timestamp()
                  AND due_at > statement_timestamp()
                  AND NOT (id = ANY($1::uuid[]))
                ORDER BY reminder_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """,
                skip,
            )
            if row is None:
                await tx.rollback()
                return None
            cid = row["id"]
            task_id = row["task_id"]
            await conn.execute(
                """
                UPDATE operator_clarification_requests
                SET reminder_sent_at=statement_timestamp(), updated_at=statement_timestamp()
                WHERE id=$1
                """,
                cid,
            )
            try:
                await insert_lifecycle_outbox_event(
                    conn,
                    clarification_id=str(cid),
                    task_id=str(task_id),
                    event_type=REMINDER_EVENT_TYPE,
                    idempotency_key=_reminder_key(str(cid)),
                    payload={"reason": "reminder_recorded"},
                )
            except asyncpg.UniqueViolationError:
                await tx.rollback()
                logger.warning(
                    "reminder outbox collision (reconciliation) clarification_id=%s", cid
                )
                return ("reconcile", cid)
            await tx.commit()
            self.reminder_claims += 1
            m.REMINDER_CLAIMS_TOTAL.inc()
            logger.info("reminder recorded clarification_id=%s task_id=%s", cid, task_id)
            return ("committed", cid)
        except asyncpg.UniqueViolationError:
            raise
        except Exception:
            with contextlib.suppress(Exception):
                await tx.rollback()
            raise

    # -- expiry ------------------------------------------------------------------------

    async def _claim_one_expiry(
        self, conn: asyncpg.Connection, skip: list[uuid.UUID]
    ) -> tuple[str, uuid.UUID] | None:
        tx = conn.transaction()
        await tx.start()
        try:
            row = await conn.fetchrow(
                """
                SELECT id, task_id
                FROM operator_clarification_requests
                WHERE status='open'
                  AND answered_at IS NULL
                  AND due_at <= statement_timestamp()
                  AND NOT (id = ANY($1::uuid[]))
                ORDER BY due_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """,
                skip,
            )
            if row is None:
                await tx.rollback()
                return None
            cid = row["id"]
            task_id = row["task_id"]

            # Lock the parent task and read its authoritative status BEFORE any mutation. Lock
            # ordering is clarification-then-task; no other path locks BOTH tables in one
            # transaction (the answer CAS and every task-status write are single-statement
            # autocommit updates), so this introduces no new deadlock cycle.
            task_status = await conn.fetchval(
                "SELECT status FROM operator_tasks WHERE id=$1 FOR UPDATE", task_id
            )

            # Parent already terminal: leave clarification, task, and outbox untouched (PO 1.1).
            # Suppression is observable via the terminal_parent_suppressed metric; the diagnostic
            # carries only safe identifiers and the observed status.
            if task_status in TERMINAL_TASK_STATUSES:
                await tx.rollback()
                logger.info(
                    "expiry suppressed clarification_id=%s task_id=%s observed_task_status=%s "
                    "reason_code=terminal_parent_suppressed",
                    cid,
                    task_id,
                    task_status,
                )
                return ("suppressed_terminal", cid)

            # Parent neither terminal nor clarification_needed: a lifecycle-invariant mismatch.
            # Leave everything untouched and surface it as a reconciliation failure (PO 1.1).
            if task_status != EXPIRABLE_PARENT_TASK_STATUS:
                await tx.rollback()
                logger.warning(
                    "expiry mismatch clarification_id=%s task_id=%s observed_task_status=%s "
                    "reason_code=reconciliation_required",
                    cid,
                    task_id,
                    task_status,
                )
                return ("reconcile", cid)

            # Parent is clarification_needed: perform the full atomic transition. The guarded
            # UPDATE must affect EXACTLY one row (we hold the task lock, so this is an invariant
            # check); a 0-row result rolls the whole transaction back -- no clarification expiry,
            # no outbox row -- and is surfaced as a reconciliation failure.
            tag = await conn.execute(
                """
                UPDATE operator_tasks
                SET status='clarification_expired', updated_at=statement_timestamp()
                WHERE id=$1 AND status='clarification_needed'
                """,
                task_id,
            )
            if _rowcount(tag) != 1:
                await tx.rollback()
                logger.warning(
                    "expiry rolled back: guarded task update affected %s rows "
                    "clarification_id=%s task_id=%s reason_code=reconciliation_required",
                    _rowcount(tag),
                    cid,
                    task_id,
                )
                return ("reconcile", cid)

            await conn.execute(
                """
                UPDATE operator_clarification_requests
                SET status='expired', expired_at=statement_timestamp(),
                    updated_at=statement_timestamp()
                WHERE id=$1
                """,
                cid,
            )
            try:
                await insert_lifecycle_outbox_event(
                    conn,
                    clarification_id=str(cid),
                    task_id=str(task_id),
                    event_type=EXPIRED_EVENT_TYPE,
                    idempotency_key=_expired_key(str(cid)),
                    payload={"reason": "expired"},
                )
            except asyncpg.UniqueViolationError:
                await tx.rollback()
                logger.warning("expiry outbox collision (reconciliation) clarification_id=%s", cid)
                return ("reconcile", cid)
            await tx.commit()
            self.expiry_claims += 1
            m.EXPIRY_CLAIMS_TOTAL.inc()
            logger.info("clarification expired clarification_id=%s task_id=%s", cid, task_id)
            return ("committed", cid)
        except asyncpg.UniqueViolationError:
            raise
        except Exception:
            with contextlib.suppress(Exception):
                await tx.rollback()
            raise

    # -- run loop ----------------------------------------------------------------------

    async def run(self, stop_event: asyncio.Event) -> None:
        """Poll every poll_interval_seconds until stop_event is set. Graceful: a cycle in flight
        completes (or rolls back) before shutdown; no new claim starts once stop_event is set."""
        self.running = True
        try:
            while not stop_event.is_set():
                try:
                    await self.run_once()
                except asyncio.CancelledError:
                    break
                except Exception:
                    # A transient DB error must not kill the loop; it is counted and retried.
                    pass
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=self.poll_interval_seconds)
                except asyncio.TimeoutError:
                    pass
        finally:
            self.running = False
