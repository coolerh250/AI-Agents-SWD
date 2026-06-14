"""Stage 46 -- Pydantic models for agent discussion.

Discussion captures structured role-based review OUTPUT SUMMARIES only.
There is no chain-of-thought, no raw prompt, no transcript. Strict
validation (extra=forbid).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

SESSION_TYPES = (
    "project_design_review",
    "requirement_review",
    "architecture_review",
    "qa_strategy_review",
    "security_review",
    "delivery_readiness_review",
    "risk_review",
    "implementation_strategy_review",
)
SESSION_STATUSES = ("draft", "in_progress", "completed", "blocked", "failed", "cancelled")
REVIEW_MODES = ("deterministic_template", "llm_assisted_disabled", "human_review")
PARTICIPATION_TYPES = ("reviewer", "owner", "approver", "observer")
PARTICIPANT_STATUSES = ("pending", "completed", "skipped", "failed")
CONTRIBUTION_TYPES = (
    "requirement_question",
    "scope_assessment",
    "architecture_option",
    "implementation_plan",
    "qa_strategy",
    "security_risk",
    "delivery_risk",
    "acceptance_coverage",
    "blocker",
    "recommendation",
)
CONFIDENCE_LEVELS = ("low", "medium", "high")
SEVERITY_LEVELS = ("low", "medium", "high", "critical")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DiscussionParticipant(_Strict):
    agent_role: str
    participation_type: str = "reviewer"
    status: str = "completed"
    metadata: dict = Field(default_factory=dict)


class DiscussionContribution(_Strict):
    agent_role: str
    contribution_type: str
    summary: str
    rationale_summary: str | None = None
    confidence: str | None = "medium"
    severity: str | None = None
    related_artifact_refs: list[dict] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class DiscussionArtifact(_Strict):
    artifact_type: str
    title: str = ""
    content: dict | None = None
    uri: str | None = None
    created_by_agent: str = "design-review-agent"
    metadata: dict = Field(default_factory=dict)


class DiscussionSession(_Strict):
    session_type: str = "project_design_review"
    status: str = "draft"
    review_mode: str = "deterministic_template"
    planning_only: bool = True
    project_id: str | None = None
    work_item_id: str | None = None
    source_task_id: str | None = None
    created_by_agent: str = "design-review-agent"
    metadata: dict = Field(default_factory=dict)


class DiscussionOutput(_Strict):
    session_id: str
    project_id: str | None = None
    participants_count: int = 0
    contributions_count: int = 0
    status: str = "completed"
    planning_only: bool = True
    production_executed: bool = False


__all__ = [
    "DiscussionSession",
    "DiscussionParticipant",
    "DiscussionContribution",
    "DiscussionArtifact",
    "DiscussionOutput",
    "SESSION_TYPES",
    "SESSION_STATUSES",
    "REVIEW_MODES",
    "PARTICIPATION_TYPES",
    "PARTICIPANT_STATUSES",
    "CONTRIBUTION_TYPES",
    "CONFIDENCE_LEVELS",
    "SEVERITY_LEVELS",
]
