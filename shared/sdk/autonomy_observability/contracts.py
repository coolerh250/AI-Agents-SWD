"""Step AT-M3.6A -- the explicit response contract for the autonomous-runtime read surface.

Every AT-M3.6A endpoint declares one of these as its ``response_model``, so the public shape is a
declared contract rather than whatever columns a SELECT happened to return. A column added to
``plan_execution_units`` tomorrow does not silently become part of this API, and a column removed
from it fails here rather than in a consumer.

FIELDS SAY WHAT KIND OF FACT THEY ARE. The distinction matters most exactly where a reader is
likeliest to get it wrong:

* ``is_current`` / ``lineage_status`` -- DERIVED from lineage, recomputed per read, never stored.
* ``autonomy_phase`` / ``progress`` / ``blockers`` / ``next_work`` -- DERIVED, non-authoritative.
* ``dispatch_state`` -- derived, and deliberately unable to say "executing".
* ``execution_mode`` -- a constant statement of what a completion in this system actually is.
* everything else -- the canonical row, passed through.

These models are permissive about extra keys being absent and strict about the ones that carry
meaning. They are additive: no existing ``/operations`` response model is changed, renamed or
removed by this slice, so an Admin Console already reading ``/operations`` sees no difference.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# --- shared leaf shapes ---------------------------------------------------------------------------


class Blocker(BaseModel):
    """One explainable reason something is not moving, tied to the entity it is about."""

    code: str = Field(description="closed-vocabulary blocker code")
    entity_type: str
    entity_id: str | None = None
    canonical_reason: str | None = Field(
        default=None,
        description="the value as stored in the canonical column; None when the blocker is the "
        "absence of a row rather than a recorded reason",
    )
    detail: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class AutonomyPhase(BaseModel):
    """A derived label plus the rule that produced it. Never persisted, never authoritative."""

    phase: str
    reason: str
    blocker_codes: list[str] = Field(default_factory=list)
    is_derived: bool = True
    authority: str


class Progress(BaseModel):
    """Counts over ONE graph, with the completion formula stated rather than implied."""

    total_units: int
    blocked: int
    ready: int
    assigned: int
    dispatched: int
    completed: int
    failed: int
    cancelled: int
    unavailable: int = Field(
        description="a SUBSET of `ready`: units nobody eligible can take. Not part of the state sum"
    )
    completion_percent: float | None
    completion_percent_formula: str
    execution_mode: str


class NextWork(BaseModel):
    """What a scheduler pass WOULD find. Reading it dispatches nothing."""

    ready_units: list[dict[str, Any]] = Field(default_factory=list)
    capability_unavailable_units: list[dict[str, Any]] = Field(default_factory=list)
    unpublished_dispatch_units: list[dict[str, Any]] = Field(default_factory=list)
    dependency_blocked_units: list[dict[str, Any]] = Field(default_factory=list)
    note: str


class DependencyEdge(BaseModel):
    """Topology in stable identifiers, so a DAG can be drawn without parsing plan prose."""

    execution_unit_id: str
    step_key: str
    dependency_type: str
    state: str | None = None
    depends_on_step_key: str | None = None


class WorkItemDetail(BaseModel):
    """The lineage carrier's detail. Its id is a top-level field on the unit, not repeated here."""

    work_item_key: str | None = None
    title: str | None = None
    status: str | None = None
    lifecycle_state: str | None = None


class Assignment(BaseModel):
    assigned_principal_id: str | None = None
    assigned_principal_name: str | None = None
    assigned_principal_type: str | None = None
    assigned_role: str | None = None
    assigned_agent_key: str | None = None
    assigned_at: datetime | None = None


