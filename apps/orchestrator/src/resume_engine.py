from shared.sdk.http_clients.approval_http_client import ApprovalHttpClient
from shared.sdk.http_clients.audit_http_client import AuditHttpClient
from shared.sdk.notifications.client import send_notification
from shared.sdk.workflow_store.store import WorkflowStore


class ResumeError(Exception):
    """Raised when a workflow cannot be resumed."""


class ResumeEngine:
    """Resumes and replays persisted workflows.

    Resuming is mock-safe: it only updates workflow bookkeeping (stage,
    execution_result, audit trail). It never executes a production action.
    """

    def __init__(self, store: WorkflowStore | None = None) -> None:
        self.store = store or WorkflowStore()

    async def replay_workflow_state(self, task_id: str) -> dict | None:
        """Return the full persisted workflow state without executing anything."""
        return await self.store.get_workflow_state(task_id)

    async def resume_workflow(self, task_id: str) -> dict:
        """Force-resume a workflow; only allowed once its approval is granted."""
        workflow = await self.store.get_workflow_state(task_id)
        if workflow is None:
            raise ResumeError(f"workflow not found: {task_id}")
        if workflow["approval_status"] == "approved":
            return await self._apply_approved(task_id)
        if not await self._approval_granted(workflow):
            raise ResumeError(f"workflow {task_id} is not approved; cannot resume")
        return await self._apply_approved(task_id)

    async def resume_approved_workflows(self) -> list[str]:
        """Startup recovery: reconcile waiting_approval workflows with approvals."""
        resumed: list[str] = []
        for workflow in await self.store.list_workflows(status="waiting_approval"):
            request_id = _approval_request_id(workflow)
            if not request_id:
                continue
            try:
                approval = await ApprovalHttpClient().get_approval(request_id)
            except Exception:  # approval-engine unreachable; skip this workflow
                continue
            status = approval.get("status")
            if status == "approved":
                await self._apply_approved(workflow["task_id"])
                resumed.append(workflow["task_id"])
            elif status == "rejected":
                await self.mark_rejected(workflow["task_id"])
        return resumed

    async def on_approval_event(self, task_id: str, status: str) -> dict | None:
        """Handle an approval.* event for a persisted workflow."""
        workflow = await self.store.get_workflow_state(task_id)
        if workflow is None:
            return None
        if status == "approved":
            return await self._apply_approved(task_id)
        if status == "rejected":
            return await self.mark_rejected(task_id)
        return None

    async def mark_rejected(self, task_id: str) -> dict:
        workflow = await self.store.get_workflow_state(task_id)
        if workflow is None:
            raise ResumeError(f"workflow not found: {task_id}")
        state = dict(workflow["state"]) if isinstance(workflow["state"], dict) else {}
        execution_result = {"status": "rejected", "production_executed": False}
        state["stage"] = "rejected"
        state["approval_status"] = "rejected"
        state["execution_result"] = execution_result
        updated = await self.store.update_workflow_state(
            task_id,
            stage="rejected",
            state=state,
            approval_required=bool(workflow["approval_required"]),
            approval_status="rejected",
            risk_level=str(workflow["risk_level"] or "unknown"),
            execution_result=execution_result,
        )
        if updated is None:
            raise ResumeError(f"workflow not found: {task_id}")
        await send_notification(task_id, "workflow.rejected", f"workflow {task_id} was rejected")
        return updated

    async def _apply_approved(self, task_id: str) -> dict:
        workflow = await self.store.get_workflow_state(task_id)
        if workflow is None:
            raise ResumeError(f"workflow not found: {task_id}")
        state = dict(workflow["state"]) if isinstance(workflow["state"], dict) else {}
        audit_ref = await self._record_resume_audit(task_id)
        # mock-safe: resume only updates bookkeeping; no production action runs.
        execution_result = {
            "status": "completed",
            "production_executed": False,
            "resumed": True,
            "mock": True,
        }
        state["stage"] = "completed"
        state["approval_status"] = "approved"
        state["audit_refs"] = list(state.get("audit_refs", [])) + [audit_ref]
        state["execution_result"] = execution_result
        updated = await self.store.update_workflow_state(
            task_id,
            stage="completed",
            state=state,
            approval_required=bool(workflow["approval_required"]),
            approval_status="approved",
            risk_level=str(workflow["risk_level"] or "unknown"),
            execution_result=execution_result,
        )
        if updated is None:
            raise ResumeError(f"workflow not found: {task_id}")
        await send_notification(
            task_id, "workflow.resumed", f"workflow {task_id} resumed and completed"
        )
        return updated

    async def _approval_granted(self, workflow: dict) -> bool:
        request_id = _approval_request_id(workflow)
        if not request_id:
            return False
        try:
            approval = await ApprovalHttpClient().get_approval(request_id)
        except Exception:
            return False
        return approval.get("status") == "approved"

    async def _record_resume_audit(self, task_id: str) -> str:
        try:
            result = await AuditHttpClient().record_event(
                task_id=task_id,
                agent="resume-engine",
                decision_type="workflow_resume",
                summary=f"workflow {task_id} resumed after approval",
                result="resumed",
                artifact_refs={},
            )
            return str(result.get("audit_id") or f"audit-local:{task_id}")
        except Exception:
            return f"audit-local:{task_id}"


def _approval_request_id(workflow: dict) -> str:
    state = workflow.get("state")
    request_id = state.get("approval_request_id", "") if isinstance(state, dict) else ""
    if not request_id or str(request_id).startswith("approval-local:"):
        return ""
    return str(request_id)
