"""Stage 49 -- Delivery Package Agent.

Consumes delivery package build requests from ``stream.delivery_package``, reads
one completed mini delivery pilot's evidence, builds a formal Delivery Package
+ Acceptance Gate (sections, artifacts, checklist, operator-review placeholder,
handoff summaries, readiness snapshot, report), and reports
``delivery_package.ready_for_review`` / ``delivery_package.build_failed`` to the
orchestrator via ``stream.delivery_package_events``.

Controlled-only by default: no real LLM, no GitHub write, no PR, no deploy, no
external delivery, no auto human acceptance. ``production_executed`` is always
False.
"""

from __future__ import annotations

import os

from shared.sdk.base_agent.stream_agent import StreamAgent
from shared.sdk.delivery_package import (
    DeliveryPackageRequest,
    DeliveryPackageStore,
    run_delivery_package_build,
)
from shared.sdk.delivery_package.audit_events import (
    DECISION_DELIVERY_PACKAGE_BUILD_FAILED,
    DECISION_DELIVERY_PACKAGE_READY_FOR_REVIEW,
)
from shared.sdk.delivery_package.events import (
    EVENT_DELIVERY_PACKAGE_BUILD_FAILED,
    EVENT_DELIVERY_PACKAGE_READY_FOR_REVIEW,
    STREAM_DELIVERY_PACKAGE,
    STREAM_DELIVERY_PACKAGE_EVENTS,
)
from shared.sdk.design_review import DesignReviewStore
from shared.sdk.mini_delivery_pilot import MiniDeliveryPilotStore
from shared.sdk.project_planning import ProjectPlanningStore
from shared.sdk.workspace_operator import WorkspaceOperatorStore


def _flag(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, "true" if default else "false")).strip().lower()
    return raw not in ("false", "0", "no", "")


class DeliveryPackageAgent(StreamAgent):
    """Controlled delivery package builder -- no LLM, no GitHub, no PR, no deploy."""

    name = "delivery-package-agent"
    input_stream = STREAM_DELIVERY_PACKAGE
    output_stream = STREAM_DELIVERY_PACKAGE_EVENTS
    group = "delivery-package-agent-group"
    consumer = "delivery-package-agent-1"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._pilot_store = MiniDeliveryPilotStore()
        self._project_store = ProjectPlanningStore()
        self._review_store = DesignReviewStore()
        self._workspace_store = WorkspaceOperatorStore()
        self._package_store = DeliveryPackageStore()

    async def handle(self, payload: dict) -> dict:
        task_id = str(payload.get("task_id", "unknown"))
        workflow_id = str(payload.get("workflow_id", "")) or None
        pilot_id = str(payload.get("pilot_id") or "") or None

        if not _flag("ENABLE_DELIVERY_PACKAGE", True):
            return self._failed(task_id, workflow_id, "", "delivery_package_disabled")
        if not pilot_id:
            return self._failed(task_id, workflow_id, "", "pilot_id_required")

        request = DeliveryPackageRequest(
            pilot_id=pilot_id,
            project_id=(str(payload.get("project_id") or "") or None),
            package_type=str(payload.get("package_type") or "mini_project_delivery"),
            controlled_only=True,
            requested_by_agent=self.name,
            source_task_id=task_id if task_id != "unknown" else None,
        )
        result = await run_delivery_package_build(
            request=request,
            pilot_store=self._pilot_store,
            project_store=self._project_store,
            review_store=self._review_store,
            workspace_store=self._workspace_store,
            package_store=self._package_store,
            emit_events=True,
        )

        failed = result.package_status not in ("ready_for_review", "accepted")
        event_type = (
            EVENT_DELIVERY_PACKAGE_BUILD_FAILED
            if failed
            else EVENT_DELIVERY_PACKAGE_READY_FOR_REVIEW
        )
        message = {
            "event": event_type,
            **self.correlation_ids(payload),
            "task_id": task_id,
            "workflow_id": workflow_id or "",
            "package_id": result.package_id or "",
            "project_id": result.project_id or "",
            "pilot_id": result.pilot_id or "",
            "workspace_id": result.workspace_id or "",
            "package_status": result.package_status,
            "acceptance_gate_status": result.acceptance_gate_status or "",
            "acceptance_gate_decision": result.acceptance_gate_decision or "",
            "human_acceptance_status": result.human_acceptance_status,
            "readiness_status": result.readiness_status or "",
            "blocking_findings_count": result.blocking_findings_count,
            "blocked_reason": result.blocked_reason or "",
            "controlled_only": True,
            "production_executed": False,
            "github_write_performed": False,
            "pr_created": False,
            "deployment_performed": False,
            "real_llm_used": False,
            "external_delivery_performed": False,
        }
        await self.publish_next(message)
        return {
            "task_id": task_id,
            "decision_type": (
                DECISION_DELIVERY_PACKAGE_BUILD_FAILED
                if failed
                else DECISION_DELIVERY_PACKAGE_READY_FOR_REVIEW
            ),
            "summary": (
                f"delivery package {result.package_status} "
                f"(gate={result.acceptance_gate_decision}, "
                f"human_acceptance={result.human_acceptance_status})"
            ),
            "result": result.package_status,
            "artifact_refs": {
                "package_id": result.package_id,
                "project_id": result.project_id,
                "pilot_id": result.pilot_id,
                "package_status": result.package_status,
                "acceptance_gate_decision": result.acceptance_gate_decision,
                "human_acceptance_status": result.human_acceptance_status,
                "controlled_only": True,
                "production_executed": False,
                "github_write_performed": False,
                "pr_created": False,
                "deployment_performed": False,
                "real_llm_used": False,
                "external_delivery_performed": False,
            },
            "event_type": event_type,
            "message": f"delivery package {result.package_status}",
        }

    def _failed(self, task_id: str, workflow_id: str | None, package_id: str, reason: str) -> dict:
        return {
            "task_id": task_id,
            "decision_type": DECISION_DELIVERY_PACKAGE_BUILD_FAILED,
            "summary": f"delivery package refused: {reason}",
            "result": "failed",
            "artifact_refs": {
                "package_id": package_id,
                "blocked_reason": reason,
                "controlled_only": True,
                "production_executed": False,
            },
            "event_type": EVENT_DELIVERY_PACKAGE_BUILD_FAILED,
            "message": f"delivery package refused: {reason}",
        }
