"""Stage 46 -- Design Review Agent.

Consumes design review requests from ``stream.design_review``, runs a
deterministic multi-role discussion + design review against an already-planned
project graph (NO LLM), persists findings/decisions/gates, and reports
``design_review.completed`` / ``design_review.blocked`` to the orchestrator via
``stream.design_review_events``.

Review-only by default:

* DESIGN_REVIEW_TEMPLATE_MODE=true            -> deterministic templates only.
* ENABLE_DESIGN_REVIEW_REAL_LLM=false         -> never calls a real LLM.
* DESIGN_REVIEW_PLANNING_ONLY=true            -> stays planning-only.
* ENABLE_DESIGN_REVIEW_WORK_ITEM_DISPATCH=false -> never dispatches work items.

It never modifies a repo, opens a PR, deploys, or sends real external
messages. ``production_executed`` is always False.
"""

from __future__ import annotations

import os

from shared.sdk.agent_discussion import AgentDiscussionStore
from shared.sdk.base_agent.stream_agent import StreamAgent
from shared.sdk.design_review import DesignReviewStore, run_design_review
from shared.sdk.design_review.audit_events import (
    DECISION_DESIGN_REVIEW_BLOCKED,
    DECISION_DESIGN_REVIEW_COMPLETED,
)
from shared.sdk.design_review.events import (
    EVENT_DESIGN_REVIEW_BLOCKED,
    EVENT_DESIGN_REVIEW_COMPLETED,
    STREAM_DESIGN_REVIEW,
    STREAM_DESIGN_REVIEW_EVENTS,
)
from shared.sdk.project_planning import ProjectPlanningStore


def _flag(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, "true" if default else "false")).strip().lower()
    return raw not in ("false", "0", "no", "")


class DesignReviewAgent(StreamAgent):
    """Deterministic design review agent -- no LLM, no GitHub, no deploy."""

    name = "design-review-agent"
    input_stream = STREAM_DESIGN_REVIEW
    output_stream = STREAM_DESIGN_REVIEW_EVENTS
    group = "design-review-agent-group"
    consumer = "design-review-agent-1"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._project_store = ProjectPlanningStore()
        self._discussion_store = AgentDiscussionStore()
        self._review_store = DesignReviewStore()

    async def handle(self, payload: dict) -> dict:
        task_id = str(payload.get("task_id", "unknown"))
        workflow_id = str(payload.get("workflow_id", "")) or None
        project_id = str(payload.get("project_id") or "")
        review_type = str(payload.get("review_type") or "full_pre_execution")

        if not project_id:
            return {
                "task_id": task_id,
                "decision_type": DECISION_DESIGN_REVIEW_BLOCKED,
                "summary": "design review request missing project_id",
                "result": "failed",
                "artifact_refs": {"production_executed": False},
                "event_type": EVENT_DESIGN_REVIEW_BLOCKED,
                "message": "design review request missing project_id",
            }

        output = await run_design_review(
            project_id=project_id,
            project_store=self._project_store,
            discussion_store=self._discussion_store,
            review_store=self._review_store,
            review_type=review_type,
            planning_only=_flag("DESIGN_REVIEW_PLANNING_ONLY", True),
            work_item_dispatch_enabled=_flag("ENABLE_DESIGN_REVIEW_WORK_ITEM_DISPATCH", False),
            requested_by_agent=self.name,
            source_task_id=task_id if task_id != "unknown" else None,
            emit_events=True,
        )

        blocked = output.status == "blocked"
        event_type = EVENT_DESIGN_REVIEW_BLOCKED if blocked else EVENT_DESIGN_REVIEW_COMPLETED
        message = {
            "event": event_type,
            **self.correlation_ids(payload),
            "task_id": task_id,
            "workflow_id": workflow_id or "",
            "project_id": project_id,
            "review_session_id": output.review_session_id,
            "discussion_session_id": output.discussion_session_id,
            "decision": output.decision,
            "status": output.status,
            "findings_count": output.findings_count,
            "blocking_findings_count": output.blocking_findings_count,
            "gates_count": output.gates_count,
            "planning_only": True,
            "production_executed": False,
        }
        await self.publish_next(message)
        return {
            "task_id": task_id,
            "decision_type": (
                DECISION_DESIGN_REVIEW_BLOCKED if blocked else DECISION_DESIGN_REVIEW_COMPLETED
            ),
            "summary": (
                f"design review {output.status} for project {project_id} "
                f"(decision={output.decision}, findings={output.findings_count})"
            ),
            "result": output.status,
            "artifact_refs": {
                "project_id": project_id,
                "review_session_id": output.review_session_id,
                "discussion_session_id": output.discussion_session_id,
                "decision": output.decision,
                "findings_count": output.findings_count,
                "blocking_findings_count": output.blocking_findings_count,
                "gates_count": output.gates_count,
                "planning_only": True,
                "production_executed": False,
            },
            "event_type": event_type,
            "message": f"design review {output.status} for project {project_id}",
        }
