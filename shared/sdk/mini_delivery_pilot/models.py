"""Stage 48 -- Pydantic models for the mini project delivery pilot.

Strict validation. No chain-of-thought, no raw prompts -- only summaries,
evidence refs, and counts. Controlled-only: every real-write flag defaults
false and ``production_executed`` is always false.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

PILOT_TYPES = ("fastapi_todo_service", "custom_controlled_project")
PILOT_STATUSES = (
    "created",
    "planning",
    "planned",
    "design_reviewing",
    "design_reviewed",
    "workspace_executing",
    "workspace_completed",
    "qa_evaluating",
    "acceptance_evaluating",
    "safety_evaluating",
    "report_ready",
    "completed",
    "failed",
    "cancelled",
)
STEP_TYPES = (
    "planning",
    "review",
    "implementation",
    "testing",
    "qa",
    "acceptance",
    "safety",
    "reporting",
)
STEP_STATUSES = (
    "pending",
    "running",
    "passed",
    "passed_with_findings",
    "failed",
    "skipped",
    "blocked",
)
EVALUATION_STATUSES = ("satisfied", "failed", "pending", "waived", "not_applicable")
EVIDENCE_TYPES = (
    "test_run",
    "static_check",
    "generated_file",
    "workspace_artifact",
    "manual_review_required",
    "documentation_review",
)
QA_STATUSES = ("passed", "passed_with_findings", "failed", "blocked")
SAFETY_STATUSES = ("safe", "safe_with_findings", "blocked", "failed")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MiniDeliveryPilot(_Strict):
    pilot_key: str
    pilot_type: str = "fastapi_todo_service"
    status: str = "created"
    project_id: str | None = None
    workspace_id: str | None = None
    design_review_session_id: str | None = None
    graph_snapshot_id: str | None = None
    source_task_id: str | None = None
    controlled_only: bool = True
    real_llm_enabled: bool = False
    github_write_enabled: bool = False
    pr_creation_enabled: bool = False
    deployment_enabled: bool = False
    production_executed: bool = False
    created_by_agent: str = "mini-delivery-pilot-agent"
    metadata: dict = Field(default_factory=dict)


class MiniDeliveryPilotStep(_Strict):
    step_key: str
    step_type: str
    status: str = "pending"
    evidence_refs: list = Field(default_factory=list)
    summary: str | None = None
    metadata: dict = Field(default_factory=dict)


class AcceptanceEvaluation(_Strict):
    acceptance_criterion_id: str | None = None
    work_item_id: str | None = None
    evaluation_status: str = "pending"
    evidence_type: str = "manual_review_required"
    evidence_ref: dict = Field(default_factory=dict)
    evaluator: str = "mini-delivery-pilot-agent"
    rationale_summary: str | None = None
    criterion_key: str | None = None
    metadata: dict = Field(default_factory=dict)


class QAEvidenceReport(_Strict):
    status: str = "blocked"
    tests_total: int | None = None
    tests_passed: int | None = None
    tests_failed: int | None = None
    static_checks_status: str | None = None
    coverage_summary: dict = Field(default_factory=dict)
    findings: list = Field(default_factory=list)
    report_summary: str | None = None
    created_by_agent: str = "mini-delivery-pilot-agent"
    metadata: dict = Field(default_factory=dict)


class SafetyEvidenceReport(_Strict):
    status: str = "safe"
    production_executed_count: int = 0
    github_write_performed: bool = False
    pr_created: bool = False
    deployment_performed: bool = False
    real_llm_used: bool = False
    real_external_delivery_performed: bool = False
    repo_root_modified: bool = False
    secret_leak_detected: bool = False
    chain_of_thought_persisted: bool = False
    findings: list = Field(default_factory=list)
    report_summary: str | None = None
    created_by_agent: str = "mini-delivery-pilot-agent"
    metadata: dict = Field(default_factory=dict)


class MiniDeliveryReport(_Strict):
    report_type: str = "mini_delivery_pilot_report"
    status: str = "draft"
    title: str | None = None
    executive_summary: str | None = None
    project_summary: dict = Field(default_factory=dict)
    design_review_summary: dict = Field(default_factory=dict)
    workspace_summary: dict = Field(default_factory=dict)
    qa_summary: dict = Field(default_factory=dict)
    acceptance_summary: dict = Field(default_factory=dict)
    safety_summary: dict = Field(default_factory=dict)
    known_limitations: list = Field(default_factory=list)
    next_steps: list = Field(default_factory=list)
    artifact_refs: list = Field(default_factory=list)
    created_by_agent: str = "mini-delivery-pilot-agent"
    metadata: dict = Field(default_factory=dict)


class PilotArtifact(_Strict):
    artifact_type: str
    title: str | None = None
    content: dict | None = None
    uri: str | None = None
    created_by_agent: str = "mini-delivery-pilot-agent"
    metadata: dict = Field(default_factory=dict)


class MiniDeliveryPilotRequest(_Strict):
    request_text: str = (
        "Create a FastAPI Todo Service with CRUD, SQLite, pytest, README, and API examples."
    )
    project_id: str | None = None
    design_review_session_id: str | None = None
    workspace_id: str | None = None
    pilot_type: str = "fastapi_todo_service"
    controlled_only: bool = True
    requested_by_agent: str = "mini-delivery-pilot-agent"
    source_task_id: str | None = None


class MiniDeliveryPilotResult(_Strict):
    pilot_id: str | None = None
    pilot_key: str | None = None
    pilot_type: str = "fastapi_todo_service"
    project_id: str | None = None
    design_review_session_id: str | None = None
    workspace_id: str | None = None
    qa_report_id: str | None = None
    safety_report_id: str | None = None
    mini_delivery_report_id: str | None = None
    acceptance_total: int = 0
    acceptance_satisfied: int = 0
    acceptance_failed: int = 0
    acceptance_pending: int = 0
    tests_status: str | None = None
    qa_status: str | None = None
    safety_status: str | None = None
    pilot_status: str = "failed"
    blocked_reason: str | None = None
    controlled_only: bool = True
    production_executed: bool = False
    github_write_performed: bool = False
    pr_created: bool = False
    deployment_performed: bool = False
    real_llm_used: bool = False
    metadata: dict = Field(default_factory=dict)


__all__ = [
    "MiniDeliveryPilot",
    "MiniDeliveryPilotStep",
    "AcceptanceEvaluation",
    "QAEvidenceReport",
    "SafetyEvidenceReport",
    "MiniDeliveryReport",
    "PilotArtifact",
    "MiniDeliveryPilotRequest",
    "MiniDeliveryPilotResult",
    "PILOT_TYPES",
    "PILOT_STATUSES",
    "STEP_TYPES",
    "STEP_STATUSES",
    "EVALUATION_STATUSES",
    "EVIDENCE_TYPES",
    "QA_STATUSES",
    "SAFETY_STATUSES",
]
