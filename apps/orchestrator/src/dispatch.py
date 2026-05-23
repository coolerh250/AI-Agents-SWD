import contextlib
from datetime import datetime, timezone

from shared.sdk.event_bus.redis_streams import RedisStreamEventBus

TASKS_STREAM = "stream.tasks"


def build_dispatch_event(task_id: str, workflow_id: str, request: dict, source: str) -> dict:
    """Build the task dispatch event the orchestrator publishes to stream.tasks."""
    return {
        "event": "task.created",
        "task_id": task_id,
        "workflow_id": workflow_id,
        "request": request,
        "source": source,
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }


async def dispatch_task(task_id: str, workflow_id: str, request: dict, source: str) -> bool:
    """Publish a task dispatch event to stream.tasks. Returns True on success.

    Dispatching hands the task to the agent pipeline (intake -> requirement ->
    development -> qa -> devops). It runs no production action.
    """
    event = build_dispatch_event(task_id, workflow_id, request, source)
    bus = RedisStreamEventBus()
    try:
        await bus.publish_event(TASKS_STREAM, event)
        return True
    except Exception:
        return False
    finally:
        with contextlib.suppress(Exception):
            await bus.close()
