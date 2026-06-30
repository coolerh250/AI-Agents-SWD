"""Step 61 -- backup / restore / DR operations data models + constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Environments
ENV_LOCAL = "local"
ENV_DEV = "dev"
ENV_TEST = "test"
ENV_NONPROD = "nonprod"
ALLOWED_ENVIRONMENTS = (ENV_LOCAL, ENV_DEV, ENV_TEST, ENV_NONPROD)
FORBIDDEN_ENVIRONMENTS = ("production", "prod")

# Artifact classes
ARTIFACT_CLASSES = (
    "runtime_evidence",
    "database_dump",
    "redis_snapshot",
    "audit_export",
    "security_summary",
    "release_evidence",
    "temporary_trace",
    "temporary_build_cache",
    "scheduled_dr_report",
    "regression_report",
    "orphan_volume",
    "cluster_runtime_state",
)

# Restore types
RESTORE_TYPES = (
    "validate_backup",
    "restore_nonproduction_copy",
    "dry_run_restore",
    "schema_validation",
    "integrity_validation",
)
FORBIDDEN_RESTORE_TYPES = (
    "restore_production",
    "overwrite_production",
    "failover_production",
    "restore_customer_data",
)

# Restore validation types
VALIDATION_TYPES = (
    "manifest_integrity_check",
    "schema_validation",
    "redaction_validation",
    "artifact_freshness_check",
    "restore_dry_run",
    "nonproduction_copy_restore",
    "post_restore_consistency_check",
)

# DR operation types
DR_OPERATION_TYPES = (
    "backup_inventory",
    "backup_validation",
    "restore_plan_created",
    "restore_validation",
    "cleanup_review",
    "dr_readiness_assessment",
)
FORBIDDEN_DR_OPERATION_TYPES = (
    "production_failover",
    "production_restore",
    "cross_region_failover",
    "production_data_overwrite",
)

# Cleanup scopes that are always blocked.
FORBIDDEN_CLEANUP_SCOPES = (
    "kind_cluster",
    "argocd",
    "active_database",
    "active_redis",
    "active_runtime_state",
)

DR_READINESS_DECISIONS = (
    "not_ready",
    "blocked_by_missing_evidence",
    "blocked_by_policy",
    "ready_for_operator_review",
)


@dataclass
class CleanupReview:
    cleanup_review_id: str
    scope: str
    candidates: list[dict[str, Any]]
    allowed_count: int = 0
    blocked_count: int = 0
    requires_approval_count: int = 0
    estimated_size_bytes: int = 0
    risk_level: str = "low"
    cleanup_executed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "cleanup_review_id": self.cleanup_review_id,
            "scope": self.scope,
            "candidates": self.candidates,
            "allowed_count": self.allowed_count,
            "blocked_count": self.blocked_count,
            "requires_approval_count": self.requires_approval_count,
            "estimated_size_bytes": self.estimated_size_bytes,
            "risk_level": self.risk_level,
            "cleanup_executed": False,
        }


@dataclass
class RestorePlan:
    restore_plan_id: str
    target: str
    source_artifact: str | None
    target_environment: str
    restore_type: str
    status: str = "planned"
    requires_human_approval: bool = False
    production_restore: bool = False
    validation_required: bool = True
    rollback_plan_required: bool = True
    blocked_reason: str | None = None
    policy_decision: str = "pending"

    def to_dict(self) -> dict[str, Any]:
        return {
            "restore_plan_id": self.restore_plan_id,
            "target": self.target,
            "source_artifact": self.source_artifact,
            "target_environment": self.target_environment,
            "restore_type": self.restore_type,
            "status": self.status,
            "requires_human_approval": self.requires_human_approval,
            "production_restore": False,
            "validation_required": self.validation_required,
            "rollback_plan_required": self.rollback_plan_required,
            "policy_decision": self.policy_decision,
            "blocked_reason": self.blocked_reason,
            "restore_executed": False,
        }


@dataclass
class RestoreValidationResult:
    validation_id: str
    restore_plan_id: str | None
    validation_types: list[str]
    status: str = "passed"
    checks: list[dict[str, Any]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "restore_plan_id": self.restore_plan_id,
            "validation_types": self.validation_types,
            "status": self.status,
            "checks": self.checks,
            "missing": self.missing,
            "active_database_overwritten": False,
            "active_redis_overwritten": False,
            "argocd_sync_performed": False,
            "kind_cluster_mutated": False,
            "production_executed": False,
        }


@dataclass
class DROperation:
    dr_operation_id: str
    operation_type: str
    target_environment: str
    status: str = "recorded"
    policy_decision: str = "recorded"
    blocked_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dr_operation_id": self.dr_operation_id,
            "operation_type": self.operation_type,
            "target_environment": self.target_environment,
            "status": self.status,
            "policy_decision": self.policy_decision,
            "blocked_reason": self.blocked_reason,
            "production_restore": False,
            "production_failover": False,
            "production_executed": False,
        }


@dataclass
class DRReadinessResult:
    decision: str
    production_ready: bool = False
    production_restore_ready: bool = False
    blockers: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "production_ready": False,
            "production_restore_ready": False,
            "blockers": self.blockers,
            "missing_evidence": self.missing_evidence,
        }
