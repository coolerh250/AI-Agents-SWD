"""Step AT-M2-TEAM-CORE -- focused tests for runtime team formation and capability routing.

The property under test throughout is that the successor of a piece of work is decided from the
team as it is NOW, not from a constant compiled into an agent module. Several tests therefore
change the team and assert the routing decision moves; a test that only checked a happy path
would pass equally well against the old hard-coded pipeline.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from shared.sdk.agent_team import events as team_events
from shared.sdk.agent_team.capabilities import (
    AGENT_CAPABILITY_SEED,
    ANALYZE_REQUIREMENTS,
    APPROVAL_REQUIRED_CAPABILITIES,
    FIX_DEFECTS,
    GENERATE_CODE,
    KNOWN_CAPABILITIES,
    PLAN_DEPLOYMENT,
    VERIFY_QUALITY,
    AgentCapabilityDeclaration,
)
from shared.sdk.agent_team.context import build_team_context, team_context_of, with_team_context
from shared.sdk.agent_team.models import TeamMessageCreate
from shared.sdk.agent_team.router import (
    RoutingCandidate,
    RoutingRequest,
    route,
)
from shared.sdk.agent_team.service import TeamService
from tests.agent_team_fakes import InMemoryTeamStore, RecordingAuditClient, RecordingEventBus

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "11111111-1111-1111-1111-111111111111"
GOAL = "Build a todo API"


def service() -> tuple[TeamService, InMemoryTeamStore, RecordingEventBus, RecordingAuditClient]:
    store = InMemoryTeamStore()
    bus = RecordingEventBus()
    audit = RecordingAuditClient()
    return TeamService(store=store, event_bus=bus, audit_client=audit), store, bus, audit


def candidate(agent_key: str, role: str, caps: tuple[str, ...], **kwargs) -> RoutingCandidate:
    return RoutingCandidate(
        principal_id=f"principal-{agent_key}",
        agent_key=agent_key,
        role=role,
        capabilities=frozenset(caps),
        transport_stream=kwargs.pop("transport_stream", f"stream.{role}"),
        **kwargs,
    )


# --- the router ---------------------------------------------------------------------------------


def test_router_selects_the_only_member_declaring_the_capability():
    decision = route(
        RoutingRequest(requested_capability=VERIFY_QUALITY, project_id=PROJECT),
        [
            candidate("development-agent", "development", (GENERATE_CODE,)),
            candidate("qa-agent", "qa", (VERIFY_QUALITY,)),
        ],
    )
    assert decision.outcome == "selected"
    assert decision.selected_agent_key == "qa-agent"
    assert decision.selected_stream == "stream.qa"
    assert VERIFY_QUALITY in decision.reason


def test_router_reports_no_eligible_agent_rather_than_guessing():
    decision = route(
        RoutingRequest(requested_capability=VERIFY_QUALITY, project_id=PROJECT),
        [candidate("development-agent", "development", (GENERATE_CODE,))],
    )
    assert decision.outcome == "no_eligible_agent"
    assert decision.selected_principal_id is None
    assert decision.selected_stream is None
    rejections = {c["agent_key"]: c["rejected_because"] for c in decision.candidates_considered}
    assert rejections["development-agent"] == "capability_not_declared"


def test_router_ignores_a_member_who_has_left_and_one_whose_profile_is_disabled():
    decision = route(
        RoutingRequest(requested_capability=GENERATE_CODE, project_id=PROJECT),
        [
            candidate(
                "development-agent", "development", (GENERATE_CODE,), membership_state="left"
            ),
            candidate("backup-dev", "development", (GENERATE_CODE,), profile_status="disabled"),
        ],
    )
    assert decision.outcome == "no_eligible_agent"
    rejections = {c["agent_key"]: c["rejected_because"] for c in decision.candidates_considered}
    assert rejections["development-agent"] == "membership_state=left"
    assert rejections["backup-dev"] == "profile_status=disabled"


def test_router_prefers_the_specialist_over_the_generalist_and_says_so():
    decision = route(
        RoutingRequest(requested_capability=FIX_DEFECTS, project_id=PROJECT),
        [
            candidate("generalist", "development", (GENERATE_CODE, FIX_DEFECTS, VERIFY_QUALITY)),
            candidate("fixer", "development", (FIX_DEFECTS,)),
        ],
    )
    assert decision.selected_agent_key == "fixer"
    assert "specialised" in decision.reason


def test_router_is_deterministic_for_identical_teams():
    team = [
        candidate("alpha", "development", (GENERATE_CODE,)),
        candidate("bravo", "development", (GENERATE_CODE,)),
    ]
    request = RoutingRequest(requested_capability=GENERATE_CODE, project_id=PROJECT)
    assert (
        route(request, team).selected_agent_key
        == route(request, list(reversed(team))).selected_agent_key
    )


def test_a_production_effect_capability_is_never_routed_to_an_agent():
    """The L5 boundary: routing selects a worker, it has never been able to authorize an act."""
    for capability in sorted(APPROVAL_REQUIRED_CAPABILITIES):
        decision = route(
            RoutingRequest(requested_capability=capability, project_id=PROJECT),
            [candidate("eager-agent", "devops", (capability,))],
        )
        assert decision.outcome == "requires_human_approval", capability
        assert decision.selected_principal_id is None
        assert decision.selected_stream is None


def test_a_workflow_waiting_on_a_human_routes_nothing():
    decision = route(
        RoutingRequest(
            requested_capability=GENERATE_CODE,
            project_id=PROJECT,
            workflow_stage="waiting_approval",
        ),
        [candidate("development-agent", "development", (GENERATE_CODE,))],
    )
    assert decision.outcome == "no_eligible_agent"
    assert "waiting on a human decision" in decision.reason


def test_a_candidate_with_no_transport_cannot_be_selected():
    decision = route(
        RoutingRequest(requested_capability=GENERATE_CODE, project_id=PROJECT),
        [candidate("ghost", "development", (GENERATE_CODE,), transport_stream=None)],
    )
    assert decision.outcome == "no_eligible_agent"
    assert decision.candidates_considered[0]["rejected_because"] == "no_transport_stream"


# --- team formation -----------------------------------------------------------------------------


async def test_forming_a_team_creates_principals_members_and_a_thread():
    svc, store, bus, audit = service()
    formed = await svc.form_team(PROJECT, GOAL)
    assert len(formed["members"]) == len(AGENT_CAPABILITY_SEED)
    assert formed["thread_id"]
    roster = await svc.roster(PROJECT)
    assert {m["agent_key"] for m in roster} == {d.agent_key for d in AGENT_CAPABILITY_SEED}
    assert all(m["principal_type"] == "runtime_agent" for m in roster)
    assert team_events.EVENT_TEAM_FORMED in [
        e["event"] for e in bus.events_on(team_events.STREAM_TEAM)
    ]
    assert team_events.AUDIT_TEAM_FORMED in audit.decision_types()
    assert team_events.AUDIT_MEMBER_JOINED in audit.decision_types()


async def test_forming_a_team_twice_does_not_duplicate_members():
    svc, store, _, _ = service()
    await svc.form_team(PROJECT, GOAL)
    await svc.form_team(PROJECT, GOAL)
    roster = await svc.roster(PROJECT)
    assert len(roster) == len(AGENT_CAPABILITY_SEED)
    assert len(store.principals) == len(AGENT_CAPABILITY_SEED)


async def test_a_team_can_be_formed_from_a_subset_of_agents():
    svc, _, _, _ = service()
    await svc.form_team(PROJECT, GOAL, agent_keys=("qa-agent", "devops-agent"))
    assert {m["agent_key"] for m in await svc.roster(PROJECT)} == {"qa-agent", "devops-agent"}


# --- addressed messaging ------------------------------------------------------------------------


async def test_requirement_agent_addresses_development_agent_durably():
    svc, store, bus, audit = service()
    formed = await svc.form_team(PROJECT, GOAL)
    message = await svc.send_message(
        project_id=PROJECT,
        thread_id=formed["thread_id"],
        sender_agent_key="requirement-agent",
        to_agent_key="development-agent",
        message_type="proposal",
        summary="Todo API needs create/list/delete endpoints and a persistence layer",
    )
    assert message is not None
    sender = await svc.principal_for_agent(PROJECT, "requirement-agent")
    recipient = await svc.principal_for_agent(PROJECT, "development-agent")
    assert str(message["sender_principal_id"]) == sender
    assert str(message["recipient_principal_id"]) == recipient
    assert sender != recipient, "two distinct runtime identities must be involved"
    assert message["audit_ref"], "a collaboration record that is not attributable is not evidence"
    assert len(store.messages) == 1
    assert team_events.AUDIT_MESSAGE_POSTED in audit.decision_types()
    assert team_events.EVENT_MESSAGE_POSTED in [
        e["event"] for e in bus.events_on(team_events.STREAM_TEAM)
    ]


async def test_a_reply_names_its_parent_and_reaches_the_original_sender():
    svc, _, _, _ = service()
    formed = await svc.form_team(PROJECT, GOAL)
    first = await svc.send_message(
        project_id=PROJECT,
        thread_id=formed["thread_id"],
        sender_agent_key="requirement-agent",
        to_agent_key="development-agent",
        summary="please implement the todo endpoints",
    )
    reply = await svc.send_message(
        project_id=PROJECT,
        thread_id=formed["thread_id"],
        sender_agent_key="development-agent",
        to_agent_key="requirement-agent",
        summary="endpoints generated; three files written",
        parent_message_id=str(first["message_id"]),
    )
    assert str(reply["parent_message_id"]) == str(first["message_id"])
    inbox = await svc.inbox(PROJECT, "requirement-agent")
    assert [str(m["message_id"]) for m in inbox] == [str(reply["message_id"])]


async def test_an_inbox_excludes_the_agents_own_messages():
    svc, _, _, _ = service()
    formed = await svc.form_team(PROJECT, GOAL)
    await svc.send_message(
        project_id=PROJECT,
        thread_id=formed["thread_id"],
        sender_agent_key="qa-agent",
        to_team=True,
        summary="starting verification",
    )
    assert await svc.inbox(PROJECT, "qa-agent") == []
    assert len(await svc.inbox(PROJECT, "development-agent")) == 1


def test_an_unaddressed_message_is_rejected_by_the_model():
    with pytest.raises(ValueError, match="recipient"):
        TeamMessageCreate(
            thread_id="22222222-2222-2222-2222-222222222222",
            project_id=PROJECT,
            sender_principal_id="33333333-3333-3333-3333-333333333333",
            message_type="message",
            summary="who is this for?",
        )


# --- routing on a real team ---------------------------------------------------------------------


async def test_capability_routing_selects_and_records_a_reason():
    svc, store, bus, audit = service()
    await svc.form_team(PROJECT, GOAL)
    decision, record = await svc.decide_route(project_id=PROJECT, capability=VERIFY_QUALITY)
    assert decision.selected_agent_key == "qa-agent"
    assert record["outcome"] == "selected"
    assert record["reason"]
    assert record["audit_ref"]
    assert team_events.AUDIT_ROUTING_DECIDED in audit.decision_types()
    assert team_events.EVENT_ROUTING_DECIDED in [
        e["event"] for e in bus.events_on(team_events.STREAM_TEAM)
    ]
    assert len(await svc.routing_history(PROJECT)) == 1


async def test_removing_a_member_changes_the_routing_decision_with_no_operator_input():
    """Acceptance 4. The same request, a different team, a different answer."""
    svc, _, _, _ = service()
    await svc.form_team(PROJECT, GOAL)
    before, _ = await svc.decide_route(project_id=PROJECT, capability=VERIFY_QUALITY)
    assert before.selected_agent_key == "qa-agent"

    await svc.set_membership_state(PROJECT, "qa-agent", "left")

    after, record = await svc.decide_route(project_id=PROJECT, capability=VERIFY_QUALITY)
    assert after.outcome == "no_eligible_agent"
    assert after.selected_agent_key is None
    assert record["outcome"] == "no_eligible_agent"
    assert after.reason != before.reason


async def test_moving_a_capability_to_another_agent_moves_the_work():
    """The stronger form: work relocates rather than merely failing."""
    svc, _, _, _ = service()
    await svc.form_team(PROJECT, GOAL)
    first, _ = await svc.decide_route(project_id=PROJECT, capability=FIX_DEFECTS)
    assert first.selected_agent_key == "development-agent-autofix"

    await svc.set_agent_capabilities("development-agent-autofix", ())
    await svc.set_agent_capabilities("development-agent", (GENERATE_CODE, FIX_DEFECTS))

    second, _ = await svc.decide_route(project_id=PROJECT, capability=FIX_DEFECTS)
    assert second.selected_agent_key == "development-agent"
    assert second.selected_stream == "stream.development"


async def test_a_paused_member_is_skipped_and_reinstating_them_restores_the_route():
    svc, _, _, _ = service()
    await svc.form_team(PROJECT, GOAL)
    await svc.set_membership_state(PROJECT, "devops-agent", "paused")
    paused, _ = await svc.decide_route(project_id=PROJECT, capability=PLAN_DEPLOYMENT)
    assert paused.outcome == "no_eligible_agent"

    await svc.set_membership_state(PROJECT, "devops-agent", "active")
    resumed, _ = await svc.decide_route(project_id=PROJECT, capability=PLAN_DEPLOYMENT)
    assert resumed.selected_agent_key == "devops-agent"


async def test_every_routing_decision_is_durable_evidence_with_its_candidate_set():
    svc, _, _, _ = service()
    await svc.form_team(PROJECT, GOAL)
    await svc.decide_route(project_id=PROJECT, capability=ANALYZE_REQUIREMENTS, task_id="t-1")
    history = await svc.routing_history(PROJECT)
    assert len(history) == 1
    considered = history[0]["candidates_considered"]
    assert {c["agent_key"] for c in considered} == {d.agent_key for d in AGENT_CAPABILITY_SEED}
    assert sum(1 for c in considered if c["eligible"]) == 1


# --- the SDK seam -------------------------------------------------------------------------------


def test_the_capability_seed_declares_only_agents_that_can_receive_work():
    """A declared agent with no runtime would let the router select an unreachable worker."""
    for declaration in AGENT_CAPABILITY_SEED:
        assert declaration.transport_stream, declaration.agent_key
        assert set(declaration.capabilities) <= KNOWN_CAPABILITIES, declaration.agent_key
    seeded = {d.agent_key for d in AGENT_CAPABILITY_SEED}
    assert "backend-agent" not in seeded and "frontend-agent" not in seeded


def test_team_context_round_trips_and_rejects_a_payload_without_a_project():
    context = build_team_context(project_id=PROJECT, goal_ref=GOAL, workflow_stage="dispatch")
    assert team_context_of(with_team_context({"task_id": "t"}, context))["project_id"] == PROJECT
    assert team_context_of({"task_id": "t"}) is None
    assert team_context_of({"team_context": {"project_id": ""}}) is None


def test_the_runtime_agents_declare_capabilities_rather_than_only_a_successor_stream():
    declared = {
        "agents/requirement-agent/src/agent.py": ANALYZE_REQUIREMENTS,
        "agents/development-agent/src/agent.py": GENERATE_CODE,
        "agents/qa-agent/src/agent.py": VERIFY_QUALITY,
        "agents/devops-agent/src/agent.py": PLAN_DEPLOYMENT,
    }
    for relpath, capability in declared.items():
        source = (ROOT / relpath).read_text(encoding="utf-8")
        assert "declared_capabilities = (" in source, relpath
        assert capability.upper() in source or capability in source, relpath


async def test_an_agent_with_a_team_context_publishes_where_the_router_says():
    from shared.sdk.base_agent.stream_agent import StreamAgent

    class ProbeAgent(StreamAgent):
        name = "probe-agent"
        input_stream = "stream.probe"
        output_stream = "stream.compile-time-successor"
        successor_capability = VERIFY_QUALITY

        async def handle(self, payload: dict) -> dict:
            return {}

    svc, _, bus, _ = service()
    await svc.form_team(PROJECT, GOAL)
    agent = ProbeAgent(event_bus=bus, team_service=svc)

    # No team context: the legacy transport is used, exactly as before AT-M2.
    agent._team_context = None
    await agent.publish_next({"task_id": "t-1"})
    assert bus.streams()[-1] == "stream.compile-time-successor"

    # With a team context the router decides, and it does not choose the class attribute.
    agent._team_context = build_team_context(project_id=PROJECT, goal_ref=GOAL)
    await agent.publish_next({"task_id": "t-1"})
    assert bus.streams()[-1] == "stream.qa"
    assert agent.last_routing_decision.selected_agent_key == "qa-agent"


async def test_an_agent_parks_work_it_cannot_route_instead_of_using_its_successor_constant():
    """The load-bearing negative: no eligible agent must never mean 'use the old pipeline'."""
    from shared.sdk.base_agent.stream_agent import StreamAgent

    class ProbeAgent(StreamAgent):
        name = "probe-agent"
        input_stream = "stream.probe"
        output_stream = "stream.compile-time-successor"
        successor_capability = VERIFY_QUALITY

        async def handle(self, payload: dict) -> dict:
            return {}

    svc, _, bus, _ = service()
    await svc.form_team(PROJECT, GOAL)
    await svc.set_membership_state(PROJECT, "qa-agent", "left")
    agent = ProbeAgent(event_bus=bus, team_service=svc)
    agent._team_context = build_team_context(project_id=PROJECT, goal_ref=GOAL)

    await agent.publish_next({"task_id": "t-1"})
    assert bus.streams()[-1] == team_events.STREAM_TEAM_BLOCKED
    assert "stream.compile-time-successor" not in bus.streams()


async def test_process_adopts_the_inbound_team_context_so_agents_need_no_wiring():
    from shared.sdk.base_agent.stream_agent import StreamAgent

    class EchoAgent(StreamAgent):
        name = "echo-agent"
        input_stream = "stream.echo"
        output_stream = "stream.echo.out"
        successor_capability = GENERATE_CODE

        async def handle(self, payload: dict) -> dict:
            await self.publish_next({"task_id": payload.get("task_id", "")})
            return {"summary": "echoed"}

    svc, _, bus, _ = service()
    await svc.form_team(PROJECT, GOAL)
    agent = EchoAgent(event_bus=bus, team_service=svc)
    await agent.process(
        with_team_context({"task_id": "t-9"}, build_team_context(project_id=PROJECT))
    )
    assert "stream.development" in bus.streams()


# --- invariants and safety ------------------------------------------------------------------------


def test_the_migration_stores_no_hidden_reasoning_field():
    """INV-04, checked against the schema rather than the contract prose."""
    sql = (ROOT / "migrations" / "036_at_m2_team_core.sql").read_text(encoding="utf-8")
    columns = re.findall(r"^\s{4}([a-z_]+)\s+(?:UUID|TEXT|JSONB|BOOLEAN|TIMESTAMPTZ)", sql, re.M)
    assert columns, "no columns parsed -- the INV-04 check would be vacuous"
    forbidden = (
        "chain_of_thought",
        "raw_reasoning",
        "hidden_reasoning",
        "reasoning_token",
        "token_trace",
        "scratchpad",
        "system_prompt",
        "unredacted",
        "secret",
        "credential",
        "api_key",
        "password",
    )
    leaks = [c for c in columns if any(marker in c for marker in forbidden)]
    assert leaks == [], f"AT-M2 contracted a hidden-reasoning or secret column: {leaks}"


def test_the_migration_creates_no_second_team_or_execution_lineage():
    """INV-02 / AT-D01: a team is its memberships; execution stays on Work Item -> Run."""
    sql = (ROOT / "migrations" / "036_at_m2_team_core.sql").read_text(encoding="utf-8")
    created = set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", sql))
    assert "teams" not in created and "agent_teams" not in created
    assert created == {
        "actor_principals",
        "agent_profiles",
        "project_team_memberships",
        "conversation_threads",
        "team_messages",
        "team_decisions",
        "agent_handoffs",
        "agent_routing_decisions",
    }
    assert "ALTER TABLE" not in sql.upper(), "AT-M2 must not modify an existing table"
    assert re.search(r"\bDROP\b", sql.upper()) is None, "the forward migration drops nothing"


def test_the_migration_is_reversible():
    down = (ROOT / "migrations" / "036_at_m2_team_core_down.sql").read_text(encoding="utf-8")
    sql = (ROOT / "migrations" / "036_at_m2_team_core.sql").read_text(encoding="utf-8")
    for table in re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", sql):
        assert f"DROP TABLE IF EXISTS {table}" in down, table


def test_task_roles_gained_no_runtime_agent_principal():
    """INV-01. Agents are principals; they never become authorization subjects."""
    rbac = (ROOT / "shared" / "sdk" / "tasks" / "rbac.py").read_text(encoding="utf-8")
    match = re.search(r"TASK_ROLES:\s*frozenset\[str\]\s*=\s*frozenset\(\s*\{(.*?)\}", rbac, re.S)
    assert match
    roles = set(re.findall(r'"([a-z_]+)"', match.group(1)))
    assert roles == {
        "requester",
        "pm_engineering_lead",
        "reviewer_approver",
        "platform_admin",
        "agent_operator",
        "security_compliance_reviewer",
    }
    for declaration in AGENT_CAPABILITY_SEED:
        assert declaration.agent_key not in roles


def test_the_team_decision_vocabulary_cannot_stand_in_for_an_acceptance_decision():
    """INV-03: a team that could emit a Review Gate Action would accept its own delivery."""
    sql = (ROOT / "migrations" / "036_at_m2_team_core.sql").read_text(encoding="utf-8")
    block = sql.split("CREATE TABLE IF NOT EXISTS team_decisions")[1].split("CREATE INDEX")[0]
    for gate_action in ("ACCEPTED_WITH_FOLLOW_UP", "REJECTED", "ACCEPTED"):
        assert gate_action not in block
    assert "CHECK (selected_option IN" not in block, "selected_option must stay free-form"


def test_routing_never_marks_anything_production_executed():
    """No team table can record a production act, because none of them can cause one.

    Checked against parsed COLUMN NAMES: the migration's prose is allowed to explain why the
    concept is absent, and a substring scan of the whole file would fail on the explanation.
    """
    sql = (ROOT / "migrations" / "036_at_m2_team_core.sql").read_text(encoding="utf-8")
    columns = re.findall(r"^\s{4}([a-z_]+)\s+(?:UUID|TEXT|JSONB|BOOLEAN|TIMESTAMPTZ)", sql, re.M)
    assert columns
    assert [c for c in columns if "production" in c] == []


async def test_a_handoff_transfers_ownership_only_on_acceptance():
    svc, store, _, _ = service()
    await svc.form_team(PROJECT, GOAL)
    dev = await svc.principal_for_agent(PROJECT, "development-agent")
    qa = await svc.principal_for_agent(PROJECT, "qa-agent")
    offered = await store.offer_handoff(
        {
            "project_id": PROJECT,
            "from_principal_id": dev,
            "to_principal_id": qa,
            "reason": "implementation complete, verification needed",
        }
    )
    assert offered["state"] == "offered" and offered["accepted_at"] is None
    accepted = await store.accept_handoff(offered["handoff_id"])
    assert accepted["state"] == "accepted" and accepted["accepted_at"] is not None
    assert await store.accept_handoff(offered["handoff_id"]) is None


def test_a_capability_declaration_carries_no_secret_material():
    for declaration in AGENT_CAPABILITY_SEED:
        for field in (declaration.tool_policy_profile, declaration.model_provider_ref):
            assert field is None or not re.search(r"(?i)(key|token|secret|password)=", field)


def test_declarations_are_immutable_so_a_team_cannot_be_reconfigured_by_accident():
    declaration = AGENT_CAPABILITY_SEED[0]
    with pytest.raises(Exception):
        declaration.capabilities = ()  # type: ignore[misc]
    assert isinstance(declaration, AgentCapabilityDeclaration)


# --- the AT-M1 -> AT-M2 lifecycle transition ------------------------------------------------------
#
# AT-M1's "no implementation" guard is HEAD-relative on purpose, so it would reject every
# successor milestone forever. AT-M2 closes its window at a recorded boundary. These tests exist
# because a guard that can be switched off is only safe if switching it off is hard, so the
# interesting cases are the ones where the switch must NOT engage.


def _load(path: str):
    import importlib.util

    spec = importlib.util.spec_from_file_location(f"probe_{Path(path).stem}", ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_at_m1_window_is_closed_and_names_its_boundary():
    guard = _load("scripts/verify_at_m1_architecture_reset.py")
    window, reason = guard.at_m1_rejection_window()
    assert window.endswith(guard.AT_M1_SUPERSESSION_COMMIT), reason
    assert "superseded" in reason.lower()


def test_the_boundary_sits_between_the_reviewed_stage_head_and_head():
    """It cannot be invented, and it cannot be walked back over AT-M1's own commits."""
    guard = _load("scripts/verify_at_m1_architecture_reset.py")
    assert guard.is_ancestor(guard.AT_M1_STAGE_HEAD, guard.AT_M1_SUPERSESSION_COMMIT)
    assert guard.is_ancestor(guard.AT_M1_SUPERSESSION_COMMIT, "HEAD")