class RoutingExplanation(BaseModel):
    """Why this agent. Deterministic-rule explainability, never model reasoning.

    ``candidates_considered`` is the AT-M2 evidence set: who was looked at, who was eligible and
    what each ineligible member was missing. No prompt, completion or chain of thought exists in
    ``agent_routing_decisions`` to expose, and none is invented here.
    """

    routing_decision_id: str | None = None
    requested_capability: str | None = None
    outcome: str | None = None
    reason: str | None = None
    selected_role: str | None = None
    selected_stream: str | None = None
    candidates_considered: list[dict[str, Any]] = Field(default_factory=list)
    decided_at: datetime | None = None
    preferred_role: str | None = Field(
        default=None, description="the plan's intended_owner_role, carried as a preference"
    )
    preferred_role_is_a_filter: bool = Field(
        default=False,
        description="always false: the plan's role hint never filters and never assigns",
    )


class Dispatch(BaseModel):
    """The canonical PostgreSQL dispatch row. Not proof that anything ran."""

    correlation_id: str
    target_stream: str
    published_at: datetime | None = None
    created_at: datetime | None = None
    plan_revision_id: str | None = None
    step_key: str | None = None
    assigned_principal_id: str | None = None
    work_item_id: str | None = None


class HumanApprovalBoundary(BaseModel):
    """Read-only. AT-M3.6A never requests, approves, rejects or expires an approval."""

    referred: bool
    canonical_reason: str | None = None
    approval_record: dict[str, Any] | None = None
    note: str


class ExecutionUnit(BaseModel):
    execution_unit_id: str
    plan_execution_graph_id: str
    plan_revision_id: str
    goal_id: str
    project_id: str
    step_key: str
    state: str
    required_capabilities: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    intended_owner_role: str | None = None
    unavailable_reason: str | None = None
    disposition: str | None = None
    result_ref: str | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    work_item_id: str
    work_item: WorkItemDetail
    assignment: Assignment
    routing: RoutingExplanation
    dispatch: Dispatch | None = None
    dispatch_state: str
    dispatch_truth: str
    execution_mode: str
    human_approval: HumanApprovalBoundary
    depends_on: list[DependencyEdge] = Field(default_factory=list)
    unlocks: list[DependencyEdge] = Field(default_factory=list)
    plan_revision_is_current: bool
    has_routing_decision: bool = False
    blockers: list[Blocker] = Field(default_factory=list)
    lineage: dict[str, Any] | None = None


# --- goal overview --------------------------------------------------------------------------------


class GoalRef(BaseModel):
    goal_id: str
    project_id: str
    project_title: str | None = None
    project_status: str | None = None
    statement: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    status: str
    created_by: str
    created_at: datetime | None = None


class ExecutionLineage(BaseModel):
    """The Goal's single autonomous execution root. One per Goal, by primary key."""

    primary_work_item_id: str
    primary_work_item_title: str | None = None
    primary_work_item_key: str | None = None
    primary_work_item_status: str | None = None
    primary_work_item_lifecycle_state: str | None = None
    is_cancelled: bool
    created_at: datetime | None = None


class TeamMember(BaseModel):
    principal_id: str
    display_name: str | None = None
    agent_key: str | None = None
    functional_role: str
    membership_state: str
    profile_status: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    joined_at: datetime | None = None
    left_at: datetime | None = None


class TeamSummary(BaseModel):
    project_id: str
    active_member_count: int
    members: list[TeamMember] = Field(default_factory=list)


class DiscussionParticipant(BaseModel):
    seat_index: int
    principal_id: str
    display_name: str | None = None
    agent_key: str
    functional_role: str
    matched_capabilities: list[str] = Field(default_factory=list)
    selection_reason: str
    turns_taken: int


class DiscussionTurn(BaseModel):
    """A turn and the SUMMARY of the message it produced. Never the message body."""

    round_index: int
    seat_index: int
    speaker_principal_id: str
    speaker_display_name: str | None = None
    intent: str
    reasoning_verb: str
    reasoning_invocation_id: str | None = None
    status: str
    concern_count: int
    message_id: str | None = None
    message_type: str | None = None
    message_summary: str | None = None
    created_at: datetime | None = None


