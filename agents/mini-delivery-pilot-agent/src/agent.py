"""Stage 48 -- Mini Delivery Pilot Agent.

Consumes mini delivery pilot requests from ``stream.delivery_pilot``, chains
the controlled project-plan -> design-review -> workspace-execution stages,
builds acceptance / QA / safety evidence + a mini delivery report, and reports
``delivery_pilot.completed`` / ``delivery_pilot.failed`` to the orchestrator
via ``stream.delivery_pilot_events``.

Controlled-only by default: no real LLM, no GitHub write, no PR, no deploy, no
external delivery. ``production_executed`` is always False.
"""

from __future__ import annotations

import os

from shared.sdk.agent_discussion import AgentDiscussionStore
from shared.sdk.base_agent.stream_agent import StreamAgent
from shared.sdk.design_review import DesignReviewStore
from shared.sdk.mini_delivery_pilot import (
    MiniDeliveryPilotRequest,
    MiniDeliveryPilotStore,
    run_mini_delivery_pilot,
)
from shared.sdk.mini_delivery_pilot.audit_events import (
    DECISION_MINI_DELIVERY_PILOT_COMPLETED,
    DECISION_MINI_DELIVERY_PILOT_FAILED,
)
from shared.sdk.mini_delivery_pilot.events import (
    EVENT_DELIVERY_PILOT_COMPLETED,
    EVENT_DELIVERY_PILOT_FAILED,
    STREAM_DELIVERY_PILOT,
    STREAM_DELIVERY_PILOT_EVENTS,
)
from shared.sdk.project_planning import ProjectPlanningStore
from shared.sdk.workspace_operator import WorkspaceOperatorStore


def _flag(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, "true" if default else "false")).strip().lower()
    return raw not in ("false", "0", "no", "")


class MiniDeliveryPilotAgent(StreamAgent):
    """Controlled mini delivery pilot -- no LLM, no GitHub, no PR, no deploy."""

    name = "mini-delivery-pilot-agent"
    input_stream = STREAM_DELIVERY_PILOT
    output_stream = STREAM_DELIVERY_PILOT_EVENTS
    group = "mini-delivery-pilot-agent-group"
    consumer = "mini-delivery-pilot-agent-1"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._project_store = ProjectPlanningStore()
        self._discussion_store = AgentDiscussionStore()
        self._review_store = DesignReviewStore()
        self._workspace_store = WorkspaceOperatorStore()
        self._pilot_store = MiniDeliveryPilotStore()

    async def handle(self, payload: dict) -> dict:
        task_id = str(payload.get("task_id", "unknown"))
        workflow_id = str(payload.get("workflow_id", "")) or None

        if not _flag("ENABLE_MINI_DELIVERY_PILOT", True):
            return self._failed(task_id, workflow_id, "", "mini_delivery_pilot_disabled")

        request = MiniDeliveryPilotRequest(
            request_text=str(
                payload.get("request_text")
                or "Create a FastAPI Todo Service with CRUD, SQLite, pytest, README, and API examples."
            ),
            project_id=(str(payload.get("project_id") or "") or None),
            design_review_session_id=(str(payload.get("design_review_session_id") or "") or None),
            workspace_id=(str(payload.get("workspace_id") or "") or None),
            pilot_type=str(payload.get("pilot_type") or "fastapi_todo_service"),
            controlled_only=True,
            requested_by_agent=self.name,
            source_task_id=task_id if task_id != "unknown" else None,
        )
        result = await run_mini_delivery_pilot(
            request=request,
            project_store=self._project_store,
            discussion_store=self._discussion_store,
            review_store=self._review_store,
            workspace_store=self._workspace_store,
            pilot_store=self._pilot_store,
            emit_events=True,
        )

        failed = result.pilot_status in ("failed", "blocked")
        event_type = EVENT_DELIVERY_PILOT_FAILED if failed else EVENT_DELIVERY_PILOT_COMPLETED
        message = {
            "event": event_type,
            **self.correlation_ids(payload),
            "task_id": task_id,
            "workflow_id": workflow_id or "",
            "pilot_id": result.pilot_id or "",
            "project_id": result.project_id or "",
            "design_review_session_id": result.design_review_session_id or "",
            "workspace_id": result.workspace_id or "",
            "pilot_status": result.pilot_status,
            "qa_status": result.qa_status or "",
            "safety_status": result.safety_status or "",
            "acceptance_total": result.acceptance_total,
            "acceptance_satisfied": result.acceptance_satisfied,
            "blocked_reason": result.blocked_reason or "",
            "controlled_only": True,
            "production_executed": False,
            "github_write_performed": False,
            "pr_created": False,
            "deployment_performed": False,
            "real_llm_used": False,
        }
        await self.publish_next(message)
        return {
            "task_id": task_id,
            "decision_type": (
                DECISION_MINI_DELIVERY_PILOT_FAILED
                if failed
                else DECISION_MINI_DELIVERY_PILOT_COMPLETED
            ),
            "summary": (
                f"mini delivery pilot {result.pilot_status} "
                f"(QA={result.qa_status}, safety={result.safety_status}, "
                f"acceptance {result.acceptance_satisfied}/{result.acceptance_total})"
            ),
            "result": result.pilot_status,
            "artifact_refs": {
                "pilot_id": result.pilot_id,
                "project_id": result.project_id,
                "workspace_id": result.workspace_id,
                "pilot_status": result.pilot_status,
                "qa_status": result.qa_status,
                "safety_status": result.safety_status,
                "controlled_only": True,
                "production_executed": False,
                "github_write_performed": False,
                "pr_created": False,
                "deployment_performed": False,
                "real_llm_used": False,
            },
            "event_type": event_type,
            "message": f"mini delivery pilot {result.pilot_status}",
        }

    def _failed(self, task_id: str, workflow_id: str | None, pilot_id: str, reason: str) -> dict:
        return {
            "task_id": task_id,
            "decision_type": DECISION_MINI_DELIVERY_PILOT_FAILED,
            "summary": f"mini delivery pilot refused: {reason}",
            "result": "failed",
            "artifact_refs": {
                "pilot_id": pilot_id,
                "blocked_reason": reason,
                "controlled_only": True,
                "production_executed": False,
            },
            "event_type": EVENT_DELIVERY_PILOT_FAILED,
            "message": f"mini delivery pilot refused: {reason}",
        }
