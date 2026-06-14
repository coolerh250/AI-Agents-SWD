"""Stage 46 -- Pydantic models for design review.

Strict validation. No chain-of-thought, no raw prompts -- only findings,
decisions, gates, and summaries.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

REVIEW_TYPES = (
    "project_design",
    "architecture",
    "implementation",
    "qa_strategy",
    "security",
    "delivery",
    "full_pre_execution",
)
REVIEW_STATUSES = ("pending", "passed", "passed_with_findings", "blocked", "failed")
REVIEW_DECISIONS = ("go", "go_with_findings", "no_go", "needs_clarification", "planning_only")
FINDING_TYPES = (
    "requirement_gap",
    "architecture_risk",
    "implementation_risk",
    "qa_gap",
    "security_risk",
    "delivery_risk",
    "dependency_issue",
    "acceptance_gap",
    "scope_risk",
)
SEVERITIES = ("low", "medium", "high", "critical")
FINDING_STATUSES = ("open", "accepted", "mitigated", "waived", "closed")
DECISION_TYPES = (
    "architecture_decision",
    "implementation_decision",
    "qa_decision",
    "security_decision",
    "delivery_decision",
    "clarification_decision",
    "go_no_go_decision",
)
APPROVAL_STATUSES = ("not_required", "pending", "approved", "rejected")
GATE_TYPES = (
    "requirement_gate",
    "architecture_gate",
    "implementation_strategy_gate",
    "qa_strategy_gate",
    "security_gate",
    "delivery_gate",
    "pre_execution_gate",
)
GATE_STATUSES = ("pending", "passed", "passed_with_findings", "blocked", "failed", "waived")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReviewContext(_Strict):
    """All project-planning data a reviewer needs, loaded from the store."""

    project_id: str
    template: str = "generic_software_project"
    brief: dict = Field(default_factory=dict)
    user_stories: list[dict] = Field(default_factory=list)
    work_items: list[dict] = Field(default_factory=list)
    dependencies: list[dict] = Field(default_factory=list)
    acceptance_criteria: list[dict] = Field(default_factory=list)
    risks: list[dict] = Field(default_factory=list)
    graph_validation_status: str = "valid"
    graph_snapshot_id: str | None = None


class DesignReviewFinding(_Strict):
    finding_key: str
    finding_type: str
    severity: str = "low"
    title: str
    description: str
    recommendation: str | None = None
    status: str = "open"
    work_item_key: str | None = None
    created_by_agent: str = "design-review-agent"
    metadata: dict = Field(default_factory=dict)


class DesignReviewDecision(_Strict):
    decision_type: str
    decision: str
    rationale_summary: str | None = None
    decided_by: str = "design-review-agent"
    approval_required: bool = False
    approval_status: str = "not_required"
    metadata: dict = Field(default_factory=dict)


class ProjectReviewGate(_Strict):
    gate_type: str
    status: str = "pending"
    required: bool = True
    blocking: bool = True
    metadata: dict = Field(default_factory=dict)


class DesignReviewSession(_Strict):
    project_id: str
    review_type: str = "full_pre_execution"
    status: str = "pending"
    decision: str = "planning_only"
    graph_snapshot_id: str | None = None
    discussion_session_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class GoNoGoSummary(_Strict):
    decision: str = "planning_only"
    blocking_findings_count: int = 0
    total_findings_count: int = 0
    gates_passed: int = 0
    gates_total: int = 0
    next_suggested_stage: str = "real_repo_workspace_operator"
    planning_only: bool = True
    production_executed: bool = False


class DesignReviewOutput(_Strict):
    project_id: str
    discussion_session_id: str | None = None
    review_session_id: str | None = None
    review_type: str = "full_pre_execution"
    status: str = "pending"
    decision: str = "planning_only"
    participants_count: int = 0
    contributions_count: int = 0
    gates_count: int = 0
    findings_count: int = 0
    blocking_findings_count: int = 0
    decisions_count: int = 0
    go_no_go_decision: str = "planning_only"
    planning_only: bool = True
    work_item_dispatch_enabled: bool = False
    production_executed: bool = False
    metadata: dict = Field(default_factory=dict)


__all__ = [
    "ReviewContext",
    "DesignReviewSession",
    "DesignReviewFinding",
    "DesignReviewDecision",
    "ProjectReviewGate",
    "DesignReviewOutput",
    "GoNoGoSummary",
    "REVIEW_TYPES",
    "REVIEW_STATUSES",
    "REVIEW_DECISIONS",
    "FINDING_TYPES",
    "SEVERITIES",
    "FINDING_STATUSES",
    "DECISION_TYPES",
    "APPROVAL_STATUSES",
    "GATE_TYPES",
    "GATE_STATUSES",
]
