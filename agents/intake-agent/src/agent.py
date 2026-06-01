from shared.sdk.base_agent.stream_agent import StreamAgent
from shared.sdk.observability.metrics import AGENT_DISCUSSIONS_TOTAL
from shared.sdk.task_execution import TaskExecutionStore


class IntakeAgent(StreamAgent):
    """Consumes raw tasks from stream.tasks, normalizes them, and forwards them
    to stream.requirements. Records an agent execution, an audit event, and a
    notification for every message. Makes no LLM / GitHub / Slack calls.

    Stage 27: also appends an intake-summary row to ``agent_discussions``
    so the inter-agent discussion log starts at the first hop.
    """

    name = "intake-agent"
    input_stream = "stream.tasks"
    output_stream = "stream.requirements"
    group = "intake-agent-group"
    consumer = "intake-agent-1"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._task_store = TaskExecutionStore()

    def build_message(self, payload: dict) -> dict:
        request = payload.get("request", {})
        return {
            "event": "task.intake_completed",
            **self.correlation_ids(payload),
            "source": payload.get("source", "unknown"),
            "request": request,
            "request_type": request.get("type", "unknown"),
            "normalized_by": self.name,
        }

    async def handle(self, payload: dict) -> dict:
        message = self.build_message(payload)
        task_id = message["task_id"]
        workflow_id = str(payload.get("workflow_id", "")) or None
        request = payload.get("request", {}) if isinstance(payload.get("request"), dict) else {}
        description = str(request.get("description") or "")
        await self.publish_next(message)
        # Stage 27 — short summary row in agent_discussions.
        try:
            await self._task_store.add_agent_discussion(
                task_id=task_id,
                workflow_id=workflow_id,
                agent=self.name,
                role="intake",
                message_type="analysis",
                content=(
                    f"intake-agent normalized task {task_id}; "
                    f"request_type={message['request_type']}, "
                    f"description={description[:120]}"
                ),
                confidence=0.9,
                references={"normalized_by": self.name},
            )
            AGENT_DISCUSSIONS_TOTAL.labels(agent=self.name, message_type="analysis").inc()
        except Exception:
            # Persistence failures must not break the pipeline.
            pass
        return {
            "task_id": task_id,
            "decision_type": "intake",
            "summary": f"intake-agent normalized task {task_id}",
            "result": "forwarded_to_requirements",
            "artifact_refs": {"request_type": message["request_type"]},
            "event_type": "agent.intake_completed",
            "message": f"intake-agent processed task {task_id}",
        }
