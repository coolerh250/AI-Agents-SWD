import uuid
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from dispatch import dispatch_task
from shared.sdk.agent_team.capabilities import ANALYZE_REQUIREMENTS
from shared.sdk.agent_team.context import build_team_context
from shared.sdk.agent_team.service import TeamService
from shared.sdk.audit.client import AuditClient
from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
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
    # AT-M2-TEAM-CORE. project_id is what makes a run autonomous-path: it names the project
    # whose TEAM owns the work. Without it the workflow behaves exactly as it did before.
    project_id: str
    team_context: dict[str, Any]
    # not_applicable | formed | failed -- a failed team is NOT a project-less run.
    team_formation: str
    routing: dict[str, Any]


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
    "project_id",
    "team_context",
    "team_formation",
    "routing",
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


def _team_service() -> TeamService:
    """The orchestrator's team runtime. An overridable seam for tests and the demo.

    Team formation and routing publish onto the team stream and the audit stream, so the service
    is given the same event bus and audit client the agents use rather than being left silent.
    """
    bus = RedisStreamEventBus()
    return TeamService(event_bus=bus, audit_client=AuditClient(event_bus=bus))


TEAM_NOT_APPLICABLE = "not_applicable"
TEAM_FORMED = "formed"
TEAM_FAILED = "failed"


