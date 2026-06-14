"""Stage 45 -- Project Planner Agent.

Consumes planning requests from ``stream.project_planning``, builds a
deterministic project brief + task graph (template mode, NO LLM), persists
the full graph, validates dependencies, and reports completion to the
orchestrator via ``stream.project_events``.

Planning-only by default:

* ENABLE_PROJECT_WORK_ITEM_DISPATCH=false  -> never dispatches work items.
* ENABLE_PROJECT_PLANNER_REAL_LLM=false    -> never calls a real LLM.
* PROJECT_PLANNER_TEMPLATE_MODE=true       -> deterministic templates only.

It never modifies a repo, opens a PR, or deploys. ``production_executed``
is always False.
"""

from __future__ import annotations

import os

from shared.sdk.base_agent.stream_agent import StreamAgent
from shared.sdk.project_planning import (
    PlannerInput,
    ProjectPlanningStore,
    plan_project,
)
from shared.sdk.project_planning.audit_events import (
    DECISION_PROJECT_PLANNING_COMPLETED,
    DECISION_PROJECT_PLANNING_FAILED,
)
from shared.sdk.project_planning.events import (
    EVENT_PROJECT_CLARIFICATION_REQUIRED,
    EVENT_PROJECT_PLANNING_COMPLETED,
    EVENT_PROJECT_PLANNING_FAILED,
    STREAM_PROJECT_EVENTS,
    STREAM_PROJECT_PLANNING,
)


def _flag(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, "true" if default else "false")).strip().lower()
    return raw not in ("false", "0", "no", "")


class ProjectPlannerAgent(StreamAgent):
    """Deterministic project planner — no LLM, no GitHub, no deploy."""

    name = "project-planner-agent"
    input_stream = STREAM_PROJECT_PLANNING
    output_stream = STREAM_PROJECT_EVENTS
    group = "project-planner-agent-group"
    consumer = "project-planner-agent-1"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._store = ProjectPlanningStore()

    async def handle(self, payload: dict) -> dict:
        task_id = str(payload.get("task_id", "unknown"))
        workflow_id = str(payload.get("workflow_id", "")) or None
        request = payload.get("request", {}) if isinstance(payload.get("request"), dict) else {}
        request_text = str(
            request.get("description")
            or payload.get("request_text")
            or payload.get("requirement_summary")
            or ""
        )
        requirement_summary = payload.get("requirement_summary")
        project_type = payload.get("project_type") or request.get("type")
        autonomy_level = str(payload.get("autonomy_level") or "autonomous_dev_test")

        planner_input = PlannerInput(
            task_id=task_id,
            request_text=request_text,
            requirement_summary=str(requirement_summary) if requirement_summary else None,
            source=str(payload.get("source") or "orchestrator"),
            requester=str(payload.get("requester") or "") or None,
            project_type=str(project_type) if project_type else None,
            autonomy_level=autonomy_level,
            dispatch_policy="planning_only",
        )

        output = await plan_project(
            planner_input,
            self._store,
            emit_events=True,
            planning_only=True,
        )

        if output.requires_clarification:
            message = {
                "event": EVENT_PROJECT_CLARIFICATION_REQUIRED,
                **self.correlation_ids(payload),
                "task_id": task_id,
                "workflow_id": workflow_id or "",
                "project_id": output.project_id,
                "requires_clarification": True,
                "planning_only": True,
                "production_executed": False,
            }
            await self.publish_next(message)
            return {
                "task_id": task_id,
                "decision_type": DECISION_PROJECT_PLANNING_FAILED,
                "summary": f"project {output.project_id} requires clarification",
                "result": "requires_clarification",
                "artifact_refs": {
                    "project_id": output.project_id,
                    "requires_clarification": True,
                    "production_executed": False,
                },
                "event_type": EVENT_PROJECT_CLARIFICATION_REQUIRED,
                "message": f"project {output.project_id} requires clarification",
            }

        event_type = (
            EVENT_PROJECT_PLANNING_COMPLETED
            if output.validation_status in ("valid", "warning")
            else EVENT_PROJECT_PLANNING_FAILED
        )
        message = {
            "event": event_type,
            **self.correlation_ids(payload),
            "task_id": task_id,
            "workflow_id": workflow_id or "",
            "project_id": output.project_id,
            "graph_snapshot_id": output.graph_snapshot_id,
            "validation_status": output.validation_status,
            "work_items_count": output.work_items_count,
            "planning_only": True,
            "production_executed": False,
        }
        await self.publish_next(message)
        return {
            "task_id": task_id,
            "decision_type": DECISION_PROJECT_PLANNING_COMPLETED,
            "summary": (
                f"project {output.project_id} planned "
                f"({output.work_items_count} work items, "
                f"validation={output.validation_status})"
            ),
            "result": "completed",
            "artifact_refs": {
                "project_id": output.project_id,
                "graph_snapshot_id": output.graph_snapshot_id,
                "work_items_count": output.work_items_count,
                "dependencies_count": output.dependencies_count,
                "acceptance_criteria_count": output.acceptance_criteria_count,
                "validation_status": output.validation_status,
                "planning_only": True,
                "production_executed": False,
            },
            "event_type": event_type,
            "message": (
                f"project {output.project_id} planning completed "
                f"({output.work_items_count} work items)"
            ),
        }
