from shared.sdk.base_agent.stream_agent import StreamAgent


class DevelopmentAgent(StreamAgent):
    """Consumes requirement specs from stream.development, produces a mock
    code_change artifact, and publishes a development.completed event to
    stream.qa. Records an agent execution, an audit event, and a notification.
    Makes no LLM / GitHub / Slack calls and produces no real code.
    """

    name = "development-agent"
    input_stream = "stream.development"
    output_stream = "stream.qa"
    group = "development-agent-group"
    consumer = "development-agent-1"

    def build_artifact(self, payload: dict) -> dict:
        """Produce a mock code_change artifact (no real code is written)."""
        task_id = str(payload.get("task_id", "unknown"))
        return {
            "artifact_type": "code_change",
            "task_id": task_id,
            "files_changed": [],
            "summary": f"mock code change for {task_id}",
            "produced_by": self.name,
            "mock": True,
        }

    async def handle(self, payload: dict) -> dict:
        artifact = self.build_artifact(payload)
        task_id = artifact["task_id"]
        message = {
            "event": "development.completed",
            **self.correlation_ids(payload),
            "artifact": artifact,
            "produced_by": self.name,
        }
        await self.bus.publish_event(self.output_stream, message)
        return {
            "task_id": task_id,
            "decision_type": "development",
            "summary": f"development-agent produced code_change for {task_id}",
            "result": "development.completed",
            "artifact_refs": {"artifact": "code_change"},
            "event_type": "development.completed",
            "message": f"development-agent completed task {task_id}",
        }
