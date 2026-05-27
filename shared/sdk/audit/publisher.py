"""Thin stream-based audit publisher used by services and agents.

Stage 19 unifies the audit path:

    producer  --publish-->  stream.audit  --consume-->  audit-worker  -->  audit_logs

This module is the producer side. It is intentionally small so the existing
direct-HTTP writers (audit-service POST handler retained for compatibility)
and any future ad-hoc producers can share one entry point.

The publisher is best-effort: a Redis hiccup must NOT propagate up to the
caller's hot path. Failures are swallowed; the caller can still write through
``AuditHttpClient.record_event`` if it needs a synchronous receipt.
"""

from __future__ import annotations

import contextlib
from typing import Any

from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from shared.sdk.observability.tracing import start_span

AUDIT_STREAM = "stream.audit"


async def publish_audit_event(
    *,
    task_id: str | None,
    agent: str,
    decision_type: str,
    summary: str,
    result: str,
    artifact_refs: dict[str, Any] | None = None,
    workflow_id: str = "",
    event_bus: RedisStreamEventBus | None = None,
    close_bus: bool | None = None,
) -> str | None:
    """Publish one audit event onto ``stream.audit``.

    Returns the Redis ``XADD`` id when the publish succeeded, or ``None``
    when it failed (the message was effectively dropped). Errors are
    suppressed — the caller's hot path must not be affected by an audit-stream
    glitch.
    """
    payload: dict[str, Any] = {
        "task_id": task_id or "unknown",
        "workflow_id": workflow_id or "",
        "agent": agent,
        "decision_type": decision_type,
        "summary": summary,
        "result": result,
        "artifact_refs": artifact_refs or {},
    }
    owns_bus = event_bus is None
    bus = event_bus or RedisStreamEventBus()
    should_close = close_bus if close_bus is not None else owns_bus
    message_id: str | None = None
    try:
        with start_span(
            "audit.publish",
            **{
                "service.name": agent,
                "agent": agent,
                "stream": AUDIT_STREAM,
                "audit.decision_type": decision_type,
                "task_id": payload["task_id"],
                "workflow_id": payload["workflow_id"],
            },
        ):
            message_id = await bus.publish_event(AUDIT_STREAM, payload)
    except Exception:
        message_id = None
    finally:
        if should_close:
            with contextlib.suppress(Exception):
                await bus.close()
    return message_id
