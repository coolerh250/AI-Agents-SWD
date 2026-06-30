"""Step 62 -- production deployment readiness gate data models + constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Decision statuses (the gate can never be production_ready / approved).
DECISION_NOT_READY = "not_ready"
DECISION_BLOCKED_MISSING_EVIDENCE = "blocked_by_missing_evidence"
DECISION_BLOCKED_POLICY = "blocked_by_policy"
DECISION_BLOCKED_PREREQUISITES = "blocked_by_production_prerequisites"
DECISION_READY_FOR_OPERATOR_REVIEW = "ready_for_operator_review"
DECISION_OPERATOR_REVIEW_REQUESTED = "operator_review_requested"
DECISION_STATUSES = (
    DECISION_NOT_READY,
    DECISION_BLOCKED_MISSING_EVIDENCE,
    DECISION_BLOCKED_POLICY,
    DECISION_BLOCKED_PREREQUISITES,
    DECISION_READY_FOR_OPERATOR_REVIEW,
    DECISION_OPERATOR_REVIEW_REQUESTED,
)

# The prerequisite markers that MUST be present (the readiness checklist's hard evidence).
REQUIRED_MARKERS = (
    "IDENTITY_FOUNDATION_BASELINE_VERIFY",
    "SECRET_MANAGEMENT_FOUNDATION_BASELINE_VERIFY",
    "APPLICATION_SECURITY_SUPPLY_CHAIN_BASELINE_VERIFY",
    "NONPRODUCTION_KUBERNETES_RUNTIME_SMOKE_VERIFY",
    "NONPRODUCTION_ARGOCD_MANUAL_SYNC_BASELINE_VERIFY",
    "MULTI_PROJECT_DELIVERY_DISPATCH_BASELINE_VERIFY",
    "SANDBOX_GITHUB_DRAFT_PR_BASELINE_VERIFY",
    "RELEASE_DEPLOYMENT_GOVERNANCE_BASELINE_VERIFY",
    "BACKUP_RESTORE_DR_OPERATIONS_BASELINE_VERIFY",
)


@dataclass
class BlockingRuleResult:
    name: str
    severity: str
    active: bool

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "severity": self.severity, "active": self.active}


@dataclass
class ReadinessDecision:
    decision: str
    production_ready: bool = False
    production_approved: bool = False
    production_action_allowed: bool = False
    hard_blockers: list[str] = field(default_factory=list)
    prerequisite_blockers: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "production_ready": False,
            "production_approved": False,
            "production_action_allowed": False,
            "hard_blockers": self.hard_blockers,
            "prerequisite_blockers": self.prerequisite_blockers,
            "missing_evidence": self.missing_evidence,
        }
