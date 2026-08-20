"""Step AT-M2-TEAM-CORE -- the executable demo scenario.

    Goal "Build a todo API"
      -> team formed
      -> members and capabilities visible
      -> requirement addresses development directly
      -> the router picks each successor from capability
      -> the reason is persisted
      -> QA's repair loop is routed too
    then a capability is withdrawn
      -> the routing decision CHANGES, with no operator naming the next agent

It drives the real orchestrator graph, the real StreamAgent publish path and the real router.
Persistence and transport are in-memory (no Postgres, no Redis, no container), which is the
strongest end-to-end proof available without starting infrastructure; every decision under test
is made by production code.
"""

from __future__ import annotations

import pytest

import workflow as orchestrator_workflow
from shared.sdk.agent_team import events as team_events
from shared.sdk.agent_team.capabilities import (
    AGENT_CAPABILITY_SEED,
    ANALYZE_REQUIREMENTS,
    FIX_DEFECTS,
    GENERATE_CODE,
    PLAN_DEPLOYMENT,
    VERIFY_QUALITY,
)
from shared.sdk.agent_team.context import build_team_context
from shared.sdk.agent_team.service import TeamService
from shared.sdk.base_agent.stream_agent import StreamAgent
from tests.agent_team_fakes import InMemoryTeamStore, RecordingAuditClient, RecordingEventBus

PROJECT = "44444444-4444-4444-4444-444444444444"
GOAL = "Build a todo API"


class _NoApprovalPolicy:
    """A low-risk goal: the policy engine allows it without human approval."""

    async def evaluate(self, action, task_id="", workflow_id=""):
        return {"approval_required": False, "risk_level": "low"}


class _LocalAudit:
    async def record_event(self, **kwargs):
        return {"audit_id": "audit-local-demo"}


class _NoWorkflowStore:
    """The workflow already tolerates a down store; stubbing it keeps the demo off the network."""

    async def create_workflow_state(self, *args, **kwargs):
        return None

    async def update_workflow_state(self, *args, **kwargs):
        return None


def _offline(monkeypatch):
    """Keep the demo to in-memory infrastructure: no Postgres, no Redis, no HTTP."""
    monkeypatch.setattr(orchestrator_workflow, "PolicyHttpClient", _NoApprovalPolicy)
    monkeypatch.setattr(orchestrator_workflow, "AuditHttpClient", _LocalAudit)
    monkeypatch.setattr(orchestrator_workflow, "WorkflowStore", _NoWorkflowStore)

    async def _no_notification(*args, **kwargs):
        return None

    monkeypatch.setattr(orchestrator_workflow, "send_notification", _no_notification)


@pytest.fixture
def team():
    store = InMemoryTeamStore()
    bus = RecordingEventBus()
    audit = RecordingAuditClient()
    return TeamService(store=store, event_bus=bus, audit_client=audit), store, bus, audit


