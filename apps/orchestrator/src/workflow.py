import uuid
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from dispatch import dispatch_task
from shared.sdk.http_clients.approval_http_client import ApprovalHttpClient
from shared.sdk.http_clients.audit_http_client import AuditHttpClient
from shared.sdk.http_clients.policy_http_client import PolicyHttpClient
from shared.sdk.notifications.client import send_notification
from shared.sdk.observability.metrics import WORKFLOW_TOTAL
from shared.sdk.observability.tracing import (
    generate_trace_id,
    get_current_trace_id,
    start_span,
)
from shared.sdk.workflow_store.store import WorkflowStore


class WorkflowState(TypedDict):
    task_id: str
    workflow_id: str
    trace_id: str
    source: str
    request: dict[str, Any]
    stage: str
    artifacts: list[dict[str, Any]]
    assigned_agents: list[str]
    approval_required: bool
    approval_status: str
    approval_request_id: str
    retry_count: int
    audit_refs: list[str]
    risk_level: str
    execution_result: dict[str, Any]


REQUIRED_STATE_FIELDS = [
    "task_id",
    "workflow_id",
    "trace_id",
    "source",
    "request",
    "stage",
    "artifacts",
    "assigned_agents",
    "approval_required",
    "approval_status",
    "approval_request_id",
    "retry_count",
    "audit_refs",
    "risk_level",
    "execution_result",
]


async def _persist(state: WorkflowState, update: dict) -> None:
    """Best-effort persistence of the post-node state to workflow_states."""
    merged: dict = {**state, **update}
    try:
        await WorkflowStore().update_workflow_state(
            merged["task_id"],
            stage=merged["stage"],
            state=merged,
            approval_required=merged["approval_required"],
            approval_status=merged["approval_status"],
            risk_level=merged["risk_level"],
            execution_result=merged["execution_result"],
        )
    except Exception:  # persistence failure must not break the workflow
        pass


async def intake_node(state: WorkflowState) -> dict:
    update = {"stage": "requirement_analysis"}
    await _persist(state, update)
    return update


async def requirement_node(state: WorkflowState) -> dict:
    spec = {
        "type": "requirement_spec",
        "request_type": state["request"].get("type", "unknown"),
        "summary": state["request"].get("description", "no description provided"),
    }
    update = {
        "artifacts": state["artifacts"] + [spec],
        "assigned_agents": ["requirement-agent"],
        "stage": "policy_check",
    }
    await _persist(state, update)
    return update


async def policy_node(state: WorkflowState) -> dict:
    """Delegate the policy decision to the policy-engine service over HTTP."""
    action = state["request"].get("type", "")
    with start_span(
        "workflow.policy_check",
        **{
            "service.name": "orchestrator",
            "task_id": state["task_id"],
            "workflow_id": state["workflow_id"],
            "agent": "orchestrator",
            "event_type": "policy_check",
            "policy.action": action,
        },
    ):
        try:
            decision = await PolicyHttpClient().evaluate(
                action, task_id=state["task_id"], workflow_id=state["workflow_id"]
            )
            approval_required = bool(decision.get("approval_required"))
            risk_level = str(decision.get("risk_level", "low"))
        except Exception:  # fail-safe: require approval if the policy engine is down
            approval_required = True
            risk_level = "unknown"
    update = {
        "approval_required": approval_required,
        "risk_level": risk_level,
        "stage": "approval",
    }
    await _persist(state, update)
    return update


async def approval_node(state: WorkflowState) -> dict:
    """Create an approval request via the approval-engine when one is required."""
    if not state["approval_required"]:
        update = {"stage": "audit", "approval_status": "not_required"}
        await _persist(state, update)
        return update
    with start_span(
        "workflow.approval_request",
        **{
            "service.name": "orchestrator",
            "task_id": state["task_id"],
            "workflow_id": state["workflow_id"],
            "agent": "orchestrator",
            "event_type": "approval_request",
            "risk_level": state["risk_level"],
        },
    ):
        try:
            result = await ApprovalHttpClient().request_approval(
                task_id=state["task_id"],
                action=state["request"].get("type", ""),
                risk_level=state["risk_level"],
                reason="restricted action requires human approval",
                workflow_id=state["workflow_id"],
            )
            request_id = str(result.get("request_id", ""))
            status = str(result.get("status", "pending"))
        except Exception:  # degrade gracefully if the approval engine is down
            request_id = f"approval-local:{state['task_id']}"
            status = "pending"
    update = {
        "stage": "waiting_approval",
        "approval_status": status,
        "approval_request_id": request_id,
    }
    await _persist(state, update)
    return update


async def audit_node(state: WorkflowState) -> dict:
    """Record a workflow audit event via the audit-service."""
    ref = f"audit-local:{state['task_id']}"
    with start_span(
        "workflow.audit",
        **{
            "service.name": "orchestrator",
            "task_id": state["task_id"],
            "workflow_id": state["workflow_id"],
            "agent": "orchestrator",
            "event_type": "workflow_audit",
        },
    ):
        try:
            result = await AuditHttpClient().record_event(
                task_id=state["task_id"],
                agent="orchestrator",
                decision_type="workflow",
                summary=f"workflow {state['task_id']} reached stage {state['stage']}",
                result=state["approval_status"],
                artifact_refs={"artifacts": state["artifacts"]},
                workflow_id=state["workflow_id"],
            )
            ref = str(result.get("audit_id") or ref)
        except Exception:  # degrade gracefully if the audit service is down
            pass
    update = {"audit_refs": state["audit_refs"] + [ref]}
    await _persist(state, update)
    return update


