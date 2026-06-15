"""Stage 47 -- Workspace Operator Agent.

Consumes controlled workspace execution requests from
``stream.workspace_execution``, validates the design-review preconditions,
generates a deterministic FastAPI Todo project in a controlled workspace,
runs pytest + static checks, collects a diff summary, builds artifacts, maps
work-item execution links, and reports ``workspace.execution_completed`` /
``workspace.execution_failed`` to the orchestrator via
``stream.workspace_events``.

Controlled-only by default:

* WORKSPACE_OPERATOR_TEMPLATE_MODE=true            -> deterministic templates.
* WORKSPACE_OPERATOR_CONTROLLED_ONLY=true          -> controlled workspace only.
* ENABLE_WORKSPACE_OPERATOR_REAL_LLM=false         -> never calls a real LLM.
* ENABLE_WORKSPACE_OPERATOR_GITHUB_WRITE=false     -> never writes GitHub / PR.
* ENABLE_WORKSPACE_OPERATOR_REPO_WRITE=false       -> never writes the repo root.
* ENABLE_WORKSPACE_OPERATOR_DEPLOY=false           -> never deploys.
* ENABLE_WORKSPACE_OPERATOR_WORK_ITEM_DISPATCH=false -> never dispatches work items.

``production_executed`` is always False.
"""

from __future__ import annotations

import os

from shared.sdk.base_agent.stream_agent import StreamAgent
from shared.sdk.design_review import DesignReviewStore
from shared.sdk.project_planning import ProjectPlanningStore
from shared.sdk.workspace_operator import (
    WorkspaceExecutionRequest,
    WorkspaceOperatorStore,
    run_workspace_execution,
)
from shared.sdk.workspace_operator.audit_events import (
    DECISION_WORKSPACE_EXECUTION_COMPLETED,
    DECISION_WORKSPACE_EXECUTION_FAILED,
)
from shared.sdk.workspace_operator.events import (
    EVENT_WORKSPACE_EXECUTION_COMPLETED,
    EVENT_WORKSPACE_EXECUTION_FAILED,
    STREAM_WORKSPACE_EVENTS,
    STREAM_WORKSPACE_EXECUTION,
)


def _flag(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, "true" if default else "false")).strip().lower()
    return raw not in ("false", "0", "no", "")


class WorkspaceOperatorAgent(StreamAgent):
    """Controlled workspace operator -- no LLM, no GitHub, no deploy, no PR."""

    name = "workspace-operator-agent"
    input_stream = STREAM_WORKSPACE_EXECUTION
    output_stream = STREAM_WORKSPACE_EVENTS
    group = "workspace-operator-agent-group"
    consumer = "workspace-operator-agent-1"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._project_store = ProjectPlanningStore()
        self._review_store = DesignReviewStore()
        self._workspace_store = WorkspaceOperatorStore()

    async def handle(self, payload: dict) -> dict:
        task_id = str(payload.get("task_id", "unknown"))
        workflow_id = str(payload.get("workflow_id", "")) or None
        project_id = str(payload.get("project_id") or "")

        if not project_id or not _flag("ENABLE_WORKSPACE_OPERATOR", True):
            reason = "missing_project_id" if not project_id else "workspace_operator_disabled"
            return self._failed(task_id, workflow_id, project_id, reason)

        request = WorkspaceExecutionRequest(
            project_id=project_id,
            design_review_session_id=(str(payload.get("design_review_session_id") or "") or None),
            graph_snapshot_id=(str(payload.get("graph_snapshot_id") or "") or None),
            execution_type=str(payload.get("execution_type") or "fastapi_todo_generation"),
            workspace_type=str(payload.get("workspace_type") or "generated_project"),
            requested_by_agent=self.name,
            controlled_only=True,
            source_task_id=task_id if task_id != "unknown" else None,
        )
        result = await run_workspace_execution(
            request=request,
            project_store=self._project_store,
            review_store=self._review_store,
            workspace_store=self._workspace_store,
            emit_events=True,
        )

        failed = result.status == "failed"
        event_type = (
            EVENT_WORKSPACE_EXECUTION_FAILED if failed else EVENT_WORKSPACE_EXECUTION_COMPLETED
        )
        message = {
            "event": event_type,
            **self.correlation_ids(payload),
            "task_id": task_id,
            "workflow_id": workflow_id or "",
            "project_id": project_id,
            "workspace_id": result.workspace_id or "",
            "status": result.status,
            "tests_status": result.tests_status or "",
            "static_check_status": result.static_check_status or "",
            "generated_files_count": result.generated_files_count,
            "work_item_links_count": result.work_item_links_count,
            "blocked_reason": result.blocked_reason or "",
            "controlled_only": True,
            "production_executed": False,
            "github_write_performed": False,
            "repo_write_performed": False,
            "deployment_performed": False,
            "real_llm_used": False,
        }
        await self.publish_next(message)
        return {
            "task_id": task_id,
            "decision_type": (
                DECISION_WORKSPACE_EXECUTION_FAILED
                if failed
                else DECISION_WORKSPACE_EXECUTION_COMPLETED
            ),
            "summary": (
                f"workspace execution {result.status} for project {project_id} "
                f"(files={result.generated_files_count}, tests={result.tests_status})"
            ),
            "result": result.status,
            "artifact_refs": {
                "project_id": project_id,
                "workspace_id": result.workspace_id,
                "status": result.status,
                "tests_status": result.tests_status,
                "static_check_status": result.static_check_status,
                "generated_files_count": result.generated_files_count,
                "controlled_only": True,
                "production_executed": False,
                "github_write_performed": False,
                "repo_write_performed": False,
                "deployment_performed": False,
                "real_llm_used": False,
            },
            "event_type": event_type,
            "message": f"workspace execution {result.status} for project {project_id}",
        }

    def _failed(self, task_id: str, workflow_id: str | None, project_id: str, reason: str) -> dict:
        return {
            "task_id": task_id,
            "decision_type": DECISION_WORKSPACE_EXECUTION_FAILED,
            "summary": f"workspace execution refused: {reason}",
            "result": "failed",
            "artifact_refs": {
                "project_id": project_id,
                "blocked_reason": reason,
                "controlled_only": True,
                "production_executed": False,
            },
            "event_type": EVENT_WORKSPACE_EXECUTION_FAILED,
            "message": f"workspace execution refused: {reason}",
        }
