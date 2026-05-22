from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from shared.sdk.http_clients.approval_http_client import ApprovalHttpClient
from shared.sdk.http_clients.audit_http_client import AuditHttpClient
from shared.sdk.http_clients.policy_http_client import PolicyHttpClient


class WorkflowState(TypedDict):
    task_id: str
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


async def intake_node(state: WorkflowState) -> dict:
    return {"stage": "requirement_analysis"}


async def requirement_node(state: WorkflowState) -> dict:
    spec = {
        "type": "requirement_spec",
        "request_type": state["request"].get("type", "unknown"),
        "summary": state["request"].get("description", "no description provided"),
    }
    return {
        "artifacts": state["artifacts"] + [spec],
        "assigned_agents": ["requirement-agent"],
        "stage": "policy_check",
    }


async def policy_node(state: WorkflowState) -> dict:
    """Delegate the policy decision to the policy-engine service over HTTP."""
    action = state["request"].get("type", "")
    try:
        decision = await PolicyHttpClient().evaluate(action)
        approval_required = bool(decision.get("approval_required"))
        risk_level = str(decision.get("risk_level", "low"))
    except Exception:  # fail-safe: require approval if the policy engine is down
        approval_required = True
        risk_level = "unknown"
    return {
        "approval_required": approval_required,
        "risk_level": risk_level,
        "stage": "approval",
    }


async def approval_node(state: WorkflowState) -> dict:
    """Create an approval request via the approval-engine when one is required."""
    if not state["approval_required"]:
        return {"stage": "audit", "approval_status": "not_required"}
    try:
        result = await ApprovalHttpClient().request_approval(
            task_id=state["task_id"],
            action=state["request"].get("type", ""),
            risk_level=state["risk_level"],
            reason="restricted action requires human approval",
        )
        request_id = str(result.get("request_id", ""))
        status = str(result.get("status", "pending"))
    except Exception:  # degrade gracefully if the approval engine is down
        request_id = f"approval-local:{state['task_id']}"
        status = "pending"
    return {
        "stage": "waiting_approval",
        "approval_status": status,
        "approval_request_id": request_id,
    }


async def audit_node(state: WorkflowState) -> dict:
    """Record a workflow audit event via the audit-service."""
    ref = f"audit-local:{state['task_id']}"
    try:
        result = await AuditHttpClient().record_event(
            task_id=state["task_id"],
            agent="orchestrator",
            decision_type="workflow",
            summary=f"workflow {state['task_id']} reached stage {state['stage']}",
            result=state["approval_status"],
            artifact_refs={"artifacts": state["artifacts"]},
        )
        ref = str(result.get("audit_id") or ref)
    except Exception:  # degrade gracefully if the audit service is down
        pass
    return {"audit_refs": state["audit_refs"] + [ref]}


async def final_node(state: WorkflowState) -> dict:
    if state["approval_required"]:
        return {
            "stage": "waiting_approval",
            "execution_result": {
                "status": "blocked_pending_approval",
                "production_executed": False,
            },
        }
    return {
        "stage": "completed",
        "execution_result": {"status": "completed", "production_executed": False, "mock": True},
    }


def build_workflow():
    graph = StateGraph(WorkflowState)
    graph.add_node("intake", intake_node)
    graph.add_node("requirement", requirement_node)
    graph.add_node("policy", policy_node)
    graph.add_node("approval", approval_node)
    graph.add_node("audit", audit_node)
    graph.add_node("final", final_node)
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "requirement")
    graph.add_edge("requirement", "policy")
    graph.add_edge("policy", "approval")
    graph.add_edge("approval", "audit")
    graph.add_edge("audit", "final")
    graph.add_edge("final", END)
    return graph.compile()


def _initial_state(request: dict) -> WorkflowState:
    return {
        "task_id": request.get("task_id", "unknown"),
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
    workflow = build_workflow()
    final_state = await workflow.ainvoke(_initial_state(request))
    return dict(final_state)


def workflow_state_schema() -> dict:
    return {
        "task_id": "string - unique task identifier",
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
