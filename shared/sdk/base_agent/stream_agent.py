import asyncio
from abc import abstractmethod

from shared.sdk.agent_execution.store import AgentExecutionStore
from shared.sdk.audit.client import AuditClient
from shared.sdk.base_agent.base import BaseAgent
from shared.sdk.event_bus.redis_streams import (
    RedisStreamEventBus,
    is_retry_exhausted,
    with_incremented_retry,
)
from shared.sdk.notifications.client import send_notification


class StreamAgent(BaseAgent):
    """A BaseAgent that consumes one Redis stream and transforms each message.

    For every message it records an agent_executions row (started -> completed
    or failed), writes an audit event, and publishes a notification. Concrete
    agents implement handle(); they make no LLM / GitHub / Slack / Kubernetes /
    cloud calls and execute no production actions.
    """

    input_stream: str = ""
    output_stream: str = ""
    group: str = ""
    consumer: str = ""

    def __init__(self, event_bus: RedisStreamEventBus | None = None) -> None:
        bus = event_bus or RedisStreamEventBus()
        super().__init__(audit_client=AuditClient(event_bus=bus))
        self.bus = bus
        self.execution_store = AgentExecutionStore()
        self.processed_count = 0
        self.failed_count = 0
        self.dead_letter_count = 0
        self.last_task_id: str | None = None
        self.running = False

    @staticmethod
    def correlation_ids(payload: dict) -> dict:
        """The task/workflow ids every pipeline message must carry forward."""
        return {
            "task_id": str(payload.get("task_id", "unknown")),
            "workflow_id": payload.get("workflow_id", ""),
        }

    # BaseAgent abstract methods — stream agents transform inside handle().
    async def receive_task(self, task: dict) -> dict:
        return dict(task)

    async def analyze(self, context: dict) -> dict:
        return dict(context)

    async def execute(self, plan: dict) -> dict:
        return dict(plan)

    @abstractmethod
    async def handle(self, payload: dict) -> dict:
        """Transform one message and (optionally) publish to the output stream.

        Returns a descriptor dict with: task_id, decision_type, summary, result,
        artifact_refs, event_type, message, and optional execution_metadata.
        """

    async def process(self, payload: dict) -> dict:
        task_id = str(payload.get("task_id", "unknown"))
        execution_id = await self._start_execution(task_id)
        try:
            result = await self.handle(payload)
        except Exception as exc:
            self.failed_count += 1
            await self._fail_execution(execution_id, str(exc))
            raise
        self.processed_count += 1
        self.last_task_id = task_id
        await self._complete_execution(execution_id, result)
        await self.write_audit(
            {
                "decision_type": result.get("decision_type", self.name),
                "summary": result.get("summary", ""),
                "result": result.get("result", ""),
                "task_id": task_id,
                "artifact_refs": result.get("artifact_refs", {}),
            }
        )
        await send_notification(
            task_id,
            result.get("event_type", f"{self.name}.completed"),
            result.get("message", result.get("summary", "")),
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
                        payload = event["event"]
                        try:
                            await self.process(payload)
                        except Exception as exc:
                            await self._handle_failure(payload, exc)
                        await self.bus.ack_event(self.input_stream, self.group, event["id"])
                except asyncio.CancelledError:
                    break
                except Exception:
                    await asyncio.sleep(1)
        finally:
            self.running = False

    async def _handle_failure(self, payload: dict, exc: Exception) -> None:
        """Retry a failed message; dead-letter it once its retries are exhausted.

        This is the retry / dead-letter foundation — there is no separate retry
        scheduler. A failed message is re-published to the input stream with an
        incremented retry_count; once retry_count reaches max_retries it goes to
        stream.deadletter instead.
        """
        attempted = with_incremented_retry(payload)
        try:
            if is_retry_exhausted(attempted):
                await self.bus.publish_dead_letter(self.input_stream, attempted, str(exc))
                self.dead_letter_count += 1
            else:
                await self.bus.publish_event(self.input_stream, attempted)
        except Exception:
            pass  # a transient Redis error must not stop the consumer loop

    def status(self) -> dict:
        return {
            "agent": self.name,
            "running": self.running,
            "input_stream": self.input_stream,
            "output_stream": self.output_stream,
            "group": self.group,
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "dead_letter_count": self.dead_letter_count,
            "last_task_id": self.last_task_id,
        }

    async def close(self) -> None:
        await self.bus.close()

    async def _start_execution(self, task_id: str) -> str | None:
        try:
            execution = await self.execution_store.create_execution(task_id, self.name)
            return str(execution["execution_id"])
        except Exception:
            return None

    async def _complete_execution(self, execution_id: str | None, result: dict) -> None:
        if execution_id is None:
            return
        metadata = result.get("execution_metadata") or {"summary": result.get("summary", "")}
        try:
            await self.execution_store.complete_execution(execution_id, metadata=metadata)
        except Exception:
            pass

    async def _fail_execution(self, execution_id: str | None, error: str) -> None:
        if execution_id is None:
            return
        try:
            await self.execution_store.fail_execution(execution_id, error)
        except Exception:
            pass
