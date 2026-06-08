"""audit-worker — consumes ``stream.audit`` and persists into ``audit_logs``.

Stage 19 introduces a single, unified audit path:

    service / agent  --publish-->  stream.audit  --consume-->  audit-worker
                                                                   |
                                                                   v
                                                              audit_logs

Behavioural contract:

* Uses the existing ``audit-group`` consumer group (idempotent ``XGROUP CREATE``
  on startup). No application polling — the consume loop uses
  ``XREADGROUP BLOCK``.
* Skips audit-service's own ``audit.recorded`` echo so persistence never
  triggers a circular write loop.
* ``ACK`` only after a successful ``INSERT`` (or after a successful deadletter
  publish in the unrecoverable-failure path). A failed INSERT is left
  un-ACKed so the next ``XREADGROUP`` picks the message up again.
* A poison message that keeps failing is rescued onto ``stream.deadletter``
  with ``event_type: audit.deadlettered`` once and then ACKed; otherwise the
  group's pending list would block.
* Bad message JSON does not crash the loop.
* No production action runs; no GitHub / Slack / cloud API is contacted.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any

from shared.sdk.audit.normalizer import is_audit_recorded_echo, normalize_audit_event
from shared.sdk.audit.store import AuditStore
from shared.sdk.audit_integrity import (
    AuditIntegrityStore,
    SIGNATURE_STATUS_NOT_CONFIGURED,
)
from shared.sdk.event_bus.redis_streams import (
    DEAD_LETTER_STREAM,
    RedisStreamEventBus,
)
from shared.sdk.observability.metrics import (
    AUDIT_INTEGRITY_DEGRADED_TOTAL,
    AUDIT_INTEGRITY_RECORDS_TOTAL,
    AUDIT_WORKER_DEADLETTERED_TOTAL,
    AUDIT_WORKER_FAILURES_TOTAL,
    AUDIT_WORKER_PROCESSED_TOTAL,
    AUDIT_WORKER_PROCESSING_SECONDS,
    AUDIT_WORKER_SKIPPED_TOTAL,
)
from shared.sdk.observability.tracing import start_span

AUDIT_STREAM = "stream.audit"
AUDIT_GROUP = "audit-group"
AUDIT_CONSUMER = "audit-worker-1"
MAX_FAILURES_BEFORE_DEADLETTER = 3


class AuditWorker:
    """Consumes ``stream.audit`` and writes audit_logs rows."""

    def __init__(
        self,
        event_bus: RedisStreamEventBus | None = None,
        store: AuditStore | None = None,
        integrity_store: AuditIntegrityStore | None = None,
    ) -> None:
        self.bus = event_bus or RedisStreamEventBus()
        self.store = store or AuditStore()
        self.integrity_store = integrity_store or AuditIntegrityStore()
        self.processed_count = 0
        self.failed_count = 0
        self.deadlettered_count = 0
        self.skipped_count = 0
        self.integrity_records_written = 0
        self.integrity_degraded_count = 0
        self.audit_integrity_degraded = False
        self.last_message_id: str | None = None
        self.last_task_id: str | None = None
        self.last_error: str | None = None
        self.last_integrity_error: str | None = None
        self.running = False
        # Track retries per message_id so a poison message eventually goes to
        # the deadletter stream instead of blocking the whole group.
        self._retry_counts: dict[str, int] = {}

    def status(self) -> dict[str, Any]:
        return {
            "service": "audit-worker",
            "running": self.running,
            "input_stream": AUDIT_STREAM,
            "group": AUDIT_GROUP,
            "consumer": AUDIT_CONSUMER,
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "deadlettered_count": self.deadlettered_count,
            "skipped_count": self.skipped_count,
            "integrity_records_written": self.integrity_records_written,
            "integrity_degraded_count": self.integrity_degraded_count,
            "audit_integrity_degraded": self.audit_integrity_degraded,
            "audit_integrity_hmac_enabled": self.integrity_store.signer.configured,
            "audit_integrity_signing_key_id": self.integrity_store.signer.key_id,
            "last_message_id": self.last_message_id,
            "last_task_id": self.last_task_id,
            "last_error": self.last_error,
            "last_integrity_error": self.last_integrity_error,
        }

    async def _publish_deadletter(
        self,
        message_id: str,
        payload: dict[str, Any],
        reason: str,
    ) -> bool:
        envelope = {
            "event": "audit.deadlettered",
            "event_type": "audit.deadlettered",
            "task_id": payload.get("task_id") if isinstance(payload, dict) else "unknown",
            "workflow_id": payload.get("workflow_id", "") if isinstance(payload, dict) else "",
            "original_stream": AUDIT_STREAM,
            "original_message_id": message_id,
            "failure_reason": reason,
            "original_event": payload,
            "retry_count": self._retry_counts.get(message_id, 0),
            "max_retries": MAX_FAILURES_BEFORE_DEADLETTER,
            "failed_at": _utcnow_iso(),
        }
        try:
            with start_span(
                "audit_worker.deadletter",
                **{
                    "service.name": "audit-worker",
                    "agent": "audit-worker",
                    "stream": AUDIT_STREAM,
                    "redis.message_id": message_id,
                },
            ):
                await self.bus.publish_event(DEAD_LETTER_STREAM, envelope)
            AUDIT_WORKER_DEADLETTERED_TOTAL.inc()
            return True
        except Exception as exc:
            self.last_error = f"deadletter publish failed: {exc}"
            AUDIT_WORKER_FAILURES_TOTAL.labels(reason="deadletter_error").inc()
            return False

    async def handle(self, message_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Process one stream.audit event.

        Returns one of:

        * ``{action: persisted, audit_id, ack: True}``
        * ``{action: skipped, reason, ack: True}``
        * ``{action: deadlettered, reason, ack: True}``
        * ``{action: retry, reason, ack: False}``  (transient failure)
        """
        self.last_message_id = message_id
        started = time.perf_counter()
        try:
            with start_span(
                "audit_worker.consume",
                **{
                    "service.name": "audit-worker",
                    "agent": "audit-worker",
                    "stream": AUDIT_STREAM,
                    "redis.message_id": message_id,
                },
            ):
                if not isinstance(payload, dict):
                    self.skipped_count += 1
                    AUDIT_WORKER_SKIPPED_TOTAL.labels(reason="empty").inc()
                    return {"action": "skipped", "reason": "non-dict payload", "ack": True}
                if is_audit_recorded_echo(payload):
                    self.skipped_count += 1
                    AUDIT_WORKER_SKIPPED_TOTAL.labels(reason="audit_recorded_echo").inc()
                    return {"action": "skipped", "reason": "audit_recorded_echo", "ack": True}
                with start_span(
                    "audit_worker.normalize",
                    **{
                        "service.name": "audit-worker",
                        "agent": "audit-worker",
                        "redis.message_id": message_id,
                    },
                ):
                    try:
                        normalized = normalize_audit_event(
                            payload,
                            source_message_id=message_id,
                            source_stream=AUDIT_STREAM,
                        )
                    except Exception as exc:
                        self.failed_count += 1
                        self.last_error = f"normalize failed: {exc}"
                        AUDIT_WORKER_FAILURES_TOTAL.labels(reason="normalize_error").inc()
                        await self._publish_deadletter(message_id, payload, str(exc))
                        # Normalizer failures are not retryable — same input
                        # would fail the same way next time.
                        return {"action": "deadlettered", "reason": str(exc), "ack": True}
                task_id = str(normalized.get("task_id") or "")
                decision_type = str(normalized.get("decision_type") or "unknown")
                with start_span(
                    "audit_worker.persist",
                    **{
                        "service.name": "audit-worker",
                        "agent": "audit-worker",
                        "redis.message_id": message_id,
                        "task_id": task_id,
                        "decision_type": decision_type,
                    },
                ):
                    persisted = await self.store.write_audit_log(normalized)
                if persisted is None:
                    self.skipped_count += 1
                    AUDIT_WORKER_SKIPPED_TOTAL.labels(reason="duplicate").inc()
                    self._retry_counts.pop(message_id, None)
                    return {
                        "action": "skipped",
                        "reason": "duplicate source_message_id",
                        "ack": True,
                    }
                self.processed_count += 1
                self.last_task_id = task_id or None
                AUDIT_WORKER_PROCESSED_TOTAL.labels(decision_type=decision_type).inc()
                self._retry_counts.pop(message_id, None)

                # Stage 34 -- append the integrity record for this audit
                # row. Failures degrade the worker (`audit_integrity_degraded`)
                # but do NOT abort the audit-write path; the backfill
                # script can recover later. We deliberately swallow the
                # exception so a transient integrity-write hiccup cannot
                # crash-loop the consumer.
                with start_span(
                    "audit_integrity.persist",
                    **{
                        "service.name": "audit-worker",
                        "agent": "audit-worker",
                        "audit_log_id": persisted.get("audit_id", ""),
                        "task_id": task_id,
                        "decision_type": decision_type,
                    },
                ):
                    try:
                        integrity = (
                            await self.integrity_store.create_integrity_record_for_audit_log(
                                persisted
                            )
                        )
                        if integrity is not None:
                            self.integrity_records_written += 1
                            status_label = (
                                "signing_key_not_configured"
                                if integrity.signature_status == SIGNATURE_STATUS_NOT_CONFIGURED
                                else integrity.signature_status
                            )
                            AUDIT_INTEGRITY_RECORDS_TOTAL.labels(
                                chain_version=str(integrity.chain_version),
                                status=status_label,
                            ).inc()
                            # A successful write clears any prior degradation;
                            # an operator can re-check the flag and re-run
                            # the backfill if the count is still off.
                            self.audit_integrity_degraded = False
                            self.last_integrity_error = None
                    except Exception as exc:
                        self.integrity_degraded_count += 1
                        self.audit_integrity_degraded = True
                        self.last_integrity_error = f"{exc.__class__.__name__}: {exc}"
                        AUDIT_INTEGRITY_DEGRADED_TOTAL.labels(reason="integrity_write_failed").inc()

                return {
                    "action": "persisted",
                    "audit_id": persisted.get("audit_id"),
                    "ack": True,
                }
        except Exception as exc:
            # Transient DB error — let the same message be redelivered. Bump
            # the retry count and, after enough failures, route to deadletter
            # so the group's pending list doesn't grow without bound.
            self.failed_count += 1
            self.last_error = f"persist failed: {exc}"
            AUDIT_WORKER_FAILURES_TOTAL.labels(reason="db_error").inc()
            attempts = self._retry_counts.get(message_id, 0) + 1
            self._retry_counts[message_id] = attempts
            if attempts >= MAX_FAILURES_BEFORE_DEADLETTER:
                published = await self._publish_deadletter(message_id, payload, str(exc))
                self._retry_counts.pop(message_id, None)
                if published:
                    return {"action": "deadlettered", "reason": str(exc), "ack": True}
                # Even deadletter failed — keep the message un-ACKed so the
                # group will redeliver it; the next attempt may succeed.
                return {"action": "retry", "reason": str(exc), "ack": False}
            return {"action": "retry", "reason": str(exc), "ack": False}
        finally:
            AUDIT_WORKER_PROCESSING_SECONDS.observe(time.perf_counter() - started)

    async def _ensure_group(self) -> None:
        """Idempotent group create — never fails when the group already exists."""
        with contextlib.suppress(Exception):
            await self.bus.ensure_group(AUDIT_STREAM, AUDIT_GROUP)

    async def run(self, stop_event: asyncio.Event) -> None:
        """Consume stream.audit until ``stop_event`` is set."""
        self.running = True
        await self._ensure_group()
        try:
            while not stop_event.is_set():
                try:
                    events = await self.bus.consume_events(
                        AUDIT_STREAM,
                        AUDIT_GROUP,
                        AUDIT_CONSUMER,
                        count=20,
                        block_ms=2000,
                    )
                    for event in events:
                        message_id = event["id"]
                        payload = event["event"]
                        try:
                            outcome = await self.handle(message_id, payload)
                        except Exception as exc:  # belt-and-braces: never crash the loop
                            self.last_error = f"handler crashed: {exc}"
                            AUDIT_WORKER_FAILURES_TOTAL.labels(reason="db_error").inc()
                            outcome = {"action": "retry", "ack": False}
                        if outcome.get("ack", True):
                            with contextlib.suppress(Exception):
                                await self.bus.ack_event(AUDIT_STREAM, AUDIT_GROUP, message_id)
                except asyncio.CancelledError:
                    break
                except Exception:
                    # Transient Redis error — back off and keep trying.
                    await asyncio.sleep(1)
        finally:
            self.running = False

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            await self.bus.close()


def _utcnow_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
