import asyncio
import contextlib
from datetime import datetime

from shared.sdk.audit.publisher import publish_audit_event
from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
from shared.sdk.notifications.client import send_notification
from shared.sdk.observability.metrics import (
    WORKFLOW_COMPLETED_TOTAL,
    WORKFLOW_DURATION_SECONDS,
)
from shared.sdk.observability.tracing import start_span
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
    # Stage 45 -- project planner completion events.
    "stream.project_events",
]
WORKFLOW_EVENT_GROUP = "orchestrator-workflow-group"
WORKFLOW_EVENT_CONSUMER = "orchestrator-1"

# agent completion event -> the pipeline agent it reports for
_AGENT_BY_EVENT = {
    "requirement.completed": "requirement-agent",
    "development.completed": "development-agent",
    "qa.completed": "qa-agent",
    "devops.deployment_simulated": "devops-agent",
    # Stage 29: QA decision events also advance / gate the workflow.
    "qa.auto_fix_requested": "qa-agent",
    "qa.blocked_for_human_review": "qa-agent",
    "development.auto_fix_completed": "development-agent-autofix",
    "development.auto_fix_failed": "development-agent-autofix",
    # Stage 45 -- project planner completion events.
    "project.planning_completed": "project-planner-agent",
    "project.planning_failed": "project-planner-agent",
    "project.clarification_required": "project-planner-agent",
}
_FINAL_EVENT = "devops.deployment_simulated"

# Stage 45 -- project planning events flip the workflow to a project stage
# (planning-only) instead of advancing the legacy agent pipeline.
_PROJECT_PLANNING_COMPLETED_EVENT = "project.planning_completed"
_PROJECT_PLANNING_FAILED_EVENT = "project.planning_failed"
_PROJECT_CLARIFICATION_EVENT = "project.clarification_required"
_PROJECT_EVENTS = (
    _PROJECT_PLANNING_COMPLETED_EVENT,
    _PROJECT_PLANNING_FAILED_EVENT,
    _PROJECT_CLARIFICATION_EVENT,
)