async def dispatch_node(state: WorkflowState) -> dict:
    """Dispatch the task to the agent pipeline, unless it is blocked on approval.

    A restricted action that has not been approved is never dispatched — it stays
    at ``waiting_approval``. Otherwise the node publishes a task.created event to
    stream.tasks; the agent pipeline then runs and the orchestrator's workflow
    event consumer drives the workflow to ``completed``. No production action is
    executed here.
    """
    task_id = state["task_id"]
    with start_span(
        "workflow.dispatch",
        **{
            "service.name": "orchestrator",
            "task_id": task_id,
            "workflow_id": state["workflow_id"],
            "agent": "orchestrator",
            "event_type": "workflow_dispatch",
            "stream": "stream.tasks",
        },
    ):
        if state["approval_required"] and state["approval_status"] != "approved":
            update = {
                "stage": "waiting_approval",
                "execution_result": {
                    "status": "blocked_pending_approval",
                    "production_executed": False,
                    "dispatched": False,
                },
            }
            await _persist(state, update)
            WORKFLOW_TOTAL.labels(status="waiting_approval").inc()
            await send_notification(
                task_id,
                "workflow.waiting_approval",
                f"workflow {task_id} is waiting for approval",
            )
            return update
        dispatched = await dispatch_task(
            task_id,
            state["workflow_id"],
            dict(state["request"]),
            state["source"],
            trace_id=state.get("trace_id", ""),
        )
        update = {
            "stage": "dispatched",
            "execution_result": {
                "status": "awaiting_agents",
                "production_executed": False,
                "dispatched": dispatched,
                "mock": True,
            },
        }
        WORKFLOW_TOTAL.labels(status="dispatched").inc()
        await _persist(state, update)
        await send_notification(
            task_id, "workflow.dispatched", f"workflow {task_id} dispatched to the agent pipeline"
        )
        return update


def build_workflow():
    graph = StateGraph(WorkflowState)
    graph.add_node("intake", intake_node)
    graph.add_node("requirement", requirement_node)
    graph.add_node("policy", policy_node)
    graph.add_node("approval", approval_node)
    graph.add_node("audit", audit_node)
    graph.add_node("dispatch", dispatch_node)
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "requirement")
    graph.add_edge("requirement", "policy")
    graph.add_edge("policy", "approval")
    graph.add_edge("approval", "audit")
    graph.add_edge("audit", "dispatch")
    graph.add_edge("dispatch", END)
    return graph.compile()


def _initial_state(request: dict) -> WorkflowState:
    # Prefer the active OpenTelemetry trace_id so the workflow correlation
    # block, /workflow/progress, and the Tempo-indexed spans all share one id.
    inherited_trace_id = (
        str(request.get("trace_id") or "") or get_current_trace_id() or generate_trace_id()
    )
    return {
        "task_id": request.get("task_id", "unknown"),
        "workflow_id": request.get("workflow_id") or f"wf-{uuid.uuid4().hex[:12]}",
        "trace_id": inherited_trace_id,
        "source": request.get("source", "unknown"),
        "request": request.get("request", {}),
        "stage": "intake",
        "artifacts": [],
        "assigned_agents": [],
        "approval_required": False,
        "approval_status": "none",
        "approval_request_id": "",
        "retry_count": 0,
        "audit_refs": [],
        "risk_level": "unknown",
        "execution_result": {},
    }


async def run_mock_workflow(request: dict) -> dict:
    # Open the workflow.run span first so the rest of the workflow inherits
    # this span's trace_id — that is the id Tempo indexes the trace under and
    # the id we surface via /workflow/progress so callers can pivot into Tempo.
    task_id = str(request.get("task_id", "unknown"))
    workflow_id_hint = str(request.get("workflow_id") or "")
    with start_span(
        "workflow.run",
        **{
            "service.name": "orchestrator",
            "task_id": task_id,
            "workflow_id": workflow_id_hint,
            "agent": "orchestrator",
            "event_type": "workflow_run",
            "request.type": request.get("request", {}).get("type", "unknown"),
        },
    ):
        initial = _initial_state(request)
        try:
            await WorkflowStore().create_workflow_state(
                initial["task_id"], dict(initial["request"]), stage="intake"
            )
        except Exception:  # persistence failure must not break the workflow
            pass
        workflow = build_workflow()
        final_state = await workflow.ainvoke(initial)
        return dict(final_state)


def workflow_state_schema() -> dict:
    return {
        "task_id": "string - unique task identifier",
        "workflow_id": "string - orchestrator workflow run id",
        "trace_id": "string - distributed-trace id shared across the workflow",
        "source": "string - origin of the request",
        "request": "object - the original mock request payload",
        "stage": "string - current workflow stage",
        "artifacts": "array - artifacts produced during the workflow",
        "assigned_agents": "array - agents assigned to the task",
        "approval_required": "boolean - whether human approval is required",
        "approval_status": "string - none | pending | not_required",
        "approval_request_id": "string - approval-engine request id, when created",
        "retry_count": "integer - number of workflow retries",
        "audit_refs": "array - references to emitted audit events",
        "risk_level": "string - low | high | unknown",
        "execution_result": "object - final execution result",
    }
