from shared.sdk.base_agent.stream_agent import StreamAgent
from shared.sdk.observability.metrics import AGENT_DISCUSSIONS_TOTAL
from shared.sdk.task_execution import TaskExecutionStore


class SimulatedFailure(RuntimeError):
    """Raised by development-agent when the request asks for a controlled failure."""


class DevelopmentAgent(StreamAgent):
    """Consumes requirement specs from stream.development, produces a mock
    code_change artifact, and publishes a development.completed event to
    stream.qa. Records an agent execution, an audit event, and a notification.
    Makes no LLM / GitHub / Slack calls and produces no real code.

    Honors a controlled-failure switch (``request.simulate_failure: true``) so
    the retry / dead-letter foundation can be exercised end-to-end. The failure
    only raises within ``handle`` — it never crashes the consumer loop.
    """

    name = "development-agent"
    input_stream = "stream.development"
    output_stream = "stream.qa"
    group = "development-agent-group"
    consumer = "development-agent-1"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._task_store = TaskExecutionStore()

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

    @staticmethod
    def _should_simulate_failure(payload: dict) -> bool:
        request = payload.get("request") or {}
        if not isinstance(request, dict):
            return False
        return bool(request.get("simulate_failure"))

    async def handle(self, payload: dict) -> dict:
        if self._should_simulate_failure(payload):
            task_id = str(payload.get("task_id", "unknown"))
            raise SimulatedFailure(
                f"development-agent simulated failure for {task_id} " "(request.simulate_failure)"
            )
        artifact = self.build_artifact(payload)
        task_id = artifact["task_id"]
        message = {
            "event": "development.completed",
            **self.correlation_ids(payload),
            "request": payload.get("request", {}),
            "artifact": artifact,
            "produced_by": self.name,
        }
        await self.publish_next(message)
        workflow_id = str(payload.get("workflow_id", "")) or None
        try:
            await self._task_store.add_agent_discussion(
                task_id=task_id,
                workflow_id=workflow_id,
                agent=self.name,
                role="developer",
                message_type="execution_plan",
                content=(
                    f"development-agent produced a mock code_change for {task_id}; "
                    "no real files written, dry-run only."
                ),
                confidence=0.7,
                references={"artifact": "code_change", "mock": True},
            )
            AGENT_DISCUSSIONS_TOTAL.labels(agent=self.name, message_type="execution_plan").inc()
        except Exception:
            pass
        return {
            "task_id": task_id,
            "decision_type": "development",
            "summary": f"development-agent produced code_change for {task_id}",
            "result": "development.completed",
            "artifact_refs": {"artifact": "code_change"},
            "event_type": "development.completed",
            "message": f"development-agent completed task {task_id}",
        }