def test_sliding_the_boundary_forward_requires_amending_the_authorization_decision():
    """The one real drift attack: re-pinning the boundary to hide later commits."""
    guard = _load("scripts/verify_at_m1_architecture_reset.py")
    decision = (ROOT / guard.AT_M2_AUTHORIZATION_RECORD).read_text(encoding="utf-8")
    assert guard.AT_M1_SUPERSESSION_COMMIT in decision
    source = (ROOT / "scripts" / "verify_at_m1_architecture_reset.py").read_text(encoding="utf-8")
    assert "AT_M1_SUPERSESSION_COMMIT in read(AT_M2_AUTHORIZATION_RECORD)" in source


@pytest.mark.parametrize(
    "field",
    ["AT_M1_LIFECYCLE:         SUPERSEDED BY AT-M2", "AT_M1_SUPERSESSION_COMMIT", "AT_M2: "],
)
def test_the_window_reopens_when_the_canonical_record_stops_saying_so(field, monkeypatch):
    """Fail-closed, checked by removing each precondition in turn."""
    guard = _load("scripts/verify_at_m1_architecture_reset.py")
    real_read = guard.read
    key = field.split(":")[0]

    def redacted(relpath: str) -> str:
        text = real_read(relpath)
        if relpath == guard.AT_M1_SUPERSESSION_RECORD:
            return "\n".join(line for line in text.splitlines() if key not in line)
        return text

    monkeypatch.setattr(guard, "read", redacted)
    window, reason = guard.at_m1_rejection_window()
    assert window.endswith("HEAD"), f"removing {key} did not reopen the window"
    assert "not superseded" in reason


