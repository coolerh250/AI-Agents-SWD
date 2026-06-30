"""Step 61 (Stage 63A) -- backup / restore / DR operations SDK.

A controlled, NON-PRODUCTION backup / restore / DR governance baseline: backup inventory,
artifact classification, controlled cleanup review, restore plan, non-production restore
validation, DR operation modelling, recovery evidence, audit. It does NOT perform a
production restore, a production failover, a cleanup execution, a restore execution, a
kind / ArgoCD teardown, or an external / cloud upload. Production stays blocked;
production_ready / production_restore_ready / production_executed are always false.
"""

from __future__ import annotations

from .audit import EVENTS, build_audit_metadata
from .classification import commit_allowed, get_class, load_classes
from .cleanup_review import (
    CleanupReviewError,
    build_cleanup_review,
    classify_candidate,
    is_path_allowlisted,
)
from .dr_operation import DROperationError, build_dr_operation, evaluate_readiness
from .evidence import build_recovery_evidence
from .inventory import load_targets, production_restore_allowed_count
from .models import (
    ALLOWED_ENVIRONMENTS,
    ARTIFACT_CLASSES,
    DR_OPERATION_TYPES,
    FORBIDDEN_DR_OPERATION_TYPES,
    FORBIDDEN_ENVIRONMENTS,
    FORBIDDEN_RESTORE_TYPES,
    RESTORE_TYPES,
    VALIDATION_TYPES,
    CleanupReview,
    DROperation,
    DRReadinessResult,
    RestorePlan,
    RestoreValidationResult,
)
from .restore_plan import RestorePlanError, build_restore_plan
from .restore_validation import build_restore_validation_result
from .safety import backup_restore_dr_safety_fields
from .store import BackupRestoreDrStore

__all__ = [
    "ALLOWED_ENVIRONMENTS",
    "ARTIFACT_CLASSES",
    "DR_OPERATION_TYPES",
    "FORBIDDEN_DR_OPERATION_TYPES",
    "FORBIDDEN_ENVIRONMENTS",
    "FORBIDDEN_RESTORE_TYPES",
    "RESTORE_TYPES",
    "VALIDATION_TYPES",
    "CleanupReview",
    "DROperation",
    "DRReadinessResult",
    "RestorePlan",
    "RestoreValidationResult",
    "CleanupReviewError",
    "DROperationError",
    "RestorePlanError",
    "build_audit_metadata",
    "EVENTS",
    "build_cleanup_review",
    "classify_candidate",
    "is_path_allowlisted",
    "build_dr_operation",
    "evaluate_readiness",
    "build_recovery_evidence",
    "load_targets",
    "production_restore_allowed_count",
    "load_classes",
    "get_class",
    "commit_allowed",
    "build_restore_plan",
    "build_restore_validation_result",
    "backup_restore_dr_safety_fields",
    "BackupRestoreDrStore",
]
