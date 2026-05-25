import contextlib
from datetime import datetime, timezone

from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from shared.sdk.observability.tracing import inject_trace_context

TASKS_STREAM = "stream.tasks"


def build_dispatch_event(
    task_id: str,
    workflow_id: str,
    request: dict,
    source: str,
    trace_id: str = "",
) -> dict:
    """Build the task dispatch event the orchestrator publishes to stream.tasks."""
    event: dict = {
        "event": "task.created",
        "task_id": task_id,
        "workflow_id": workflow_id,
        "request": request,
        "source": source,
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }
    inject_trace_context(event, parent_trace_id=trace_id or None)
    return event


async def dispatch_task(
    task_id: str,
    workflow_id: str,
    request: dict,
    source: str,
    trace_id: str = "",
) -> bool:
    """Publish a task dispatch event to stream.tasks. Returns True on success.

    Dispatching hands the task to the agent pipeline (intake -> requirement ->
    development -> qa -> devops). It runs no production action. The workflow's
    trace_id is propagated onto the dispatch event so every downstream stage
    shares one distributed trace.
    """
    event = build_dispatch_event(task_id, workflow_id, request, source, trace_id=trace_id)
    bus = RedisStreamEventBus()
    try:
        await bus.publish_event(TASKS_STREAM, event)
        return True
    except Exception:
        return False
    finally:
        with contextlib.suppress(Exception):
            await bus.close()
