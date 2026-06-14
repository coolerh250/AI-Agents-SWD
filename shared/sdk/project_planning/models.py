"""Stage 45 -- Pydantic models for the project planner & task graph.

These models are deterministic, validation-strict, and carry no
chain-of-thought. Graph nodes (work items) reference each other by
``work_item_key`` during the build phase; the store resolves those keys
to UUIDs at persist time. Nothing here calls an LLM, GitHub, or any
external service.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

PROJECT_STATUSES = (
    "draft",
    "planning",
    "planned",
    "in_progress",
    "blocked",
    "qa",
    "delivery_ready",
    "accepted",
    "cancelled",
    "failed",
)
AUTONOMY_LEVELS = ("advisory", "assisted", "autonomous_dev_test", "production_gated")
RISK_LEVELS = ("low", "medium", "high", "production")
WORK_TYPES = (
    "requirement",
    "architecture",
    "backend",
    "frontend",
    "database",
    "integration",
    "qa",
    "security",
    "devops",
    "documentation",
    "release",
)
WORK_ITEM_STATUSES = (
    "pending",
    "ready",
    "in_progress",
    "blocked",
    "review",
    "completed",
    "failed",
    "cancelled",
)
WORK_ITEM_PRIORITIES = ("low", "medium", "high", "critical")
DISPATCH_POLICIES = ("planning_only", "auto_dev_test_allowed", "approval_required")
DEPENDENCY_TYPES = ("blocks", "informs", "requires_output", "review_after")
VERIFICATION_METHODS = (
    "unit_test",
    "integration_test",
    "e2e_test",
    "manual_review",
    "static_check",
    "documentation_review",
)
ACCEPTANCE_STATUSES = ("pending", "satisfied", "failed", "waived")
MILESTONE_STATUSES = ("pending", "in_progress", "completed", "blocked", "cancelled")
RISK_SEVERITIES = ("low", "medium", "high", "critical")
RISK_LIKELIHOODS = ("low", "medium", "high")
RISK_STATUSES = ("open", "mitigated", "accepted", "closed")
GRAPH_VALIDATION_STATUSES = ("valid", "invalid", "warning")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectCreate(_Strict):
    title: str
    summary: str = ""
    source_task_id: str | None = None
    request_source: str = "operator"
    requester: str | None = None
    project_type: str | None = None
    status: str = "draft"
    autonomy_level: str = "autonomous_dev_test"
    risk_level: str = "low"
    metadata: dict = Field(default_factory=dict)


class ProjectBrief(_Strict):
    problem_statement: str = ""
    goal: str = ""
    scope: list[str] = Field(default_factory=list)
    non_scope: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    stakeholders: list[str] = Field(default_factory=list)
    success_metrics: list[str] = Field(default_factory=list)
    requires_clarification: bool = False
    version: int = 1
    created_by_agent: str = "project-planner-agent"
    metadata: dict = Field(default_factory=dict)


class UserStory(_Strict):
    story_key: str
    actor: str
    need: str
    benefit: str = ""
    priority: str = "medium"
    status: str = "draft"
    metadata: dict = Field(default_factory=dict)


class AcceptanceCriterion(_Strict):
    criterion_key: str
    description: str
    verification_method: str = "manual_review"
    status: str = "pending"
    required: bool = True
    work_item_key: str | None = None
    metadata: dict = Field(default_factory=dict)


class ProjectMilestone(_Strict):
    milestone_key: str
    title: str
    description: str = ""
    order_index: int = 0
    status: str = "pending"
    metadata: dict = Field(default_factory=dict)


class ProjectWorkItem(_Strict):
    work_item_key: str
    title: str
    description: str = ""
    work_type: str | None = None
    assigned_agent_role: str | None = None
    status: str = "pending"
    priority: str = "medium"
    estimated_effort: str | None = None
    risk_level: str = "low"
    dispatch_policy: str = "planning_only"
    milestone_key: str | None = None
    parent_work_item_key: str | None = None
    metadata: dict = Field(default_factory=dict)


class WorkItemDependency(_Strict):
    work_item_key: str
    depends_on_work_item_key: str
    dependency_type: str = "blocks"
    metadata: dict = Field(default_factory=dict)


class ProjectRisk(_Strict):
    risk_key: str
    title: str
    description: str = ""
    severity: str = "medium"
    likelihood: str = "medium"
    mitigation: str = ""
    owner_agent_role: str | None = None
    status: str = "open"
    metadata: dict = Field(default_factory=dict)


class ProjectArtifact(_Strict):
    artifact_type: str
    title: str
    content: dict | None = None
    uri: str | None = None
    work_item_key: str | None = None
    created_by_agent: str = "project-planner-agent"
    metadata: dict = Field(default_factory=dict)


class ProjectGraphSnapshot(_Strict):
    version: int = 1
    graph_hash: str = ""
    nodes: list[dict] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)
    validation_status: str = "valid"
    validation_errors: list[dict] = Field(default_factory=list)
    created_by_agent: str = "project-planner-agent"
    metadata: dict = Field(default_factory=dict)


class PlannerInput(_Strict):
    task_id: str | None = None
    request_text: str
    requirement_summary: str | None = None
    source: str = "operator"
    requester: str | None = None
    project_type: str | None = None
    autonomy_level: str = "autonomous_dev_test"
    dispatch_policy: str = "planning_only"
    metadata: dict = Field(default_factory=dict)


class TaskGraph(_Strict):
    """The deterministic, pre-persistence build output."""

    project_type: str
    template: str
    milestones: list[ProjectMilestone] = Field(default_factory=list)
    work_items: list[ProjectWorkItem] = Field(default_factory=list)
    dependencies: list[WorkItemDependency] = Field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    risks: list[ProjectRisk] = Field(default_factory=list)


class PlannerOutput(_Strict):
    project_id: str
    brief_id: str | None = None
    graph_snapshot_id: str | None = None
    work_items_count: int = 0
    dependencies_count: int = 0
    acceptance_criteria_count: int = 0
    risks_count: int = 0
    milestones_count: int = 0
    user_stories_count: int = 0
    validation_status: str = "valid"
    requires_clarification: bool = False
    planning_only: bool = True
    production_executed: bool = False
    status: str = "planned"
    template: str = ""
    metadata: dict = Field(default_factory=dict)


__all__ = [
    "ProjectCreate",
    "ProjectBrief",
    "UserStory",
    "AcceptanceCriterion",
    "ProjectMilestone",
    "ProjectWorkItem",
    "WorkItemDependency",
    "ProjectRisk",
    "ProjectArtifact",
    "ProjectGraphSnapshot",
    "PlannerInput",
    "TaskGraph",
    "PlannerOutput",
    "PROJECT_STATUSES",
    "AUTONOMY_LEVELS",
    "RISK_LEVELS",
    "WORK_TYPES",
    "WORK_ITEM_STATUSES",
    "WORK_ITEM_PRIORITIES",
    "DISPATCH_POLICIES",
    "DEPENDENCY_TYPES",
    "VERIFICATION_METHODS",
    "ACCEPTANCE_STATUSES",
    "MILESTONE_STATUSES",
    "RISK_SEVERITIES",
    "RISK_LIKELIHOODS",
    "RISK_STATUSES",
    "GRAPH_VALIDATION_STATUSES",
]
