import asyncio

from shared.sdk.audit.client import AuditClient
from shared.sdk.base_agent.base import BaseAgent
from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from shared.sdk.notifications.client import send_notification

TASKS_STREAM = "stream.tasks"
REQUIREMENTS_STREAM = "stream.requirements"
INTAKE_GROUP = "intake-agent-group"


class IntakeAgent(BaseAgent):
    """Consumes raw tasks from stream.tasks, normalizes them, and forwards them
    to stream.requirements. Writes an audit event and publishes a notification.

    Performs no LLM, GitHub, Slack, or production calls.
    """

    name = "intake-agent"

    def __init__(self, event_bus: RedisStreamEventBus | None = None) -> None:
        bus = event_bus or RedisStreamEventBus()
        super().__init__(audit_client=AuditClient(event_bus=bus))
        self.bus = bus
        self.input_stream = TASKS_STREAM
        self.output_stream = REQUIREMENTS_STREAM
        self.group = INTAKE_GROUP
        self.consumer = "intake-agent-1"
        self.processed_count = 0
        self.last_task_id: str | None = None
        self.running = False

    async def receive_task(self, task: dict) -> dict:
        """Normalize an incoming raw task into the standard intake form."""
        return {
            "task_id": task.get("task_id", "unknown"),
            "source": task.get("source", "unknown"),
            "request": task.get("request", {}),
            "normalized": True,
            "received_by": self.name,
        }

    async def analyze(self, context: dict) -> dict:
        request = context.get("request", {})
        return {
            **context,
            "request_type": request.get("type", "unknown"),
            "description": request.get("description", ""),
        }

    async def execute(self, plan: dict) -> dict:
        """Forward the normalized task to the requirement stage."""
        message = {
            "event": "task.intake_completed",
            "task_id": plan["task_id"],
            "source": plan.get("source", "unknown"),
            "request": plan.get("request", {}),
            "request_type": plan.get("request_type", "unknown"),
            "normalized_by": self.name,
        }
        message_id = await self.bus.publish_event(self.output_stream, message)
        return {"published_id": message_id, "message": message}

    async def process(self, payload: dict) -> dict:
        normalized = await self.receive_task(payload)
        analysis = await self.analyze(normalized)
        result = await self.execute(analysis)
        task_id = analysis["task_id"]
        self.processed_count += 1
        self.last_task_id = task_id
        await self.write_audit(
            {
                "decision_type": "intake",
                "summary": f"intake-agent normalized task {task_id}",
                "result": "forwarded_to_requirements",
                "task_id": task_id,
                "artifact_refs": {"request_type": analysis.get("request_type")},
            }
        )
        await send_notification(
            task_id, "agent.intake_completed", f"intake-agent processed task {task_id}"
        )
        return result

    async def run_consumer(self, stop_event: asyncio.Event) -> None:
        """Consume the input stream until stop_event is set (Redis consumer group)."""
        self.running = True
        try:
            while not stop_event.is_set():
                try:
                    events = await self.bus.consume_events(
                        self.input_stream, self.group, self.consumer, count=10, block_ms=2000
                    )
                    for event in events:
                        try:
                            await self.process(event["event"])
                        except Exception:
                            pass  # one bad message must not stop the loop
                        await self.bus.ack_event(self.input_stream, self.group, event["id"])
                except asyncio.CancelledError:
                    break
                except Exception:
                    await asyncio.sleep(1)
        finally:
            self.running = False

    def status(self) -> dict:
        return {
            "agent": self.name,
            "running": self.running,
            "input_stream": self.input_stream,
            "output_stream": self.output_stream,
            "group": self.group,
            "processed_count": self.processed_count,
            "last_task_id": self.last_task_id,
        }

    async def close(self) -> None:
        await self.bus.close()