class DiscussionBounds(BaseModel):
    max_rounds: int
    max_messages: int
    max_invocations: int
    max_turns_per_participant: int
    deadline_at: datetime | None = None


class DiscussionView(BaseModel):
    discussion_id: str
    goal_id: str
    project_id: str
    thread_id: str
    plan_revision_id: str | None = None
    plan_revision_is_current: bool = Field(
        description="DERIVED: whether the exact revision this discussion opened against is still "
        "the Goal's current one. The binding itself never moves."
    )
    topic: str
    opened_by: str
    required_capabilities: list[str] = Field(default_factory=list)
    state: str
    stop_reason: str | None = None
    is_terminal: bool
    current_round: int
    turns_taken: int
    messages_posted: int
    invocations_started: int
    bounds: DiscussionBounds
    deadline_expired: bool
    result_message_id: str | None = None
    result_message_summary: str | None = None
    planning_decision_id: str | None = None
    team_decision_id: str | None = None
    resulting_plan_revision_id: str | None = None
    planning_outcome: str | None = None
    created_at: datetime | None = None
    closed_at: datetime | None = None
    open_reasoning_invocations: int = 0
    participants: list[DiscussionParticipant] = Field(default_factory=list)
    turn_count: int = 0
    turns_truncated: bool = False
    turns: list[DiscussionTurn] = Field(default_factory=list)


class TeamDecisionView(BaseModel):
    team_decision_id: str
    thread_id: str | None = None
    proposed_by: str | None = None
    options_considered: list[Any] = Field(default_factory=list)
    selected_option: str | None = None
    rationale_summary: str | None = None
    dissent_summary: str | None = None
    created_at: datetime | None = None


class PlanningDecisionView(BaseModel):
    planning_decision_id: str
    goal_id: str
    discussion_id: str
    outcome: str
    result_message_id: str
    candidate_plan_message_id: str
    candidate_message_summary: str | None = None
    candidate_message_type: str | None = None
    predecessor_plan_revision_id: str | None = None
    resulting_plan_revision_id: str | None = None
    resulting_revision_status: str | None = None
    resulting_revision_number: int | None = None
    resulting_revision_is_current: bool | None = None
    team_decision: TeamDecisionView
    created_at: datetime | None = None


class PlanRevisionView(BaseModel):
    plan_revision_id: str
    goal_id: str
    project_id: str
    revision_number: int
    status: str
    reason: str
    created_by: str | None = None
    supersedes_revision_id: str | None = None
    superseded_by_revision_id: str | None = None
    trace_ref: str | None = None
    created_at: datetime | None = None
    is_current: bool = Field(description="DERIVED from lineage; there is no currency column")
    is_accepted: bool
    plan_execution_graph_id: str | None = None
    is_materialized: bool
    materialized_at: datetime | None = None
    step_count: int | None = None
    plan: dict[str, Any] | None = Field(
        default=None, description="the revision's own structured PlanContent, when requested"
    )
    execution: dict[str, Any] | None = Field(
        default=None, description="what this revision materialized and dispatched, if anything"
    )


class ExecutionGraphSummary(BaseModel):
    plan_execution_graph_id: str
    plan_revision_id: str
    revision_number: int
    step_count: int
    materialized_by: str
    materialized_at: datetime | None = None
    is_current: bool
    edge_count: int


class HistoricalGraph(BaseModel):
    """A superseded revision's graph. Preserved, labelled, and never counted as current."""

    plan_revision_id: str
    revision_number: int
    plan_execution_graph_id: str
    step_count: int
    materialized_at: datetime | None = None
    is_current: bool
    state_counts: dict[str, int] = Field(default_factory=dict)
    canonical_dispatch_rows: int
    published_dispatch_rows: int
    execution_mode: str


class ReadModelNote(BaseModel):
    source_of_truth: str
    redis_consulted: bool
    derived_fields: list[str]
    execution_mode: str
    note: str


