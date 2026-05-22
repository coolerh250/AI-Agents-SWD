from shared.sdk.base_agent.stream_agent import StreamAgent


class QAAgent(StreamAgent):
    """Consumes code changes from stream.qa, produces a mock test_report, and
    publishes a qa.completed event to stream.deployments. Records an agent
    execution, an audit event, and a notification. Runs no real tests.
    """

    name = "qa-agent"
    input_stream = "stream.qa"
    output_stream = "stream.deployments"
    group = "qa-agent-group"
    consumer = "qa-agent-1"

    def build_report(self, payload: dict) -> dict:
        """Produce a mock test_report (no real tests are run)."""
        task_id = str(payload.get("task_id", "unknown"))
        return {
            "artifact_type": "test_report",
            "task_id": task_id,
            "status": "passed",
            "tests_run": 0,
            "produced_by": self.name,
            "mock": True,
        }

    async def handle(self, payload: dict) -> dict:
        report = self.build_report(payload)
        task_id = report["task_id"]
        message = {
            "event": "qa.completed",
            "task_id": task_id,
            "artifact": report,
            "produced_by": self.name,
        }
        await self.bus.publish_event(self.output_stream, message)
        return {
            "task_id": task_id,
            "decision_type": "qa",
            "summary": f"qa-agent produced test_report for {task_id}",
            "result": "qa.completed",
            "artifact_refs": {"artifact": "test_report"},
            "event_type": "qa.completed",
            "message": f"qa-agent completed task {task_id}",
        }