async def team_formation_node(state: WorkflowState) -> dict:
    """Form the project's runtime team, if this run belongs to a project.

    Three outcomes, and they must stay distinguishable:

    ``not_applicable``  this run names no project. The legacy task pipeline is unchanged, which
                        is a legitimate flow and still dispatches.
    ``formed``          the team exists; every later hop carries its context.
    ``failed``          a project WAS named and the team could not be formed. This is not the
                        same thing as having no team, and it must not be treated as one: an
                        earlier version degraded to ``{}`` here, which made a database outage
                        indistinguishable from a project-less run and quietly put the work back
                        on the compile-time pipeline. It now fails closed at ``route_next``.
    """
    project_id = state.get("project_id") or ""
    if not project_id:
        update = {"stage": "policy_check", "team_formation": TEAM_NOT_APPLICABLE}
        await _persist(state, update)
        return update
    goal_ref = str(state["request"].get("description") or state["request"].get("type") or "goal")
    with start_span(
        "workflow.team_formation",
        **{
            "service.name": "orchestrator",
            "task_id": state["task_id"],
            "workflow_id": state["workflow_id"],
            "agent": "orchestrator",
            "event_type": "team_formation",
            "project_id": project_id,
        },
    ):
        try:
            formed = await _team_service().form_team(project_id, goal_ref)
            context = build_team_context(
                project_id=project_id,
                goal_ref=goal_ref,
                thread_id=formed.get("thread_id"),
                workflow_stage="policy_check",
            )
            members = [m.get("functional_role") for m in formed.get("members", [])]
            formation = TEAM_FORMED
        except Exception as exc:  # recorded, never silently downgraded to the legacy path
            context = {}
            members = []
            formation = TEAM_FAILED
            state["artifacts"].append(
                {"type": "team_formation_failure", "project_id": project_id, "error": str(exc)[:200]}
            )
    update = {
        "team_context": context,
        "team_formation": formation,
        "assigned_agents": state["assigned_agents"] + [r for r in members if r],
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


async def route_next_node(state: WorkflowState) -> dict:
    """Ask the team who takes the first piece of work, and record why.

    This is where the successor stops being a constant. On a run with no team the node records
    that it did not route and the workflow continues exactly as before; on a team run the answer
    comes from the members' declared capabilities as they are right now.
    """
    formation = state.get("team_formation") or TEAM_NOT_APPLICABLE
    if formation == TEAM_FAILED:
        # Fail closed. A project was named and its team could not be formed, so nothing here
        # knows who should do the work -- and guessing means the compile-time pipeline.
        update = {
            "routing": {
                "outcome": "team_unavailable",
                "requested_capability": ANALYZE_REQUIREMENTS,
                "reason": (
                    f"the runtime team for project {state.get('project_id', '')} could not be "
                    "formed, so no successor can be selected; this is NOT a project-less run"
                ),
            }
        }
        await _persist(state, update)
        return update

    context = state.get("team_context") or {}
    project_id = context.get("project_id") or ""
    if not project_id:
        update = {
            "routing": {
                "outcome": "not_routed",
                "reason": "this run names no project, so it stays on the legacy task pipeline",
            }
        }
        await _persist(state, update)
        return update
    with start_span(
        "workflow.route_next",
        **{
            "service.name": "orchestrator",
            "task_id": state["task_id"],
            "workflow_id": state["workflow_id"],
            "agent": "orchestrator",
            "event_type": "route_next",
            "project_id": project_id,
            "capability": ANALYZE_REQUIREMENTS,
        },
    ):
        try:
            decision, _record = await _team_service().decide_route(
                project_id=project_id,
                capability=ANALYZE_REQUIREMENTS,
                workflow_stage=state["stage"],
                task_id=state["task_id"],
                workflow_id=state["workflow_id"],
            )
            routing = decision.as_record()
        except Exception:  # an unreachable router must not silently pick a successor
            routing = {
                "outcome": "no_eligible_agent",
                "requested_capability": ANALYZE_REQUIREMENTS,
                "reason": "the router could not be reached, so no successor was selected",
            }
    update = {"routing": routing}
    await _persist(state, update)
    return update


# The only outcome that may dispatch without a routing decision behind it: a run that names no
# project was never on the autonomous path. Everything else must be selected or blocked --
# listing the permitted values rather than the blocked ones keeps a new outcome fail-closed.
DISPATCHABLE_ROUTING_OUTCOMES = frozenset({"selected", "not_routed"})

BLOCKED_STAGE_FOR_OUTCOME = {
    "team_unavailable": "blocked_team_unavailable",
    "requires_human_approval": "blocked_requires_human_approval",
}


def select_route(state: WorkflowState) -> str:
    """The workflow's first genuine conditional edge.

    Work with a capable owner is dispatched; work with none is parked for a human. Nothing here
    can reach a compile-time successor, and an unrecognised outcome parks rather than dispatches.
    """
    outcome = str((state.get("routing") or {}).get("outcome") or "")
    if outcome in DISPATCHABLE_ROUTING_OUTCOMES:
        return "dispatch"
    return "team_blocked"


async def team_blocked_node(state: WorkflowState) -> dict:
    """The work has no owner. Park it and say why; never fall back to a fixed agent.

    The stage distinguishes WHY it parked -- an unavailable team is an infrastructure problem an
    operator can fix, while no eligible agent is a team-composition decision. Collapsing them
    would hide an outage behind a staffing message.
    """
    routing = state.get("routing") or {}
    outcome = str(routing.get("outcome") or "no_eligible_agent")
    reason = str(routing.get("reason") or "no eligible agent")
    stage = BLOCKED_STAGE_FOR_OUTCOME.get(outcome, "blocked_no_eligible_agent")
    update = {
        "stage": stage,
        "execution_result": {
            "status": stage,
            "production_executed": False,
            "dispatched": False,
            "routing_outcome": outcome,
            "reason": reason,
        },
    }
    WORKFLOW_TOTAL.labels(status=stage).inc()
    await _persist(state, update)
    await send_notification(
        state["task_id"],
        f"workflow.{stage}",
        f"workflow {state['task_id']} parked ({outcome}): {reason}",
    )
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
            team_context=state.get("team_context") or None,
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
    graph.add_node("team_formation", team_formation_node)
    graph.add_node("policy", policy_node)
    graph.add_node("approval", approval_node)
    graph.add_node("audit", audit_node)
    graph.add_node("route_next", route_next_node)
    graph.add_node("dispatch", dispatch_node)
    graph.add_node("team_blocked", team_blocked_node)
    graph.add_edge(START, "intake")
    graph.add_edge("intake", "requirement")
    graph.add_edge("requirement", "team_formation")
    graph.add_edge("team_formation", "policy")
    graph.add_edge("policy", "approval")
    graph.add_edge("approval", "audit")
    graph.add_edge("audit", "route_next")
    # AT-M2-TEAM-CORE: the graph's first conditional edge. Which node runs next is decided at
    # runtime from the team's capabilities, not fixed when this module is imported.
    graph.add_conditional_edges(
        "route_next", select_route, {"dispatch": "dispatch", "team_blocked": "team_blocked"}
    )
    graph.add_edge("dispatch", END)
    graph.add_edge("team_blocked", END)
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
        "project_id": str(request.get("project_id") or request.get("request", {}).get("project_id") or ""),
        "team_context": {},
        "team_formation": "not_applicable",
        "routing": {},
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
        "project_id": "string - the project whose team owns this run, when there is one",
        "team_context": "object - project/goal/thread the runtime team is working on",
        "team_formation": "string - not_applicable | formed | failed",
        "routing": "object - the runtime routing decision and why it was made",
    }
