import asyncio
import contextlib
import json
from datetime import datetime, timezone

from shared.sdk.event_bus.redis_streams import (
    DEAD_LETTER_STREAM,
    RedisStreamEventBus,
    get_max_retries,
    get_retry_count,
)
from shared.sdk.http_clients.audit_http_client import AuditHttpClient
from shared.sdk.incidents import IncidentStore
from shared.sdk.notifications.client import send_notification
from shared.sdk.observability.metrics import RETRY_TOTAL, WORKFLOW_FAILED_TOTAL
from shared.sdk.observability.tracing import start_span
from shared.sdk.workflow_store.store import WorkflowStore

DEAD_LETTER_GROUP = "retry-scheduler-group"
DEAD_LETTER_CONSUMER = "retry-scheduler-1"
TERMINAL_FAILURE_STREAM = "stream.deadletter.terminal"
DEFAULT_RETRY_DELAY_SECONDS = 1.0
MAX_RETRY_DELAY_SECONDS = 60.0


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RetryScheduler:
    """Consumes stream.deadletter and re-queues each event to its original stream.

    A dead-letter event is requeued after ``retry_after_seconds`` to its
    ``original_stream`` with ``event: retry.requeued``. Events whose retry_count
    has already exceeded ``max_retries`` are marked ``terminal_failure: true`` on
    a separate ``stream.deadletter.terminal`` stream and never re-queued. The
    scheduler also exposes a manual replay path (``replay(message_id)``) that an
    operator can call to put an entry back on its original stream.

    There is no busy polling — the consume loop uses XREADGROUP BLOCK and each
    scheduled requeue uses asyncio.sleep.
    """

    def __init__(self, event_bus: RedisStreamEventBus | None = None) -> None:
        self.bus = event_bus or RedisStreamEventBus()
        self.requeued_count = 0
        self.terminal_count = 0
        self.last_message_id: str | None = None
        self.running = False
        self._tasks: set[asyncio.Task] = set()

    def status(self) -> dict:
        return {
            "service": "retry-scheduler",
            "running": self.running,
            "input_stream": DEAD_LETTER_STREAM,
            "group": DEAD_LETTER_GROUP,
            "requeued_count": self.requeued_count,
            "terminal_failure_count": self.terminal_count,
            "last_message_id": self.last_message_id,
        }

    @staticmethod
    def _original_stream(payload: dict) -> str:
        value = payload.get("original_stream") or payload.get("source_stream") or ""
        return str(value)

    @staticmethod
    def _retry_delay(payload: dict) -> float:
        try:
            delay = float(payload.get("retry_after_seconds", DEFAULT_RETRY_DELAY_SECONDS))
        except (TypeError, ValueError):
            delay = DEFAULT_RETRY_DELAY_SECONDS
        return max(0.0, min(delay, MAX_RETRY_DELAY_SECONDS))

    def _is_terminal(self, payload: dict) -> bool:
        return get_retry_count(payload) > get_max_retries(payload)

    def _build_requeue_event(self, payload: dict, event_name: str) -> dict:
        original = payload.get("original_event")
        if isinstance(original, dict):
            event = dict(original)
        else:
            event = {}
        event["event"] = event_name
        event["task_id"] = event.get("task_id") or payload.get("task_id", "unknown")
        event["workflow_id"] = event.get("workflow_id") or payload.get("workflow_id", "")
        event["retry_count"] = get_retry_count(payload)
        event["max_retries"] = get_max_retries(payload)
        event["original_stream"] = self._original_stream(payload)
        event["retry_requeued_at"] = _utcnow_iso()
        return event

    def _build_terminal_event(self, payload: dict, message_id: str) -> dict:
        return {
            "event": "retry.terminal_failure",
            "task_id": payload.get("task_id", "unknown"),
            "workflow_id": payload.get("workflow_id", ""),
            "original_stream": self._original_stream(payload),
            "original_message_id": message_id,
            "terminal_failure": True,
            "retry_count": get_retry_count(payload),
            "max_retries": get_max_retries(payload),
            "failed_at": payload.get("failed_at"),
            "failure_reason": payload.get("failure_reason", ""),
            "marked_terminal_at": _utcnow_iso(),
        }

    async def handle(self, message_id: str, payload: dict) -> dict:
        """Process one dead-letter event: terminal-mark or schedule a requeue."""
        self.last_message_id = message_id
        base_attrs = {
            "service.name": "retry-scheduler",
            "agent": "retry-scheduler",
            "task_id": str(payload.get("task_id", "")),
            "workflow_id": str(payload.get("workflow_id", "")),
            "stream": self._original_stream(payload),
            "redis.message_id": message_id,
        }
        with start_span("retry.consume_deadletter", **base_attrs):
            if self._is_terminal(payload):
                with start_span(
                    "retry.terminal_failure",
                    **{**base_attrs, "event_type": "retry.terminal_failure"},
                ):
                    with contextlib.suppress(Exception):
                        await self.bus.publish_event(
                            TERMINAL_FAILURE_STREAM,
                            self._build_terminal_event(payload, message_id),
                        )
                    self.terminal_count += 1
                    RETRY_TOTAL.labels(kind="terminal_failure").inc()
                    incident_id = await self._on_terminal_failure(payload, message_id)
                    return {
                        "action": "terminal_failure",
                        "message_id": message_id,
                        "incident_id": incident_id,
                    }
            delay = self._retry_delay(payload)
            if delay > 0:
                await asyncio.sleep(delay)
            target = self._original_stream(payload)
            if not target:
                return {"action": "no_original_stream", "message_id": message_id}
            with start_span("retry.requeue", **{**base_attrs, "event_type": "retry.requeued"}):
                event = self._build_requeue_event(payload, "retry.requeued")
                await self.bus.publish_event(target, event)
                self.requeued_count += 1
                RETRY_TOTAL.labels(kind="requeued").inc()
                return {"action": "requeued", "stream": target, "message_id": message_id}

    async def _on_terminal_failure(self, payload: dict, message_id: str) -> str | None:
        """Side-effects fired after the terminal_failure event is published.

        Creates an incident_records row, flips the matching workflow_state to
        ``failed``, publishes a workflow.failed notification, and records an
        audit event. Each step is best-effort and isolated: a failure here
        must NEVER crash the retry-scheduler consumer loop. Returns the
        incident_id when the row was created.
        """
        task_id = str(payload.get("task_id", "")).strip() or None
        workflow_id = str(payload.get("workflow_id", "")).strip() or None
        failure_reason = str(payload.get("failure_reason", "")) or "terminal failure"
        original_stream = self._original_stream(payload)
        details = {
            "original_stream": original_stream,
            "retry_count": get_retry_count(payload),
            "max_retries": get_max_retries(payload),
            "failure_reason": failure_reason,
            "failed_at": payload.get("failed_at"),
            "original_event": payload.get("original_event"),
            "original_message_id": message_id,
        }

        workflow_updated = False
        with contextlib.suppress(Exception):
            workflow_updated = await self._mark_workflow_failed(task_id, failure_reason)
        if task_id and not workflow_updated:
            details["workflow_not_found"] = True

        incident_id: str | None = None
        with contextlib.suppress(Exception):
            incident = await IncidentStore().create_incident(
                severity="sev2",
                source="retry-scheduler",
                summary=(
                    f"terminal failure: max retries exceeded on {original_stream or 'unknown'} "
                    f"(task={task_id or 'unknown'})"
                ),
                task_id=task_id,
                workflow_id=workflow_id,
                details=details,
            )
            incident_id = incident.incident_id

        # workflow.failed notification + audit are tied to the task_id so the
        # existing dashboards can correlate them with workflow_states.
        notification_id = task_id or workflow_id or message_id
        with contextlib.suppress(Exception):
            await send_notification(
                notification_id,
                "workflow.failed",
                f"workflow {task_id or workflow_id or message_id} terminal failure: {failure_reason}",
            )
        with contextlib.suppress(Exception):
            await AuditHttpClient().record_event(
                task_id=task_id or incident_id or message_id,
                agent="retry-scheduler",
                decision_type="workflow_failed",
                summary=f"retry-scheduler marked {task_id or message_id} as terminal failure",
                result="failed",
                artifact_refs={
                    "incident_id": incident_id or "",
                    "original_stream": original_stream,
                    "original_message_id": message_id,
                },
                workflow_id=workflow_id or "",
            )
        with contextlib.suppress(Exception):
            WORKFLOW_FAILED_TOTAL.labels(reason="failed").inc()
        return incident_id

    async def _mark_workflow_failed(self, task_id: str | None, failure_reason: str) -> bool:
        """Flip the matching workflow_states row to ``failed``.

        Returns True only when an existing workflow row was updated. Mock-safe:
        if the workflow is already in a terminal stage (completed / canceled /
        aborted) we don't overwrite it.
        """
        if not task_id:
            return False
        store = WorkflowStore()
        workflow = await store.get_workflow_state(task_id)
        if workflow is None:
            return False
        current = str(workflow.get("stage") or "")
        if current in ("completed", "canceled", "aborted", "failed", "rejected"):
            # Already terminal — don't churn the row, but report the workflow
            # was found so the incident doesn't claim workflow_not_found.
            return True
        state = dict(workflow["state"]) if isinstance(workflow["state"], dict) else {}
        execution_result = (
            dict(workflow["execution_result"])
            if isinstance(workflow["execution_result"], dict)
            else {}
        )
        timestamp = _utcnow_iso()
        execution_result["status"] = "failed"
        execution_result["failure_reason"] = failure_reason
        execution_result["production_executed"] = False
        execution_result["failed_at"] = timestamp
        state["stage"] = "failed"
        state["failed_at"] = timestamp
        state["failure_reason"] = failure_reason
        state["execution_result"] = execution_result
        updated = await store.update_workflow_state(
            task_id,
            stage="failed",
            state=state,
            approval_required=bool(workflow["approval_required"]),
            approval_status=str(workflow["approval_status"] or "none"),
            risk_level=str(workflow["risk_level"] or "unknown"),
            execution_result=execution_result,
        )
        return updated is not None

    async def _safe_handle(self, message_id: str, payload: dict) -> None:
        try:
            await self.handle(message_id, payload)
        except Exception:
            pass  # a transient Redis error must not stop the scheduler loop

    async def list_dead_letters(self, count: int = 20) -> list[dict]:
        entries = await self.bus.client.xrevrange(DEAD_LETTER_STREAM, "+", "-", count=count)
        out: list[dict] = []
        for entry_id, fields in entries:
            raw = fields.get("data", "{}")
            try:
                payload = json.loads(raw)
            except (ValueError, TypeError):
                payload = {"raw": raw}
            out.append({"id": entry_id, "payload": payload})
        return out

    async def replay(self, message_id: str) -> dict:
        """Manually replay one dead-letter entry back to its original stream."""
        entries = await self.bus.client.xrange(DEAD_LETTER_STREAM, message_id, message_id)
        if not entries:
            raise KeyError(message_id)
        _entry_id, fields = entries[0]
        raw = fields.get("data", "{}")
        try:
            payload = json.loads(raw)
        except (ValueError, TypeError) as exc:
            raise KeyError(message_id) from exc
        target = self._original_stream(payload)
        if not target:
            raise KeyError(message_id)
        with start_span(
            "retry.manual_replay",
            **{
                "service.name": "retry-scheduler",
                "agent": "retry-scheduler",
                "task_id": str(payload.get("task_id", "")),
                "workflow_id": str(payload.get("workflow_id", "")),
                "stream": target,
                "redis.message_id": message_id,
                "event_type": "retry.manual_replay",
            },
        ):
            event = self._build_requeue_event(payload, "retry.manual_replay")
            published_id = await self.bus.publish_event(target, event)
            RETRY_TOTAL.labels(kind="manual_replay").inc()
            return {
                "replayed": True,
                "message_id": message_id,
                "stream": target,
                "published_id": published_id,
                "task_id": event.get("task_id"),
            }

    async def run(self, stop_event: asyncio.Event) -> None:
        """Consume stream.deadletter until stop_event is set."""
        self.running = True
        try:
            while not stop_event.is_set():
                try:
                    events = await self.bus.consume_events(
                        DEAD_LETTER_STREAM,
                        DEAD_LETTER_GROUP,
                        DEAD_LETTER_CONSUMER,
                        count=10,
                        block_ms=2000,
                    )
                    for event in events:
                        message_id = event["id"]
                        payload = event["event"]
                        task = asyncio.create_task(self._safe_handle(message_id, payload))
                        self._tasks.add(task)
                        task.add_done_callback(self._tasks.discard)
                        await self.bus.ack_event(DEAD_LETTER_STREAM, DEAD_LETTER_GROUP, message_id)
                except asyncio.CancelledError:
                    break
                except Exception:
                    await asyncio.sleep(1)
        finally:
            self.running = False
            for task in list(self._tasks):
                task.cancel()
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def close(self) -> None:
        await self.bus.close()