#: Stage 29 — QA decision events that flip the workflow stage to a
#: distinct gate state instead of advancing the pipeline.
_QA_AUTO_FIX_EVENT = "qa.auto_fix_requested"
_QA_BLOCKED_EVENT = "qa.blocked_for_human_review"
_AUTO_FIX_DONE_EVENTS = (
    "development.auto_fix_completed",
    "development.auto_fix_failed",
)


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
        with start_span(
            "workflow.event_update",
            **{
                "service.name": "orchestrator",
                "task_id": str(task_id),
                "workflow_id": str(payload.get("workflow_id", "")),
                "agent": "orchestrator",
                "event_type": str(event),
            },
        ):
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
        # Stage 45: project planning events set a project stage and do NOT
        # advance the legacy agent pipeline. planning-only -- never auto-
        # proceeds to development.
        if event in _PROJECT_EVENTS:
            return await self._advance_project(workflow, event, payload, state, execution_result)
        # Stage 29: only the "<agent>.completed" events mark an agent as
        # completed. QA auto-fix / blocked events represent a gating
        # decision, not a successful agent run.
        if event == _QA_AUTO_FIX_EVENT:
            progress[_AGENT_BY_EVENT[event]] = "auto_fix_requested"
        elif event == _QA_BLOCKED_EVENT:
            progress[_AGENT_BY_EVENT[event]] = "blocked"
        elif event == "development.auto_fix_failed":
            progress[_AGENT_BY_EVENT[event]] = "failed"
        else:
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
            github_result = payload.get("github") if isinstance(payload.get("github"), dict) else {}
            if github_result:
                execution_result["github"] = {
                    "status": github_result.get("status", "unknown"),
                    "dry_run": bool(github_result.get("dry_run", True)),
                    "issue_url": github_result.get("issue_url", ""),
                    "branch": github_result.get("branch", ""),
                    "pr_url": github_result.get("pr_url", ""),
                    "pr_number": github_result.get("pr_number"),
                    "checks_status": github_result.get("checks_status", "unknown"),
                    "event_type": github_result.get(
                        "event_type",
                        (
                            "github.pr.dry_run"
                            if github_result.get("dry_run", True)
                            else "github.pr.created"
                        ),
                    ),
                }
                if github_result.get("error"):
                    execution_result["github"]["error"] = github_result["error"]
        elif workflow["stage"] == "completed":
            stage = "completed"  # never move a finished workflow backwards
        elif event == _QA_AUTO_FIX_EVENT:
            # Stage 29: workflow is mid-auto-fix; don't advance past QA.
            stage = "qa_auto_fix"
            execution_result["status"] = "qa_auto_fix"
            execution_result["production_executed"] = False
            execution_result["qa_auto_fix"] = {
                "qa_run_id": str(payload.get("qa_run_id") or ""),
                "fix_request_id": str(payload.get("fix_request_id") or ""),
                "attempt_number": int(payload.get("attempt_number") or 1),
                "max_auto_fix_attempts": int(payload.get("max_auto_fix_attempts") or 2),
            }
        elif event == _QA_BLOCKED_EVENT:
            # Stage 29: workflow halted — must NOT progress to devops-agent.
            stage = "blocked_for_human_review"
            execution_result["status"] = "blocked_for_human_review"
            execution_result["production_executed"] = False
            execution_result["qa_blocked"] = {
                "qa_run_id": str(payload.get("qa_run_id") or ""),
                "reason": str(payload.get("reason") or "unknown"),
                "blocking_finding_ids": payload.get("blocking_finding_ids") or [],
            }
        elif event in _AUTO_FIX_DONE_EVENTS:
            # Auto-fix finished — workflow remains in_progress while the
            # qa-agent re-runs. Don't backslide stage if already completed.
            stage = "in_progress"
            execution_result["status"] = "in_progress"
            execution_result.setdefault("qa_auto_fix", {})
            if isinstance(execution_result.get("qa_auto_fix"), dict):
                execution_result["qa_auto_fix"]["last_event"] = event
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
            with start_span(
                "workflow.completed",
                **{
                    "service.name": "orchestrator",
                    "task_id": task_id,
                    "workflow_id": (
                        str(workflow.get("state", {}).get("workflow_id", ""))
                        if isinstance(workflow.get("state"), dict)
                        else ""
                    ),
                    "agent": "orchestrator",
                    "event_type": "workflow_completed",
                },
            ):
                WORKFLOW_COMPLETED_TOTAL.inc()
                duration = _workflow_duration_seconds(workflow)
                if duration is not None:
                    WORKFLOW_DURATION_SECONDS.observe(duration)
                await send_notification(
                    task_id, "workflow.completed", f"workflow {task_id} completed"
                )
        return updated

    async def _advance_project(
        self,
        workflow: dict,
        event: str,
        payload: dict,
        state: dict,
        execution_result: dict,
    ) -> dict | None:
        """Stage 45 -- apply a project planning event (planning-only).

        Sets the workflow stage to project_planned / planning_failed and
        records the project_id / graph_snapshot_id. Never advances to
        development; a completed workflow is never moved backwards.
        """
        task_id = workflow["task_id"]
        if workflow["stage"] == "completed":
            return None
        if event == _PROJECT_PLANNING_COMPLETED_EVENT:
            validation_status = str(payload.get("validation_status") or "valid")
            if validation_status == "invalid":
                stage = "planning_failed"
                status = "planning_failed"
            else:
                stage = "project_planned"
                status = "project_planned"
        elif event == _PROJECT_PLANNING_FAILED_EVENT:
            stage = "planning_failed"
            status = "planning_failed"
        else:  # clarification required
            stage = "project_clarification_required"
            status = "project_clarification_required"

        execution_result["status"] = status
        execution_result["production_executed"] = False
        execution_result["planning_only"] = True
        project_block = {
            "project_id": str(payload.get("project_id") or ""),
            "graph_snapshot_id": str(payload.get("graph_snapshot_id") or ""),
            "validation_status": str(payload.get("validation_status") or ""),
            "work_items_count": int(payload.get("work_items_count") or 0),
        }
        execution_result["project_planning"] = project_block
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
        with contextlib.suppress(Exception):
            await send_notification(
                task_id,
                event,
                f"workflow {task_id} {status} (project={project_block['project_id']})",
            )
        return updated

    async def _record_ignored_event(self, task_id: str, event: str, stage: str) -> None:
        """Audit + notify that an agent event was ignored on a terminated workflow."""
        with contextlib.suppress(Exception):
            await publish_audit_event(
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
