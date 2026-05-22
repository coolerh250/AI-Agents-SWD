from shared.sdk.base_agent.stream_agent import StreamAgent


class IntakeAgent(StreamAgent):
    """Consumes raw tasks from stream.tasks, normalizes them, and forwards them
    to stream.requirements. Records an agent execution, an audit event, and a
    notification for every message. Makes no LLM / GitHub / Slack calls.
    """

    name = "intake-agent"
    input_stream = "stream.tasks"
    output_stream = "stream.requirements"
    group = "intake-agent-group"
    consumer = "intake-agent-1"

    def build_message(self, payload: dict) -> dict:
        """Normalize a raw task into the standard requirement-stage message."""
        task_id = str(payload.get("task_id", "unknown"))
        request = payload.get("request", {})
        return {
            "event": "task.intake_completed",
            "task_id": task_id,
            "source": payload.get("source", "unknown"),
            "request": request,
            "request_type": request.get("type", "unknown"),
            "normalized_by": self.name,
        }

    async def handle(self, payload: dict) -> dict:
        message = self.build_message(payload)
        task_id = message["task_id"]
        await self.bus.publish_event(self.output_stream, message)
        return {
            "task_id": task_id,
            "decision_type": "intake",
            "summary": f"intake-agent normalized task {task_id}",
            "result": "forwarded_to_requirements",
            "artifact_refs": {"request_type": message["request_type"]},
            "event_type": "agent.intake_completed",
            "message": f"intake-agent processed task {task_id}",
        }