class GoalAutonomyOverview(BaseModel):
    """The answer to "what is this autonomous team doing right now, and why"."""

    goal: GoalRef
    execution_lineage: ExecutionLineage | None = None
    team: TeamSummary
    current_discussion: DiscussionView | None = None
    discussion_count: int
    current_planning_decision: PlanningDecisionView | None = None
    planning_decision_count: int
    current_plan_revision: PlanRevisionView | None = None
    plan_revision_count: int
    current_execution_graph: ExecutionGraphSummary | None = None
    current_units: list[ExecutionUnit] = Field(default_factory=list)
    progress: Progress
    autonomy_phase: AutonomyPhase
    blockers: list[Blocker] = Field(default_factory=list)
    next_work: NextWork
    historical_execution_graphs: list[HistoricalGraph] = Field(default_factory=list)
    read_model: ReadModelNote


class PlanRevisionHistory(BaseModel):
    goal_id: str
    project_id: str
    total: int
    limit: int
    offset: int
    has_more: bool
    ordering: str
    revisions: list[PlanRevisionView] = Field(default_factory=list)


class ExecutionGraphView(BaseModel):
    plan_execution_graph_id: str
    plan_revision_id: str
    goal_id: str
    project_id: str
    primary_work_item_id: str | None = None
    revision_number: int
    revision_status: str
    revision_reason: str
    supersedes_revision_id: str | None = None
    superseded_by_revision_id: str | None = None
    is_current: bool
    lineage_status: str = Field(description="CURRENT or HISTORICAL_SUPERSEDED")
    step_count: int
    materialized_by: str
    materialized_at: datetime | None = None
    total_units: int
    limit: int
    offset: int
    has_more: bool
    ordering: str
    units: list[ExecutionUnit] = Field(default_factory=list)
    progress: Progress
    next_work: NextWork
    execution_mode: str
    dispatch_truth: str


class TimelineEntry(BaseModel):
    """One recorded audit event. Evidence, not authority."""

    audit_id: str
    occurred_at: datetime | None = None
    decision_type: str | None = None
    agent: str | None = None
    summary: str | None = None
    result: str | None = None
    goal_id: str
    plan_revision_id: str | None = None
    discussion_id: str | None = None
    execution_unit_id: str | None = None
    step_key: str | None = None
    correlation_id: str | None = None
    reference_scope_verified: bool


class GoalTimeline(BaseModel):
    goal_id: str
    project_id: str
    total: int
    limit: int
    offset: int
    has_more: bool
    ordering: str
    authority: str
    entries: list[TimelineEntry] = Field(default_factory=list)


class ReasoningInvocationView(BaseModel):
    """Operational metadata only. No prompt, completion, scratchpad or artifact body."""

    invocation_id: str
    reasoning_verb: str
    provider_name: str
    provider_mode: str
    model_name: str | None = None
    status: str
    attempt: int | None = None
    round_number: int | None = None
    failure_category: str | None = None
    failure_reason: str | None = Field(
        default=None, description="the sanitized reason AT-M3.1 stores, passed through"
    )
    artifact_type: str | None = Field(
        default=None, description="the artifact's TYPE name; the object itself is not exposed"
    )
    artifact_body_exposed: bool = False
    outcome_ref: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    latency_ms: int | None = None
    correlation_id: str | None = None
    requested_by_principal_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    turn: dict[str, Any] | None = None


class DiscussionReasoningView(BaseModel):
    discussion_id: str
    goal_id: str
    project_id: str
    thread_id: str
    plan_revision_id: str | None = None
    total: int
    limit: int
    offset: int
    has_more: bool
    ordering: str
    disclosure: str
    invocations: list[ReasoningInvocationView] = Field(default_factory=list)


__all__ = [
    "AutonomyPhase",
    "Blocker",
    "DiscussionReasoningView",
    "ExecutionGraphView",
    "ExecutionUnit",
    "GoalAutonomyOverview",
    "GoalTimeline",
    "PlanRevisionHistory",
    "Progress",
]