async def test_demo_goal_to_team_to_message_to_route_to_result(team, monkeypatch, capsys):
    service, store, bus, audit = team
    monkeypatch.setattr(orchestrator_workflow, "_team_service", lambda: service)
    _offline(monkeypatch)

    # --- 1. GOAL -> TEAM ------------------------------------------------------------------------
    result = await orchestrator_workflow.run_mock_workflow(
        {
            "task_id": "demo-at-m2-1",
            "source": "operator",
            "project_id": PROJECT,
            "request": {"type": "dev.feature", "description": GOAL},
        }
    )
    assert result["team_context"]["project_id"] == PROJECT
    assert result["team_context"]["goal_ref"] == GOAL

    roster = await service.roster(PROJECT)
    assert len(roster) == len(AGENT_CAPABILITY_SEED), (
        "a goal must produce a durable team holding every recruitable runtime agent"
    )
    assert all(m["principal_type"] == "runtime_agent" for m in roster)
    assert all(m["membership_state"] == "active" for m in roster)
    capabilities = {m["agent_key"]: set(m["capabilities"]) for m in roster}
    assert capabilities["qa-agent"] == {VERIFY_QUALITY}
    assert capabilities["requirement-agent"] == {ANALYZE_REQUIREMENTS, "clarify_requirements"}

    # --- 2. CONDITIONAL ROUTE -------------------------------------------------------------------
    # The workflow's own conditional edge chose dispatch because a capable agent exists.
    assert result["routing"]["outcome"] == "selected"
    assert result["routing"]["requested_capability"] == ANALYZE_REQUIREMENTS
    assert result["routing"]["selected_role"] == "requirement"
    assert result["stage"] == "dispatched"
    assert result["execution_result"]["production_executed"] is False

    # --- 3. ADDRESSED MESSAGE -------------------------------------------------------------------
    thread_id = result["team_context"]["thread_id"]
    proposal = await service.send_message(
        project_id=PROJECT,
        thread_id=thread_id,
        sender_agent_key="requirement-agent",
        to_agent_key="development-agent",
        message_type="proposal",
        summary="Todo API: create/list/complete/delete endpoints over a persisted store",
        artifact_refs={"requirement_spec": "spec-1"},
    )
    reply = await service.send_message(
        project_id=PROJECT,
        thread_id=thread_id,
        sender_agent_key="development-agent",
        to_agent_key="requirement-agent",
        message_type="message",
        summary="acknowledged; generating the endpoint module and its test stub",
        parent_message_id=str(proposal["message_id"]),
    )
    assert str(proposal["sender_principal_id"]) != str(proposal["recipient_principal_id"])
    assert str(reply["parent_message_id"]) == str(proposal["message_id"])
    assert proposal["audit_ref"] and reply["audit_ref"]
    inbox = await service.inbox(PROJECT, "development-agent")
    assert [m["summary"] for m in inbox] == [proposal["summary"]]

    # --- 4. EVERY HOP IS ROUTED, NOT COMPILED ---------------------------------------------------
    hops = [
        (ANALYZE_REQUIREMENTS, "requirement-agent", "stream.requirements"),
        (GENERATE_CODE, "development-agent", "stream.development"),
        (VERIFY_QUALITY, "qa-agent", "stream.qa"),
        (PLAN_DEPLOYMENT, "devops-agent", "stream.deployments"),
    ]
    for capability, expected_agent, expected_stream in hops:
        decision, record = await service.decide_route(
            project_id=PROJECT, capability=capability, task_id="demo-at-m2-1"
        )
        assert decision.selected_agent_key == expected_agent, capability
        assert decision.selected_stream == expected_stream, capability
        assert record["reason"], "a routing decision without a reason is not evidence"
        assert record["audit_ref"]

    # --- 5. THE REPAIR LOOP IS ROUTED TOO -------------------------------------------------------
    repair, repair_record = await service.decide_route(
        project_id=PROJECT, capability=FIX_DEFECTS, task_id="demo-at-m2-1"
    )
    assert repair.selected_agent_key == "development-agent-autofix"
    assert repair.selected_stream == "stream.development.autofix"
    assert repair_record["outcome"] == "selected"

    # --- 6. WITHDRAW A CAPABILITY -- THE ROUTE MOVES ---------------------------------------------
    before = await service.decide_route(project_id=PROJECT, capability=VERIFY_QUALITY)
    assert before[0].selected_agent_key == "qa-agent"

    await service.set_membership_state(PROJECT, "qa-agent", "left")

    after, after_record = await service.decide_route(project_id=PROJECT, capability=VERIFY_QUALITY)
    assert after.outcome == "no_eligible_agent"
    assert after.selected_agent_key is None
    assert after_record["reason"] != before[1]["reason"]

    # And it moves rather than merely failing when someone else picks the capability up.
    await service.set_agent_capabilities("devops-agent", (PLAN_DEPLOYMENT, VERIFY_QUALITY))
    relocated, _ = await service.decide_route(project_id=PROJECT, capability=VERIFY_QUALITY)
    assert relocated.selected_agent_key == "devops-agent"
    assert relocated.selected_stream == "stream.deployments"

    # --- 7. EVIDENCE ------------------------------------------------------------------------------
    history = await service.routing_history(PROJECT)
    assert len(history) >= 8
    assert {h["outcome"] for h in history} >= {"selected", "no_eligible_agent"}
    assert team_events.AUDIT_TEAM_FORMED in audit.decision_types()
    assert team_events.AUDIT_ROUTING_DECIDED in audit.decision_types()
    assert team_events.AUDIT_MESSAGE_POSTED in audit.decision_types()
    assert not any(e.get("production_executed") for e in audit.events)

    print("\n--- AT-M2 demo -------------------------------------------------")
    print(f"goal          {GOAL}")
    print(f"team          {len(roster)} runtime-agent members on project {PROJECT[:8]}")
    for member in roster:
        print(f"  {member['agent_key']:<30} {sorted(member['capabilities'])}")
    print(f"message       requirement-agent -> development-agent ({proposal['message_type']})")
    for capability, agent, _stream in hops:
        print(f"route         {capability:<22} -> {agent}")
    print(f"repair loop   {FIX_DEFECTS:<22} -> {repair.selected_agent_key}")
    print(f"qa withdrawn  {VERIFY_QUALITY:<22} -> {after.outcome}")
    print(f"relocated     {VERIFY_QUALITY:<22} -> {relocated.selected_agent_key}")
    print(f"evidence      {len(history)} routing decisions, {len(audit.events)} audit events")
    print("----------------------------------------------------------------")
    assert "AT-M2 demo" in capsys.readouterr().out


