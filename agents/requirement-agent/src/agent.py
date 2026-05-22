import asyncio

from shared.sdk.audit.client import AuditClient
from shared.sdk.base_agent.base import BaseAgent
from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from shared.sdk.notifications.client import send_notification

REQUIREMENTS_STREAM = "stream.requirements"
DEVELOPMENT_STREAM = "stream.development"
REQUIREMENT_GROUP = "requirement-agent-group"


class RequirementAgent(BaseAgent):
    """Consumes normalized tasks from stream.requirements, produces a mock
    requirement_spec artifact, and publishes a requirement.completed event to
    stream.development. Writes an audit event and publishes a notification.

    Performs no LLM, GitHub, Slack, or production calls.
    """

    name = "requirement-agent"

    def __init__(self, event_bus: RedisStreamEventBus | None = None) -> None:
        bus = event_bus or RedisStreamEventBus()
        super().__init__(audit_client=AuditClient(event_bus=bus))
        self.bus = bus
        self.input_stream = REQUIREMENTS_STREAM
        self.output_stream = DEVELOPMENT_STREAM
        self.group = REQUIREMENT_GROUP
        self.consumer = "requirement-agent-1"
        self.processed_count = 0
        self.last_task_id: str | None = None
        self.running = False

    async def receive_task(self, task: dict) -> dict:
        request = task.get("request", {})
        return {
            "task_id": task.get("task_id", "unknown"),
            "request_type": task.get("request_type") or request.get("type", "unknown"),
            "request": request,
        }

    async def analyze(self, context: dict) -> dict:
        request = context.get("request", {})
        summary = request.get("description") or f"requirement analysis for {context['task_id']}"
        return {**context, "summary": summary}

    async def execute(self, plan: dict) -> dict:
        """Produce a mock requirement_spec artifact and publish requirement.completed."""
        spec = {
            "type": "requirement_spec",
            "task_id": plan["task_id"],
            "request_type": plan.get("request_type", "unknown"),
            "summary": plan.get("summary", ""),
            "acceptance_criteria": [
                "input is validated",
                "the happy path is covered",
                "errors are handled gracefully",
            ],
            "produced_by": self.name,
            "mock": True,
        }
        message = {
            "event": "requirement.completed",
            "task_id": plan["task_id"],
            "artifact": spec,
            "produced_by": self.name,
        }
        message_id = await self.bus.publish_event(self.output_stream, message)
        return {"published_id": message_id, "artifact": spec}

    async def process(self, payload: dict) -> dict:
        received = await self.receive_task(payload)
        analysis = await self.analyze(received)
        result = await self.execute(analysis)
        task_id = received["task_id"]
        self.processed_count += 1
        self.last_task_id = task_id
        await self.write_audit(
            {
                "decision_type": "requirement",
                "summary": f"requirement-agent produced requirement_spec for {task_id}",
                "result": "requirement.completed",
                "task_id": task_id,
                "artifact_refs": {"artifact": "requirement_spec"},
            }
        )
        await send_notification(
            task_id, "requirement.completed", f"requirement-agent completed task {task_id}"
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
