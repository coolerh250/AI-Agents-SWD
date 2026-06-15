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
    # Stage 46 -- design review completion events.
    "stream.design_review_events",
    # Stage 47 -- workspace operator completion events.
    "stream.workspace_events",
    # Stage 48 -- mini delivery pilot completion events.
    "stream.delivery_pilot_events",
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
    # Stage 46 -- design review completion events.
    "design_review.completed": "design-review-agent",
    "design_review.blocked": "design-review-agent",
    # Stage 47 -- workspace operator completion events.
    "workspace.execution_completed": "workspace-operator-agent",
    "workspace.execution_failed": "workspace-operator-agent",
    # Stage 48 -- mini delivery pilot completion events.
    "delivery_pilot.completed": "mini-delivery-pilot-agent",
    "delivery_pilot.failed": "mini-delivery-pilot-agent",
}
_FINAL_EVENT = "devops.deployment_simulated"

# Stage 46 -- design review events flip the workflow to a review stage
# (review-only) instead of advancing to development.
_DESIGN_REVIEW_COMPLETED_EVENT = "design_review.completed"
_DESIGN_REVIEW_BLOCKED_EVENT = "design_review.blocked"
_DESIGN_REVIEW_EVENTS = (_DESIGN_REVIEW_COMPLETED_EVENT, _DESIGN_REVIEW_BLOCKED_EVENT)


def _design_review_enabled() -> bool:
    import os

    return str(os.environ.get("ENABLE_DESIGN_REVIEW", "true")).strip().lower() not in (
        "false",
        "0",
        "no",
    )


# Stage 47 -- workspace operator events flip the workflow to a controlled
# workspace stage (controlled-only) instead of advancing to development.
_WORKSPACE_COMPLETED_EVENT = "workspace.execution_completed"
_WORKSPACE_FAILED_EVENT = "workspace.execution_failed"
_WORKSPACE_EVENTS = (_WORKSPACE_COMPLETED_EVENT, _WORKSPACE_FAILED_EVENT)


def _env_flag(name: str, default: bool) -> bool:
    import os

    return str(os.environ.get(name, "true" if default else "false")).strip().lower() not in (
        "false",
        "0",
        "no",
        "",
    )


def _workspace_operator_enabled() -> bool:
    return _env_flag("ENABLE_WORKSPACE_OPERATOR", True) and _env_flag(
        "WORKSPACE_OPERATOR_CONTROLLED_ONLY", True
    )


