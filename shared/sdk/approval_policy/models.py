"""Dataclasses mirroring the Stage 31 approval-policy tables."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

#: Approval-mode strings the evaluator recognises.
APPROVAL_MODES: tuple[str, ...] = (
    "per_action",
    "per_feature",
    "per_stage",
    "delegated",
)

#: Scope-type strings tied to where a policy applies.
SCOPE_TYPES: tuple[str, ...] = (
    "action",
    "feature",
    "stage",
    "workflow",
    "task",
)

#: Lifecycle statuses for human_approval_policies.
POLICY_STATUSES: tuple[str, ...] = (
    "pending",
    "active",
    "expired",
    "revoked",
    "rejected",
)

#: Lifecycle statuses for llm_proposal_promotions.
PROMOTION_STATUSES: tuple[str, ...] = (
    "requested",
    "promoted",
    "validation_failed",
    "qa_passed",
    "qa_blocked",
    "blocked_by_policy",
    "failed",
    "canceled",
)


@dataclass
class HumanApprovalPolicy:
    """One row from ``human_approval_policies``."""

    policy_id: str
    task_id: str
    workflow_id: str | None = None
    scope_type: str = "task"
    scope_id: str = ""
    approval_mode: str = "per_action"
    status: str = "pending"
    granted_by: str = ""
    granted_at: str | None = None
    expires_at: str | None = None
    max_actions: int | None = None
    max_files_changed: int | None = None
    max_auto_fix_attempts: int | None = None
    actions_used: int = 0
    allowed_stages: list[str] = field(default_factory=list)
    allowed_agents: list[str] = field(default_factory=list)
    allowed_actions: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)
    denied_paths: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "scope_type": self.scope_type,
            "scope_id": self.scope_id,
            "approval_mode": self.approval_mode,
            "status": self.status,
            "granted_by": self.granted_by,
            "granted_at": self.granted_at,
            "expires_at": self.expires_at,
            "max_actions": self.max_actions,
            "max_files_changed": self.max_files_changed,
            "max_auto_fix_attempts": self.max_auto_fix_attempts,
            "actions_used": self.actions_used,
            "allowed_stages": list(self.allowed_stages),
            "allowed_agents": list(self.allowed_agents),
            "allowed_actions": list(self.allowed_actions),
            "allowed_paths": list(self.allowed_paths),
            "denied_paths": list(self.denied_paths),
            "constraints": dict(self.constraints),
            "reason": self.reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class HumanApprovalDecision:
    """One row from ``human_approval_decisions``."""

    decision_id: str
    policy_id: str | None
    task_id: str
    workflow_id: str | None = None
    proposal_id: str | None = None
    promotion_id: str | None = None
    action_type: str = ""
    decision: str = "approved"
    decided_by: str = ""
    decided_at: str | None = None
    reason: str | None = None
    safety_snapshot: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "policy_id": self.policy_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "proposal_id": self.proposal_id,
            "promotion_id": self.promotion_id,
            "action_type": self.action_type,
            "decision": self.decision,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
            "reason": self.reason,
            "safety_snapshot": dict(self.safety_snapshot),
            "created_at": self.created_at,
        }


@dataclass
class LLMProposalApproval:
    """One row from ``llm_proposal_approvals``."""

    approval_id: str
    proposal_id: str
    task_id: str
    workflow_id: str | None = None
    approval_mode: str = "per_action"
    policy_id: str | None = None
    requested_by: str = ""
    requested_at: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    rejected_by: str | None = None
    rejected_at: str | None = None
    status: str = "pending"
    reason: str | None = None
    safety_snapshot: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "proposal_id": self.proposal_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "approval_mode": self.approval_mode,
            "policy_id": self.policy_id,
            "requested_by": self.requested_by,
            "requested_at": self.requested_at,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "rejected_by": self.rejected_by,
            "rejected_at": self.rejected_at,
            "status": self.status,
            "reason": self.reason,
            "safety_snapshot": dict(self.safety_snapshot),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class LLMProposalPromotion:
    """One row from ``llm_proposal_promotions``."""

    promotion_id: str
    proposal_id: str
    approval_id: str | None
    policy_id: str | None
    task_id: str
    workflow_id: str | None = None
    workspace_id: str | None = None
    status: str = "requested"
    promoted_by: str = ""
    promoted_at: str | None = None
    promotion_mode: str = "manual"
    promoted_files: list[dict[str, Any]] = field(default_factory=list)
    validation_result: dict[str, Any] = field(default_factory=dict)
    qa_run_id: str | None = None
    pr_draft_id: str | None = None
    error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "promotion_id": self.promotion_id,
            "proposal_id": self.proposal_id,
            "approval_id": self.approval_id,
            "policy_id": self.policy_id,
            "task_id": self.task_id,
            "workflow_id": self.workflow_id,
            "workspace_id": self.workspace_id,
            "status": self.status,
            "promoted_by": self.promoted_by,
            "promoted_at": self.promoted_at,
            "promotion_mode": self.promotion_mode,
            "promoted_files": list(self.promoted_files),
            "validation_result": dict(self.validation_result),
            "qa_run_id": self.qa_run_id,
            "pr_draft_id": self.pr_draft_id,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