def test_the_window_stays_open_for_a_boundary_this_repository_does_not_have(monkeypatch):
    guard = _load("scripts/verify_at_m1_architecture_reset.py")
    monkeypatch.setattr(guard, "AT_M1_SUPERSESSION_COMMIT", "0" * 40)
    window, _reason = guard.at_m1_rejection_window()
    assert window.endswith("HEAD")


def test_supersession_does_not_relax_the_task_roles_anchor():
    """INV-01 is not part of AT-M1's window and must stay HEAD-relative forever."""
    guard = _load("scripts/verify_at_m1_architecture_reset.py")
    assert guard.PERMANENTLY_PROTECTED_PATHS == (guard.RBAC_SOURCE,)
    assert guard.RBAC_SOURCE not in guard.STAGE_PROTECTED_PATHS
    source = (ROOT / "scripts" / "verify_at_m1_architecture_reset.py").read_text(encoding="utf-8")
    assert (
        "permanent_breaches(changed_paths(AT_M1_CURRENT_RANGE))" in source
    ), "the INV-01 anchor is no longer asked HEAD-relative"


def test_at_m2_authorization_requires_the_canonical_decision_record(monkeypatch):
    """PCP fail-closed: a snapshot claiming authorization is not itself authorization."""
    pcp = _load("scripts/verify_pcp_v2_control_plane.py")
    pm = pcp.registers(pcp.read(pcp.PM_STATE))
    assert pcp.at_m2_authorization_is_recorded(pm)

    real_read = pcp.read
    monkeypatch.setattr(pcp, "read", lambda p: "" if p == pcp.AT_M2_AUTHORIZATION else real_read(p))
    assert not pcp.at_m2_authorization_is_recorded(pm)
    assert "NOT AUTHORIZED" in pcp.at_m2_authorization_state({"AT_M2": "NOT AUTHORIZED"})


def test_the_at_m1_binding_contract_still_records_what_at_m1_decided():
    """Supersession must not rewrite history: AT-M1 said NOT AUTHORIZED, and still does."""
    binding = (
        ROOT / "docs" / "contracts" / "autonomous-team" / "at-binding-decisions.md"
    ).read_text(encoding="utf-8")
    assert re.search(r"AT_M2:\s*NOT AUTHORIZED", binding)


def test_the_authorization_record_grants_nothing_beyond_at_m2():
    decision = (ROOT / "docs" / "decisions" / "at-m2-authorization.md").read_text(encoding="utf-8")
    assert re.search(r"AT-M3 \.\. AT-M8\s+NOT AUTHORIZED", decision)
    assert re.search(r"Production action\s+NOT AUTHORIZED", decision)
    assert re.search(r"Production authorization\s+NOT GRANTED", decision)
    assert "does NOT mark PCP-V2.1 PASS" in decision
    assert "production_executed_true_count: 0" in decision
