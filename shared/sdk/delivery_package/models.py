"""Stage 49 -- Pydantic models for the Delivery Package & Acceptance Gate.

Strict validation. No chain-of-thought, no raw prompts, no raw code dump --
only summaries, evidence refs, checklists, and counts. Controlled-only: every
real-write flag defaults false and ``production_executed`` is always false.
The acceptance gate NEVER auto-marks human acceptance -- human_acceptance_status
defaults ``pending``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

PACKAGE_TYPES = (
    "mini_project_delivery",
    "controlled_workspace_delivery",
    "formal_handoff",
)
PACKAGE_STATUSES = (
    "draft",
    "building",
    "ready_for_review",
    "accepted",
    "rejected",
    "blocked",
    "failed",
    "archived",
)
HUMAN_ACCEPTANCE_STATUSES = ("pending", "accepted", "rejected", "not_required")
SECTION_STATUSES = ("draft", "ready", "missing", "failed")
GATE_TYPES = (
    "mini_delivery_acceptance",
    "formal_delivery_acceptance",
    "operator_review_gate",
)
GATE_STATUSES = ("pending", "running", "passed", "passed_with_findings", "blocked", "failed")
GATE_DECISIONS = (
    "ready_for_operator_review",
    "accepted",
    "rejected",
    "blocked",
    "needs_changes",
    "controlled_only_complete",
)
HUMAN_REVIEW_STATUSES = ("pending", "accepted", "rejected", "not_required")
CHECK_TYPES = (
    "project",
    "design_review",
    "workspace",
    "testing",
    "acceptance",
    "qa",
    "safety",
    "documentation",
    "governance",
    "human_review",
)
CHECK_STATUSES = ("passed", "failed", "warning", "skipped", "pending")
CHECK_SEVERITIES = ("info", "low", "medium", "high", "critical")
OPERATOR_REVIEW_STATUSES = ("pending", "accepted", "rejected", "changes_requested")
SUMMARY_TYPES = ("business_summary", "technical_summary", "operator_summary")
READINESS_STATUSES = (
    "not_ready",
    "ready_for_operator_review",
    "accepted",
    "blocked",
    "failed",
)

# The 14 required delivery package sections (order matters for order_index).
REQUIRED_SECTION_KEYS = (
    "executive_summary",
    "scope_and_non_scope",
    "project_plan",
    "design_review_summary",
    "implementation_summary",
    "generated_files_manifest",
    "test_results",
    "qa_summary",
    "safety_summary",
    "acceptance_checklist",
    "known_limitations",
    "run_instructions",
    "handoff_notes",
    "next_steps",
)

DEFAULT_AGENT = "delivery-package-agent"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DeliveryPackage(_Strict):
    package_key: str
    package_type: str = "mini_project_delivery"
    status: str = "draft"
    project_id: str | None = None
    pilot_id: str | None = None
    workspace_id: str | None = None
    design_review_session_id: str | None = None
    controlled_only: bool = True
    human_acceptance_required: bool = True
    human_acceptance_status: str = "pending"
    real_llm_enabled: bool = False
    github_write_enabled: bool = False
    pr_creation_enabled: bool = False
    deployment_enabled: bool = False
    external_delivery_enabled: bool = False
    production_executed: bool = False
    created_by_agent: str = DEFAULT_AGENT
    metadata: dict = Field(default_factory=dict)


class DeliveryPackageSection(_Strict):
    section_key: str
    title: str
    content: dict = Field(default_factory=dict)
    content_summary: str | None = None
    order_index: int = 0
    status: str = "draft"
    metadata: dict = Field(default_factory=dict)


class DeliveryPackageArtifact(_Strict):
    artifact_type: str
    source_table: str | None = None
    source_id: str | None = None
    title: str | None = None
    uri: str | None = None
    content: dict | None = None
    metadata: dict = Field(default_factory=dict)


class AcceptanceGateCheckResult(_Strict):
    check_key: str
    check_type: str
    status: str = "pending"
    severity: str = "info"
    blocking: bool = False
    evidence_ref: dict = Field(default_factory=dict)
    summary: str | None = None
    metadata: dict = Field(default_factory=dict)


class AcceptanceGateRun(_Strict):
    gate_key: str
    gate_type: str = "mini_delivery_acceptance"
    status: str = "pending"
    decision: str = "ready_for_operator_review"
    human_review_required: bool = True
    human_review_status: str = "pending"
    blocking_findings_count: int = 0
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    warning_checks: int = 0
    checks: list[AcceptanceGateCheckResult] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class OperatorAcceptanceReview(_Strict):
    reviewer: str | None = None
    review_status: str = "pending"
    review_summary: str | None = None
    requested_changes: list = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class HandoffSummary(_Strict):
    summary_type: str
    title: str | None = None
    summary: str
    highlights: list = Field(default_factory=list)
    limitations: list = Field(default_factory=list)
    next_steps: list = Field(default_factory=list)
    artifact_refs: list = Field(default_factory=list)
    created_by_agent: str = DEFAULT_AGENT
    metadata: dict = Field(default_factory=dict)


class DeliveryReadinessSnapshot(_Strict):
    readiness_status: str = "not_ready"
    project_ready: bool = False
    design_ready: bool = False
    workspace_ready: bool = False
    qa_ready: bool = False
    acceptance_ready: bool = False
    safety_ready: bool = False
    docs_ready: bool = False
    human_acceptance_pending: bool = True
    blocking_reasons: list = Field(default_factory=list)
    warnings: list = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class DeliveryPackageRequest(_Strict):
    pilot_id: str
    project_id: str | None = None
    package_type: str = "mini_project_delivery"
    controlled_only: bool = True
    requested_by_agent: str = DEFAULT_AGENT
    source_task_id: str | None = None


class DeliveryPackageResult(_Strict):
    package_id: str | None = None
    package_key: str | None = None
    package_type: str = "mini_project_delivery"
    project_id: str | None = None
    pilot_id: str | None = None
    workspace_id: str | None = None
    design_review_session_id: str | None = None
    acceptance_gate_run_id: str | None = None
    readiness_snapshot_id: str | None = None
    operator_review_id: str | None = None
    handoff_summary_ids: list = Field(default_factory=list)
    package_status: str = "failed"
    acceptance_gate_status: str | None = None
    acceptance_gate_decision: str | None = None
    human_acceptance_status: str = "pending"
    readiness_status: str | None = None
    sections_ready_count: int = 0
    sections_missing_count: int = 0
    blocking_findings_count: int = 0
    blocked_reason: str | None = None
    controlled_only: bool = True
    production_executed: bool = False
    github_write_performed: bool = False
    pr_created: bool = False
    deployment_performed: bool = False
    real_llm_used: bool = False
    external_delivery_performed: bool = False
    metadata: dict = Field(default_factory=dict)


__all__ = [
    "DeliveryPackage",
    "DeliveryPackageSection",
    "DeliveryPackageArtifact",
    "AcceptanceGateRun",
    "AcceptanceGateCheckResult",
    "OperatorAcceptanceReview",
    "HandoffSummary",
    "DeliveryReadinessSnapshot",
    "DeliveryPackageRequest",
    "DeliveryPackageResult",
    "PACKAGE_TYPES",
    "PACKAGE_STATUSES",
    "HUMAN_ACCEPTANCE_STATUSES",
    "SECTION_STATUSES",
    "GATE_TYPES",
    "GATE_STATUSES",
    "GATE_DECISIONS",
    "HUMAN_REVIEW_STATUSES",
    "CHECK_TYPES",
    "CHECK_STATUSES",
    "CHECK_SEVERITIES",
    "OPERATOR_REVIEW_STATUSES",
    "SUMMARY_TYPES",
    "READINESS_STATUSES",
    "REQUIRED_SECTION_KEYS",
    "DEFAULT_AGENT",
]
