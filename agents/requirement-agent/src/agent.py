from shared.sdk.base_agent.stream_agent import StreamAgent


class RequirementAgent(StreamAgent):
    """Consumes normalized tasks from stream.requirements, produces a mock
    requirement_spec artifact, and publishes a requirement.completed event to
    stream.development. Records an agent execution, an audit event, and a
    notification. Makes no LLM / GitHub / Slack calls.
    """

    name = "requirement-agent"
    input_stream = "stream.requirements"
    output_stream = "stream.development"
    group = "requirement-agent-group"
    consumer = "requirement-agent-1"

    def build_artifact(self, payload: dict) -> dict:
        """Produce a mock requirement_spec artifact (no real LLM)."""
        task_id = str(payload.get("task_id", "unknown"))
        request = payload.get("request", {})
        summary = request.get("description") or f"requirement analysis for {task_id}"
        return {
            "type": "requirement_spec",
            "task_id": task_id,
            "request_type": payload.get("request_type") or request.get("type", "unknown"),
            "summary": summary,
            "acceptance_criteria": [
                "input is validated",
                "the happy path is covered",
                "errors are handled gracefully",
            ],
            "produced_by": self.name,
            "mock": True,
        }

    async def handle(self, payload: dict) -> dict:
        artifact = self.build_artifact(payload)
        task_id = artifact["task_id"]
        message = {
            "event": "requirement.completed",
            **self.correlation_ids(payload),
            "request": payload.get("request", {}),
            "artifact": artifact,
            "produced_by": self.name,
        }
        await self.bus.publish_event(self.output_stream, message)
        return {
            "task_id": task_id,
            "decision_type": "requirement",
            "summary": f"requirement-agent produced requirement_spec for {task_id}",
            "result": "requirement.completed",
            "artifact_refs": {"artifact": "requirement_spec"},
            "event_type": "requirement.completed",
            "message": f"requirement-agent completed task {task_id}",
        }
