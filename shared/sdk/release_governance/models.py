"""Step 60 -- release & deployment governance data models + constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Environments
ENV_DEV = "dev"
ENV_TEST = "test"
ENV_NONPROD = "nonprod"
ALLOWED_ENVIRONMENTS = (ENV_DEV, ENV_TEST, ENV_NONPROD)
FORBIDDEN_ENVIRONMENTS = ("production", "prod")

# Release candidate statuses
RC_STATUSES = (
    "draft",
    "evidence_collecting",
    "ready_for_operator_review",
    "blocked",
    "rejected",
    "accepted_nonproduction",
    "archived",
)

# Deployment intent requested actions
ACTION_VALIDATE_ONLY = "validate_only"
ACTION_PREPARE_NONPROD = "prepare_nonproduction"
ACTION_REQUEST_OPERATOR_REVIEW = "request_operator_review"
ALLOWED_ACTIONS = (ACTION_VALIDATE_ONLY, ACTION_PREPARE_NONPROD, ACTION_REQUEST_OPERATOR_REVIEW)
FORBIDDEN_ACTIONS = (
    "deploy_production",
    "sync_production",
    "merge_pr",
    "push_image",
    "create_release",
    "create_tag",
)

# Deployment intent statuses
DI_STATUSES = ("created", "validated", "blocked", "operator_review_requested")

# Readiness decisions
READINESS_DECISIONS = (
    "not_ready",
    "ready_for_operator_review",
    "blocked_by_missing_evidence",
    "blocked_by_security",
    "blocked_by_policy",
    "accepted_nonproduction",
)


@dataclass
class ReleaseCandidate:
    release_candidate_id: str
    project_id: str | None
    work_item_ids: list[str]
    delivery_package_ids: list[str]
    sandbox_draft_pr_ids: list[str]
    version_label: str
    target_environment: str
    status: str = "draft"
    readiness_status: str = "not_ready"
    security_status: str = "unknown"
    runtime_status: str = "unknown"
    gitops_status: str = "unknown"
    approval_status: str = "not_requested"
    production_ready: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "release_candidate_id": self.release_candidate_id,
            "project_id": self.project_id,
            "work_item_ids": self.work_item_ids,
            "delivery_package_ids": self.delivery_package_ids,
            "sandbox_draft_pr_ids": self.sandbox_draft_pr_ids,
            "version_label": self.version_label,
            "target_environment": self.target_environment,
            "status": self.status,
            "readiness_status": self.readiness_status,
            "security_status": self.security_status,
            "runtime_status": self.runtime_status,
            "gitops_status": self.gitops_status,
            "approval_status": self.approval_status,
            "production_ready": False,
        }


@dataclass
class DeploymentIntent:
    deployment_intent_id: str
    release_candidate_id: str
    target_environment: str
    requested_action: str
    status: str = "created"
    target_runtime: str | None = None
    target_gitops_application: str | None = None
    requires_human_approval: bool = False
    policy_decision: str = "pending"
    blocked_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "deployment_intent_id": self.deployment_intent_id,
            "release_candidate_id": self.release_candidate_id,
            "target_environment": self.target_environment,
            "target_runtime": self.target_runtime,
            "target_gitops_application": self.target_gitops_application,
            "requested_action": self.requested_action,
            "status": self.status,
            "requires_human_approval": self.requires_human_approval,
            "policy_decision": self.policy_decision,
            "blocked_reason": self.blocked_reason,
            "production_executed": False,
            "deploy_performed": False,
            "argocd_sync_performed": False,
            "merge_performed": False,
            "image_push_performed": False,
        }


@dataclass
class ReadinessResult:
    decision: str
    production_ready: bool = False
    blockers: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "production_ready": False,
            "blockers": self.blockers,
            "missing_evidence": self.missing_evidence,
        }
