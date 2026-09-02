"""Step AT-M3.6A -- scenario builders for the observability read surface, against real PostgreSQL.

Every scenario below is built with the REAL upstream machinery: a real project, a real AT-M2 team
formed from the capability seed, a real AT-M3.3 discussion driven to a genuine convergence by a
deterministic provider, a real AT-M3.4 planning decision, real AT-M3.2 revisions taken through the
draft -> accepted transition, and a real AT-M3.5 materialization, assignment, dispatch and internal
completion.

Nothing here fakes the state the read surface reports. A read model that says "this step is blocked
by that step" is only worth testing against rows a real dependency DAG produced, and "a superseded
revision's graph is never presented as current" is a statement about what PostgreSQL contains, not
about what a dict literal contains.

The one deliberate double is the audit sink. The production path is
service -> AuditClient -> Redis -> audit-worker -> audit_logs, and the timeline reads the last hop.
``DirectAuditClient`` writes the SAME normalized row the worker would insert, straight through
``AuditStore``, so the timeline is exercised against genuine audit_logs rows without needing a
broker and a worker process in a read-model test.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from shared.sdk.agent_deliberation.service import DiscussionService
from shared.sdk.agent_planning.store import PlanningStore
from shared.sdk.agent_planning_decision.service import PlanningDecisionService
from shared.sdk.agent_reasoning.models import (
    CritiqueArtifact,
    DecisionSummaryArtifact,
    ProposalArtifact,
)
from shared.sdk.agent_team.service import TeamService
from shared.sdk.audit.store import AuditStore
from shared.sdk.autonomy_observability.store import AutonomyReadStore
from shared.sdk.plan_delegation.service import PlanDelegationService
from shared.sdk.plan_delegation.store import PlanDelegationStore

from tests.plan_delegation_fixtures import (
    CHAIN_PLAN,
    DEFAULT_TEAM,
    UNSERVED_PLAN,
    RecordingBus,
)

#: The capabilities the seeded team covers, so a discussion seats three distinct principals.
DISCUSSION_CAPS = ("plan_project", "verify_quality", "review_design")

DISCUSSION_PLAN: dict[str, Any] = {
    "objective": "deliver the reporting slice",
    "steps": [{"step_key": "s1", "title": "define the contract", "depends_on": []}],
    "constraints": [],
    "acceptance_criteria": ["a reviewer can read one report"],
}


#: Two steps, one dependency. Small enough that a single failure stalls the whole graph, which is
#: the state a read model is most likely to describe as still in flight.
TWO_STEP_PLAN: dict[str, Any] = {
    "objective": "one step, then the step that needs it",
    "acceptance_criteria": ["the second step consumes the first"],
    "steps": [
        {
            "step_key": "design",
            "title": "Design the slice",
            "required_capabilities": ["review_design"],
            "expected_outputs": ["a design note"],
        },
        {
            "step_key": "build",
            "title": "Build the slice",
            "required_capabilities": ["generate_code"],
            "expected_outputs": ["the slice"],
            "depends_on": ["design"],
        },
    ],
}


class ConvergingProvider:
    """Deterministic and concern-free, so a discussion genuinely converges.

    The shipped mock provider always raises ``mock_provider_no_live_model`` as a standing concern,
    so a mock-mode discussion honestly never converges -- which is correct behaviour and useless
    for building a converged fixture. This provider is injected explicitly and is never a
    substitute for a refused one.
    """

    name = "test-converging"
    mode = "mock"

    def propose(self, request) -> ProposalArtifact:
        return ProposalArtifact(
            summary="start from the report contract",
            rationale_summary="it is the only part the acceptance criteria name",
            recommendation="define the contract first",
        )

    def critique(self, request) -> CritiqueArtifact:
        return CritiqueArtifact(
            summary="the proposal covers the acceptance criteria",
            rationale_summary="checked against the goal",
            concerns=(),
            questions=(),
            recommendation="proceed",
        )

    def summarize_decision(self, request) -> DecisionSummaryArtifact:
        return DecisionSummaryArtifact(
            summary="the team is aligned on starting from the report contract",
            rationale_summary="no concern remained outstanding",
            options_considered=tuple(request.context.get("options_considered") or ("proceed",)),
            selected_option="define the contract first",
        )


class ContestingProvider(ConvergingProvider):
    """Always raises a concern, so the discussion runs to its bound and never converges."""

    name = "test-contesting"

    def critique(self, request) -> CritiqueArtifact:
        return CritiqueArtifact(
            summary="the proposal leaves the rollback path open",
            rationale_summary="checked against the goal's constraints",
            concerns=("rollback path undefined",),
            questions=(),
            recommendation="revise",
        )


class DirectAuditClient:
    """Writes the normalized audit row the audit-worker would write, without the broker.

    Same shape, same table, same columns. What it skips is the transport, which the timeline read
    does not touch: the timeline reads ``audit_logs``, and this puts genuine rows there.
    """

    def __init__(self) -> None:
        self.store = AuditStore()
        self.events: list[dict[str, Any]] = []

    def build_audit_event(self, **kwargs: Any) -> dict[str, Any]:
        return dict(kwargs)

    async def write_audit_event(self, event: dict[str, Any]) -> str | None:
        self.events.append(event)
        row = await self.store.write_audit_log(
            {
                "task_id": event.get("task_id"),
                "agent": event.get("agent"),
                "decision_type": event.get("decision_type"),
                "summary": event.get("summary"),
                "result": event.get("result"),
                "artifact_refs": {
                    **(event.get("artifact_refs") or {}),
                    # A unique dedup key per row, matching what the worker derives from the Redis
                    # message id. Without it the store's in-process dedup cache would swallow the
                    # second write of an identically-shaped event.
                    "source_message_id": uuid.uuid4().hex,
                },
            }
        )
        return row["audit_id"] if row else None


async def read_store_or_skip() -> AutonomyReadStore:
    """Skip rather than fail on a workstation with no database or no migration 042."""
    store = AutonomyReadStore()
    try:
        conn = await __import__("asyncpg").connect(dsn=store.dsn, timeout=5)
    except Exception:
        pytest.skip("no reachable PostgreSQL; skipping AT-M3.6A read-model test")
    try:
        for table in (
            "goal_execution_lineage",
            "plan_execution_graphs",
            "plan_execution_units",
            "plan_execution_dispatches",
            "planning_decisions",
            "discussion_sessions",
            "audit_logs",
        ):
            if await conn.fetchval(f"SELECT to_regclass('public.{table}')") is None:
                pytest.skip(f"{table} missing; skipping AT-M3.6A read-model test")
    finally:
        await conn.close()
    return store


async def _project_and_author(prefix: str) -> tuple[str, str]:
    store = PlanDelegationStore()
    conn = await store._connect()
    try:
        project_id = str(
            await conn.fetchval(
                "INSERT INTO projects (title) VALUES ($1) RETURNING id",
                f"{prefix}-{uuid.uuid4().hex[:8]}",
            )
        )
        author = str(
            await conn.fetchval(
                "INSERT INTO actor_principals (principal_type,display_name) "
                "VALUES ('human',$1) RETURNING principal_id",
                f"{prefix}-author-{uuid.uuid4().hex[:6]}",
            )
        )
    finally:
        await conn.close()
    return project_id, author


async def goal_only(*, agent_keys: tuple[str, ...] = DEFAULT_TEAM) -> dict[str, Any]:
    """Scenario K -- a Goal with a team and nothing else. No discussion, no plan, no graph."""
    await read_store_or_skip()
    project_id, author = await _project_and_author("m36a")
    if agent_keys:
        await TeamService().form_team(project_id, goal_ref="m36a", agent_keys=agent_keys)
    goal = await PlanningStore().create_goal(
        {
            "project_id": project_id,
            "statement": "deliver a reporting slice a reviewer can read",
            "acceptance_criteria": ["a reviewer can read one report"],
            "constraints": ["non-production only"],
            "created_by": author,
        }
    )
    return {
        "project_id": project_id,
        "author": author,
        "goal_id": str(goal["goal_id"]),
        "planning": PlanningStore(),
        "audit": None,
    }


async def with_discussion(
    *, provider: Any | None = None, converge: bool = True, audit: Any | None = None
) -> dict[str, Any]:
    """Scenario A -- a Goal whose team has deliberated, with no plan yet.

    ``converge=False`` produces the exhausted-discussion case: a real discussion that ran to its
    bound with a concern still open, which is the honest "the team did not agree" state.
    """
    case = await goal_only()
    case["audit"] = audit
    service = DiscussionService(
        provider=provider or (ConvergingProvider() if converge else ContestingProvider()),
        audit_client=audit,
    )
    session = await service.start_discussion(
        project_id=case["project_id"],
        goal_id=case["goal_id"],
        topic="what is the smallest slice that satisfies the goal?",
        opened_by=case["author"],
        required_capabilities=DISCUSSION_CAPS,
    )
    final = await service.run(str(session["discussion_id"]))
    case["discussion_id"] = str(session["discussion_id"])
    case["thread_id"] = str(session["thread_id"])
    case["discussion_state"] = final["session"]["state"]
    return case


async def with_accepted_plan(*, audit: Any | None = None) -> dict[str, Any]:
    """Scenario B -- a converged discussion formalized into a TeamDecision and an accepted plan.

    Uses the real AT-M3.4 command, which takes two identifiers and derives everything else: the
    accepted plan is the planner's own durable candidate, not something this fixture chose.
    """
    case = await with_discussion(audit=audit)
    result = await PlanningDecisionService(audit_client=audit).finalize(
        goal_id=case["goal_id"], discussion_id=case["discussion_id"]
    )
    case["planning_decision_id"] = str(result["planning_decision"]["planning_decision_id"])
    case["team_decision_id"] = str(result["planning_decision"]["team_decision_id"])
    case["plan_revision_id"] = str(result["plan_revision"]["plan_revision_id"])
    return case


async def with_executable_plan(
    *,
    plan: dict[str, Any] | None = None,
    audit: Any | None = None,
) -> dict[str, Any]:
    """A full deliberated lineage PLUS an accepted successor carrying a controlled plan.

    The planner's own plan is a single step, which is right for AT-M3.4 and useless for exercising
    a dependency DAG. So the deliberated revision stays in the lineage as revision 1 -- historical,
    visible, never rewritten -- and revision 2 carries the three-step capability chain the seeded
    team can actually cover. That is a real replan, produced by the real successor path with its
    compare-and-swap, not a hand-written row.
    """
    case = await with_accepted_plan(audit=audit)
    planning = PlanningStore()
    successor = await planning.create_successor_revision(
        {
            "goal_id": case["goal_id"],
            "expected_current_revision_id": case["plan_revision_id"],
            "created_by": case["author"],
            "reason": "team_decision",
            "plan": plan if plan is not None else CHAIN_PLAN,
        }
    )
    await planning.accept_revision(successor["plan_revision_id"])
    case["predecessor_plan_revision_id"] = case["plan_revision_id"]
    case["plan_revision_id"] = str(successor["plan_revision_id"])
    return case


def delegation_service(audit: Any | None = None) -> tuple[PlanDelegationService, RecordingBus]:
    """The real delegation runtime with an in-process bus, so no broker is required."""
    bus = RecordingBus()
    return PlanDelegationService(event_bus=bus, audit_client=audit), bus


async def materialized(
    *, plan: dict[str, Any] | None = None, audit: Any | None = None
) -> dict[str, Any]:
    """Scenario C/D/G -- the accepted plan turned into a real durable execution graph."""
    case = await with_executable_plan(plan=plan, audit=audit)
    service, bus = delegation_service(audit)
    await service.materialize_accepted_plan(
        goal_id=case["goal_id"],
        plan_revision_id=case["plan_revision_id"],
        materialized_by=case["author"],
    )
    case["delegation"] = service
    case["bus"] = bus
    return case


async def scheduled(
    *, plan: dict[str, Any] | None = None, audit: Any | None = None
) -> dict[str, Any]:
    """Scenario E -- one real scheduling pass: assignment, canonical dispatch, transport publish."""
    case = await materialized(plan=plan, audit=audit)
    await case["delegation"].schedule_ready_work(plan_revision_id=case["plan_revision_id"])
    return case


async def units_by_step(case: dict[str, Any], plan_revision_id: str | None = None) -> dict[str, Any]:
    graph = await PlanDelegationStore().get_graph(plan_revision_id or case["plan_revision_id"])
    return {unit["step_key"]: unit for unit in graph["units"]}


async def complete_step(case: dict[str, Any], step_key: str, disposition: str = "succeeded") -> None:
    """Finish a dispatched step through the INTERNAL seam -- there is no public completion route.

    The operation takes no principal and no correlation id: every attributed identity is read from
    the unit's own canonical dispatch row, which is the AT-M3.5 remediation that made impersonation
    unrepresentable rather than merely detected.
    """
    units = await units_by_step(case)
    await case["delegation"].record_internal_result(
        execution_unit_id=str(units[step_key]["execution_unit_id"]),
        disposition=disposition,
        evidence_ref=f"internal-simulation:{step_key}",
    )


async def supersede_with(
    case: dict[str, Any], *, plan: dict[str, Any] | None = None
) -> str:
    """Scenario H -- append an accepted successor, making the current revision historical."""
    planning = PlanningStore()
    successor = await planning.create_successor_revision(
        {
            "goal_id": case["goal_id"],
            "expected_current_revision_id": case["plan_revision_id"],
            "created_by": case["author"],
            "reason": "scope_correction",
            "plan": plan if plan is not None else CHAIN_PLAN,
        }
    )
    await planning.accept_revision(successor["plan_revision_id"])
    case["historical_plan_revision_id"] = case["plan_revision_id"]
    case["plan_revision_id"] = str(successor["plan_revision_id"])
    return str(successor["plan_revision_id"])


async def cancel_lineage(case: dict[str, Any]) -> None:
    """Scenario I -- cancel through the EXISTING work-item status, not a second cancel model."""
    conn = await PlanDelegationStore()._connect()
    try:
        await conn.execute(
            """
            UPDATE project_work_items SET status='cancelled', lifecycle_state='cancelled'
            WHERE id = (SELECT primary_work_item_id FROM goal_execution_lineage WHERE goal_id=$1)
            """,
            uuid.UUID(case["goal_id"]),
        )
    finally:
        await conn.close()


async def table_counts(tables: tuple[str, ...]) -> dict[str, int]:
    """Row counts for the read-only proof. Canonical tables only -- no derived table exists."""
    conn = await PlanDelegationStore()._connect()
    try:
        return {t: int(await conn.fetchval(f"SELECT count(*) FROM {t}")) for t in tables}
    finally:
        await conn.close()


#: Every canonical table an AT-M3.6A read touches, plus the ones a careless read could write.
CANONICAL_TABLES: tuple[str, ...] = (
    "reasoning_invocations",
    "team_messages",
    "team_decisions",
    "plan_revisions",
    "planning_decisions",
    "goal_execution_lineage",
    "plan_execution_graphs",
    "plan_execution_units",
    "plan_execution_dispatches",
    "agent_routing_decisions",
    "work_item_events",
    "audit_logs",
    "discussion_sessions",
    "discussion_turns",
    "discussion_participants",
    "project_work_items",
    "project_work_item_dependencies",
    "conversation_threads",
    "project_team_memberships",
    "production_action_approvals",
)

__all__ = [
    "CANONICAL_TABLES",
    "CHAIN_PLAN",
    "DISCUSSION_CAPS",
    "TWO_STEP_PLAN",
    "UNSERVED_PLAN",
    "ContestingProvider",
    "ConvergingProvider",
    "DirectAuditClient",
    "cancel_lineage",
    "complete_step",
    "delegation_service",
    "goal_only",
    "materialized",
    "read_store_or_skip",
    "scheduled",
    "supersede_with",
    "table_counts",
    "units_by_step",
    "with_accepted_plan",
    "with_discussion",
    "with_executable_plan",
]