# Stage 48 -- mini delivery pilot events flip the workflow to a pilot stage
# (controlled-only) instead of advancing the legacy pipeline.
_DELIVERY_PILOT_COMPLETED_EVENT = "delivery_pilot.completed"
_DELIVERY_PILOT_FAILED_EVENT = "delivery_pilot.failed"
_DELIVERY_PILOT_EVENTS = (_DELIVERY_PILOT_COMPLETED_EVENT, _DELIVERY_PILOT_FAILED_EVENT)


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
        if event in _DESIGN_REVIEW_EVENTS:
            return await self._advance_design_review(
                workflow, event, payload, state, execution_result
            )
        if event in _WORKSPACE_EVENTS:
            return await self._advance_workspace(workflow, event, payload, state, execution_result)
        if event in _DELIVERY_PILOT_EVENTS:
            return await self._advance_delivery_pilot(
                workflow, event, payload, state, execution_result
            )
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
        # Stage 46 -- on a successful plan, request a design review (review-only).
        if stage == "project_planned" and project_block["project_id"] and _design_review_enabled():
            with contextlib.suppress(Exception):
                await self.bus.publish_event(
                    "stream.design_review",
                    {
                        "event": "project.design_review_requested",
                        "task_id": task_id,
                        "workflow_id": str(payload.get("workflow_id", "")),
                        "project_id": project_block["project_id"],
                        "graph_snapshot_id": project_block["graph_snapshot_id"],
                        "review_type": "full_pre_execution",
                        "requested_by_agent": "orchestrator",
                        "production_executed": False,
                    },
                )
        return updated

    async def _advance_design_review(
        self,
        workflow: dict,
        event: str,
        payload: dict,
        state: dict,
        execution_result: dict,
    ) -> dict | None:
        """Stage 46 -- apply a design review event (review-only).

        Sets the workflow stage to design_reviewed / design_reviewed_with_findings
        / design_review_blocked. Never advances to development this stage.
        """
        task_id = workflow["task_id"]
        if workflow["stage"] == "completed":
            return None
        decision = str(payload.get("decision") or "planning_only")
        if event == _DESIGN_REVIEW_BLOCKED_EVENT or decision in ("no_go", "needs_clarification"):
            stage = "design_review_blocked"
        elif decision == "go_with_findings":
            stage = "design_reviewed_with_findings"
        else:  # go or planning_only
            stage = "design_reviewed"
        execution_result["status"] = stage
        execution_result["production_executed"] = False
        execution_result["planning_only"] = True
        execution_result["design_review"] = {
            "project_id": str(payload.get("project_id") or ""),
            "review_session_id": str(payload.get("review_session_id") or ""),
            "decision": decision,
            "findings_count": int(payload.get("findings_count") or 0),
            "blocking_findings_count": int(payload.get("blocking_findings_count") or 0),
            "gates_count": int(payload.get("gates_count") or 0),
        }
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
                task_id, event, f"workflow {task_id} {stage} (decision={decision})"
            )
        # Stage 47 -- on a non-blocked design review, request a controlled
        # workspace execution (controlled-only). Never dispatches the legacy
        # development-agent, never deploys, never writes GitHub.
        project_id = str(payload.get("project_id") or "")
        if (
            stage in ("design_reviewed", "design_reviewed_with_findings")
            and project_id
            and decision in ("planning_only", "go_with_findings", "go")
            and _workspace_operator_enabled()
        ):
            with contextlib.suppress(Exception):
                await self.bus.publish_event(
                    "stream.workspace_execution",
                    {
                        "event": "project.workspace_execution_requested",
                        "task_id": task_id,
                        "workflow_id": str(payload.get("workflow_id", "")),
                        "project_id": project_id,
                        "design_review_session_id": str(payload.get("review_session_id") or ""),
                        "execution_type": "fastapi_todo_generation",
                        "workspace_type": "generated_project",
                        "requested_by_agent": "orchestrator",
                        "controlled_only": True,
                        "production_executed": False,
                    },
                )
        return updated

    async def _advance_workspace(
        self,
        workflow: dict,
        event: str,
        payload: dict,
        state: dict,
        execution_result: dict,
    ) -> dict | None:
        """Stage 47 -- apply a controlled workspace execution event.

        Sets the workflow stage to workspace_execution_requested /
        workspace_generated / workspace_tests_passed / workspace_tests_failed /
        workspace_execution_failed. Never advances to deployment or PR creation;
        no auto-fix this stage.
        """
        task_id = workflow["task_id"]
        if workflow["stage"] == "completed":
            return None
        ws_status = str(payload.get("status") or "")
        tests_status = str(payload.get("tests_status") or "")
        if event == _WORKSPACE_FAILED_EVENT or ws_status == "failed":
            stage = "workspace_execution_failed"
        elif ws_status == "tests_passed" or tests_status == "passed":
            stage = "workspace_tests_passed"
        elif ws_status == "tests_failed" or tests_status == "failed":
            stage = "workspace_tests_failed"
        else:
            stage = "workspace_generated"
        execution_result["status"] = stage
        execution_result["production_executed"] = False
        execution_result["planning_only"] = True
        execution_result["controlled_only"] = True
        execution_result["workspace_execution"] = {
            "project_id": str(payload.get("project_id") or ""),
            "workspace_id": str(payload.get("workspace_id") or ""),
            "status": ws_status,
            "tests_status": tests_status,
            "static_check_status": str(payload.get("static_check_status") or ""),
            "generated_files_count": int(payload.get("generated_files_count") or 0),
            "github_write_performed": False,
            "repo_write_performed": False,
            "deployment_performed": False,
            "real_llm_used": False,
        }
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
            await send_notification(task_id, event, f"workflow {task_id} {stage}")
        return updated

    async def _advance_delivery_pilot(
        self,
        workflow: dict,
        event: str,
        payload: dict,
        state: dict,
        execution_result: dict,
    ) -> dict | None:
        """Stage 48 -- apply a mini delivery pilot event (controlled-only).

        Sets the workflow stage to mini_delivery_pilot_completed /
        mini_delivery_pilot_failed. Never advances to production, PR, or deploy.
        """
        task_id = workflow["task_id"]
        if workflow["stage"] == "completed":
            return None
        pilot_status = str(payload.get("pilot_status") or "")
        if event == _DELIVERY_PILOT_FAILED_EVENT or pilot_status in ("failed", "blocked"):
            stage = "mini_delivery_pilot_failed"
        else:
            stage = "mini_delivery_pilot_completed"
        execution_result["status"] = stage
        execution_result["production_executed"] = False
        execution_result["controlled_only"] = True
        execution_result["mini_delivery_pilot"] = {
            "pilot_id": str(payload.get("pilot_id") or ""),
            "project_id": str(payload.get("project_id") or ""),
            "workspace_id": str(payload.get("workspace_id") or ""),
            "pilot_status": pilot_status,
            "qa_status": str(payload.get("qa_status") or ""),
            "safety_status": str(payload.get("safety_status") or ""),
            "acceptance_total": int(payload.get("acceptance_total") or 0),
            "acceptance_satisfied": int(payload.get("acceptance_satisfied") or 0),
            "github_write_performed": False,
            "pr_created": False,
            "deployment_performed": False,
            "real_llm_used": False,
        }
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
            await send_notification(task_id, event, f"workflow {task_id} {stage}")
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