async def test_demo_agent_publishes_to_the_routed_stream_not_its_class_attribute(team):
    """The same run, seen from an agent: routing authority has left the source file."""
    service, _store, bus, _audit = team
    await service.form_team(PROJECT, GOAL)

    class DevelopmentLike(StreamAgent):
        name = "development-agent"
        input_stream = "stream.development"
        output_stream = "stream.qa"
        declared_capabilities = (GENERATE_CODE,)
        successor_capability = VERIFY_QUALITY

        async def handle(self, payload: dict) -> dict:
            await self.publish_next({"task_id": payload["task_id"], "event": "code.generated"})
            return {"summary": "generated"}

    agent = DevelopmentLike(event_bus=bus, team_service=service)
    context = build_team_context(project_id=PROJECT, goal_ref=GOAL)

    # process() also writes an audit event on the same bus, so the routed hop is identified by
    # the work streams published during it rather than by whatever was published last.
    work_streams = {
        d.transport_stream
        for d in __import__(
            "shared.sdk.agent_team.capabilities", fromlist=["AGENT_CAPABILITY_SEED"]
        ).AGENT_CAPABILITY_SEED
    }

    def routed_since(mark: int) -> list[str]:
        return [s for s in bus.streams()[mark:] if s in work_streams]

    mark = len(bus.streams())
    await agent.process({"task_id": "demo-at-m2-2", "team_context": context})
    assert routed_since(mark) == ["stream.qa"]
    assert agent.last_routing_decision.selected_agent_key == "qa-agent"

    # Give the QA role to devops instead. The class attribute still says "stream.qa"; the work
    # does not go there.
    await service.set_membership_state(PROJECT, "qa-agent", "left")
    await service.set_agent_capabilities("devops-agent", (PLAN_DEPLOYMENT, VERIFY_QUALITY))

    mark = len(bus.streams())
    await agent.process({"task_id": "demo-at-m2-3", "team_context": context})
    assert agent.output_stream == "stream.qa", "the constant is untouched"
    assert routed_since(mark) == ["stream.deployments"], "the work followed the capability"
    assert agent.last_routing_decision.selected_agent_key == "devops-agent"


async def test_demo_workflow_takes_the_blocked_branch_when_no_agent_can_start(team, monkeypatch):
    """The conditional edge is real: with nobody eligible the graph goes somewhere else."""
    service, _store, _bus, _audit = team

    class DevOpsOnlyTeam(TeamService):
        """A project whose team was formed without anyone who can analyse requirements."""

        async def form_team(self, project_id, goal_ref, agent_keys=None, declarations=None):
            return await super().form_team(project_id, goal_ref, agent_keys=("devops-agent",))

    limited = DevOpsOnlyTeam(
        store=service.store, event_bus=service.event_bus, audit_client=service.audit_client
    )
    monkeypatch.setattr(orchestrator_workflow, "_team_service", lambda: limited)
    _offline(monkeypatch)

    result = await orchestrator_workflow.run_mock_workflow(
        {
            "task_id": "demo-at-m2-blocked",
            "source": "operator",
            "project_id": PROJECT,
            "request": {"type": "dev.feature", "description": GOAL},
        }
    )
    assert result["routing"]["outcome"] == "no_eligible_agent"
    assert result["stage"] == "blocked_no_eligible_agent"
    assert result["execution_result"]["dispatched"] is False
    assert result["execution_result"]["production_executed"] is False
