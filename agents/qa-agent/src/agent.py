from shared.sdk.base_agent.stream_agent import StreamAgent
from shared.sdk.observability.metrics import AGENT_DISCUSSIONS_TOTAL
from shared.sdk.task_execution import TaskExecutionStore


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

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._task_store = TaskExecutionStore()

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
            **self.correlation_ids(payload),
            # Forward the original request so the downstream devops-agent
            # can read e.g. ``request.github.{enabled,repo,base_branch,dry_run}``.
            "request": payload.get("request", {}),
            "artifact": report,
            "produced_by": self.name,
        }
        await self.publish_next(message)
        workflow_id = str(payload.get("workflow_id", "")) or None
        try:
            await self._task_store.add_agent_discussion(
                task_id=task_id,
                workflow_id=workflow_id,
                agent=self.name,
                role="qa",
                message_type="validation_note",
                content=(
                    f"qa-agent produced a mock test_report for {task_id}; " "no real tests run."
                ),
                confidence=0.7,
                references={"artifact": "test_report", "mock": True},
            )
            AGENT_DISCUSSIONS_TOTAL.labels(agent=self.name, message_type="validation_note").inc()
        except Exception:
            pass
        return {
            "task_id": task_id,
            "decision_type": "qa",
            "summary": f"qa-agent produced test_report for {task_id}",
            "result": "qa.completed",
            "artifact_refs": {"artifact": "test_report"},
            "event_type": "qa.completed",
            "message": f"qa-agent completed task {task_id}",
        }
