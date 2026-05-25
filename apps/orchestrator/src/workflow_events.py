import asyncio
import contextlib
from datetime import datetime

from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from shared.sdk.http_clients.audit_http_client import AuditHttpClient
from shared.sdk.notifications.client import send_notification
from shared.sdk.observability.metrics import (
    WORKFLOW_COMPLETED_TOTAL,
    WORKFLOW_DURATION_SECONDS,
)
from shared.sdk.workflow_store.store import WorkflowStore

IGNORED_STAGES = ("aborted", "canceled")


def _workflow_duration_seconds(workflow: dict) -> float | None:
    """Best-effort seconds from workflow_states.created_at to now."""
    created = workflow.get("created_at")
    if not created:
        return None
    try:
        started = datetime.fromisoformat(str(created))
    except (TypeError, ValueError):
        return None
    now = datetime.now(started.tzinfo) if started.tzinfo else datetime.now()
    return max((now - started).total_seconds(), 0.0)


# The agent pipeline streams the orchestrator watches for completion events.
WORKFLOW_EVENT_STREAMS = [
    "stream.development",
    "stream.qa",
    "stream.deployments",
    "stream.devops",
]
WORKFLOW_EVENT_GROUP = "orchestrator-workflow-group"
WORKFLOW_EVENT_CONSUMER = "orchestrator-1"

# agent completion event -> the pipeline agent it reports for
_AGENT_BY_EVENT = {
    "requirement.completed": "requirement-agent",
    "development.completed": "development-agent",
    "qa.completed": "qa-agent",
    "devops.deployment_simulated": "devops-agent",
}
_FINAL_EVENT = "devops.deployment_simulated"


class WorkflowEventConsumer:
    """Consumes agent completion events and advances the matching workflow.

    Each agent event is correlated back to a workflow by task_id. requirement /
    development / qa progress moves the workflow to ``in_progress``;
    ``devops.deployment_simulated`` moves it to ``completed``. Tasks with no
    persisted workflow (e.g. tasks placed directly on stream.tasks) are ignored.
    It records workflow bookkeeping only — it runs no production action.
    """

    def __init__(
        self,
        store: WorkflowStore | None = None,
        event_bus: RedisStreamEventBus | None = None,
    ) -> None:
        self.store = store or WorkflowStore()
        self.bus = event_bus or RedisStreamEventBus()

    async def handle_event(self, payload: dict) -> dict | None:
        """Apply one agent event to its workflow; return the updated row or None."""
        event = payload.get("event")
        task_id = payload.get("task_id")
        if not task_id or event not in _AGENT_BY_EVENT:
            return None
        workflow = await self.store.get_workflow_state(str(task_id))
        if workflow is None:
            return None
        return await self._advance(workflow, str(event), payload)

    async def _advance(self, workflow: dict, event: str, payload: dict) -> dict | None:
        task_id = workflow["task_id"]
        if workflow["stage"] in IGNORED_STAGES:
            await self._record_ignored_event(task_id, event, str(workflow["stage"]))
            return None
        state = dict(workflow["state"]) if isinstance(workflow["state"], dict) else {}
        execution_result = (
            dict(workflow["execution_result"])
            if isinstance(workflow["execution_result"], dict)
            else {}
        )
        progress = dict(execution_result.get("agent_progress", {}))
        progress[_AGENT_BY_EVENT[event]] = "completed"
        execution_result["agent_progress"] = progress

        if event == _FINAL_EVENT:
            stage = "completed"
            execution_result["status"] = "completed"
            execution_result["production_executed"] = False
            execution_result["deployment_simulated"] = True
            record_id = payload.get("deployment_record_id")
            if record_id is not None:
                execution_result["deployment_record_id"] = record_id
        elif workflow["stage"] == "completed":
            stage = "completed"  # never move a finished workflow backwards
        else:
            stage = "in_progress"
            execution_result["status"] = "in_progress"

        state["stage"] = stage
        state["execution_result"] = execution_result
        updated = await self.store.update_workflow_state(
            task_id,
            stage=stage,
            state=state,
            approval_required=bool(workflow["approval_required"]),
            approval_status=str(workflow["approval_status"] or "none"),
            risk_level=str(workflow["risk_level"] or "unknown"),
            execution_result=execution_result,
        )
        if event == _FINAL_EVENT and updated is not None:
            WORKFLOW_COMPLETED_TOTAL.inc()
            duration = _workflow_duration_seconds(workflow)
            if duration is not None:
                WORKFLOW_DURATION_SECONDS.observe(duration)
            await send_notification(task_id, "workflow.completed", f"workflow {task_id} completed")
        return updated

    async def _record_ignored_event(self, task_id: str, event: str, stage: str) -> None:
        """Audit + notify that an agent event was ignored on a terminated workflow."""
        with contextlib.suppress(Exception):
            await AuditHttpClient().record_event(
                task_id=task_id,
                agent="orchestrator",
                decision_type="workflow_event_ignored",
                summary=f"ignored {event} on {stage} workflow {task_id}",
                result="ignored",
                artifact_refs={"event": event, "stage": stage},
            )
        await send_notification(
            task_id,
            "workflow.event_ignored",
            f"ignored {event} on {stage} workflow {task_id}",
        )

    async def run(self, stop_event: asyncio.Event) -> None:
        """Consume agent events until stop_event is set (Redis consumer group)."""
        while not stop_event.is_set():
            try:
                events = await self.bus.consume_events_multi(
                    WORKFLOW_EVENT_STREAMS,
                    WORKFLOW_EVENT_GROUP,
                    WORKFLOW_EVENT_CONSUMER,
                    block_ms=2000,
                )
                for event in events:
                    with contextlib.suppress(Exception):
                        await self.handle_event(event["event"])
                    await self.bus.ack_event(event["stream"], WORKFLOW_EVENT_GROUP, event["id"])
            except asyncio.CancelledError:
                break
            except Exception:  # transient Redis error: back off and retry
                await asyncio.sleep(1)
        with contextlib.suppress(Exception):
            await self.bus.close()
