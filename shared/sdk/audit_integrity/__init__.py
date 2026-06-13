"""Stage 34 + Stage 39 -- tamper-evident audit chain SDK.

This package adds an integrity hash chain alongside the existing
``audit_logs`` table without modifying it. The flow is:

    audit_logs row written
        -> canonical_payload(audit_log row)            (canonical.py)
        -> canonical_payload_hash = SHA-256(canonical) (hasher.py)
        -> row_hash = SHA-256(chain_version || sequence ||
                               audit_log_id || prev_hash ||
                               canonical_payload_hash) (hasher.py)
        -> hmac_signature = HMAC-SHA256(active_key, row_hash) (signer.py)
                                                       optional
        -> audit_integrity_records INSERT              (store.py)

Stage 39 adds an HMAC keyring (`keyring.py`) so signing keys can be
rotated, and exposes `create_integrity_record_in_txn` so callers (such
as the audit-service direct POST handler) can persist an audit_logs
row + its integrity row in the same Postgres transaction.

A verifier (``verifier.py``) walks the chain by ``sequence_number`` and
re-computes both hashes (and the HMAC if a keyring is configured).
Any divergence is reported with ``first_failure_sequence`` +
``first_failure_audit_log_id`` -- the verifier never auto-repairs.

The module is pure for canonicalisation + hashing; the store and the
verifier touch Postgres. None of these functions ever reads, returns,
or logs a key or token value.
"""

from __future__ import annotations

from .canonical import build_canonical_payload, canonical_json
from .forensics import (
    AuditChainForensicAnalyzer,
    FailedRecordAnalysis,
    REPAIR_RISK_HIGH,
    REPAIR_RISK_LOW,
    REPAIR_RISK_MEDIUM,
    REPAIRABLE_ROOT_CAUSES,
    ROOT_CAUSE_AUDIT_LOG_MUTATED,
    ROOT_CAUSE_CANONICALIZATION_VERSION_DRIFT,
    ROOT_CAUSE_DIRECT_POST_LEGACY_GAP,
    ROOT_CAUSE_HMAC_KEY_MISSING_ONLY,
    ROOT_CAUSE_MANUAL_DATABASE_CHANGE,
    ROOT_CAUSE_TEST_TAMPER_NOT_RESTORED,
    ROOT_CAUSE_UNKNOWN,
    analyse_record,
    classify_chain_root_cause,
    redact_summary,
)
from .hasher import GENESIS_PREV_HASH, compute_payload_hash, compute_row_hash
from .keyring import (
    DEFAULT_LEGACY_KEY_ID,
    KEY_SOURCE_KEYRING_ENV,
    KEY_SOURCE_LEGACY_ENV,
    KEY_SOURCE_SECRET_PROVIDER,
    KEY_SOURCE_UNKNOWN,
    KEYRING_MODE_INVALID,
    KEYRING_MODE_LEGACY_SINGLE_KEY,
    KEYRING_MODE_MULTI_KEYRING,
    KEYRING_MODE_NONE,
    AuditHmacKeyring,
    KeyringSnapshot,
    keyring_metadata_rows,
)
from .models import (
    AuditChainVerificationRun,
    AuditIntegrityRecord,
    CHAIN_VERSION,
    INTEGRITY_STATUS_ACTIVE,
    INTEGRITY_STATUS_BACKFILLED,
    INTEGRITY_STATUS_INVALIDATED,
    SIGNATURE_STATUS_NOT_CONFIGURED,
    SIGNATURE_STATUS_SIGNED,
    SIGNATURE_STATUS_UNSIGNED,
    VERIFICATION_STATUS_ERROR,
    VERIFICATION_STATUS_FAILED,
    VERIFICATION_STATUS_PARTIAL,
    VERIFICATION_STATUS_PASSED,
)
from .log_restore import (
    AuditLogRestorer,
    RESTORE_STATUS_APPROVAL_REQUIRED,
    RESTORE_STATUS_COMPLETED,
    RESTORE_STATUS_DRY_RUN,
    RESTORE_STATUS_FAILED,
    RESTORE_STATUS_REJECTED_UNSAFE,
    RESTORE_TYPE_TEST_TAMPER_RESIDUE,
    RestorePrecheck,
)
from .repair import (
    AuditChainRepairer,
    REPAIR_STATUS_APPROVAL_REQUIRED,
    REPAIR_STATUS_COMPLETED,
    REPAIR_STATUS_DRY_RUN,
    REPAIR_STATUS_FAILED,
    REPAIR_STATUS_SKIPPED_UNSAFE,
    RepairPlan,
    plan_repair,
)
from .signer import (
    AuditSigner,
    DEFAULT_SIGNING_KEY_ID,
    UNSIGNED_KEY_ID,
    VERIFY_OUTCOME_KEY_MISSING,
    VERIFY_OUTCOME_NO_KEYRING,
    VERIFY_OUTCOME_OK,
    VERIFY_OUTCOME_SIGNATURE_FAILED,
)
from .store import (
    ADVISORY_LOCK_NAME,
    AuditIntegrityStore,
    create_integrity_record_in_txn,
    filter_safe_keyring_rows,
)
from .verifier import (
    AuditChainVerifier,
    VERIFY_MODE_CHAIN_ONLY,
    VERIFY_MODE_PERMISSIVE,
    VERIFY_MODE_STRICT,
    VerificationResult,
    resolve_verify_mode,
)

__all__ = [
    "ADVISORY_LOCK_NAME",
    "CHAIN_VERSION",
    "DEFAULT_LEGACY_KEY_ID",
    "DEFAULT_SIGNING_KEY_ID",
    "GENESIS_PREV_HASH",
    "INTEGRITY_STATUS_ACTIVE",
    "INTEGRITY_STATUS_BACKFILLED",
    "INTEGRITY_STATUS_INVALIDATED",
    "KEY_SOURCE_KEYRING_ENV",
    "KEY_SOURCE_LEGACY_ENV",
    "KEY_SOURCE_SECRET_PROVIDER",
    "KEY_SOURCE_UNKNOWN",
    "KEYRING_MODE_INVALID",
    "KEYRING_MODE_LEGACY_SINGLE_KEY",
    "KEYRING_MODE_MULTI_KEYRING",
    "KEYRING_MODE_NONE",
    "SIGNATURE_STATUS_NOT_CONFIGURED",
    "SIGNATURE_STATUS_SIGNED",
    "SIGNATURE_STATUS_UNSIGNED",
    "UNSIGNED_KEY_ID",
    "VERIFICATION_STATUS_ERROR",
    "VERIFICATION_STATUS_FAILED",
    "VERIFICATION_STATUS_PARTIAL",
    "VERIFICATION_STATUS_PASSED",
    "VERIFY_MODE_CHAIN_ONLY",
    "VERIFY_MODE_PERMISSIVE",
    "VERIFY_MODE_STRICT",
    "VERIFY_OUTCOME_KEY_MISSING",
    "VERIFY_OUTCOME_NO_KEYRING",
    "VERIFY_OUTCOME_OK",
    "VERIFY_OUTCOME_SIGNATURE_FAILED",
    "AuditChainForensicAnalyzer",
    "AuditChainRepairer",
    "AuditLogRestorer",
    "RestorePrecheck",
    "RESTORE_STATUS_APPROVAL_REQUIRED",
    "RESTORE_STATUS_COMPLETED",
    "RESTORE_STATUS_DRY_RUN",
    "RESTORE_STATUS_FAILED",
    "RESTORE_STATUS_REJECTED_UNSAFE",
    "RESTORE_TYPE_TEST_TAMPER_RESIDUE",
    "AuditChainVerificationRun",
    "AuditChainVerifier",
    "AuditHmacKeyring",
    "AuditIntegrityRecord",
    "AuditIntegrityStore",
    "AuditSigner",
    "FailedRecordAnalysis",
    "KeyringSnapshot",
    "RepairPlan",
    "REPAIRABLE_ROOT_CAUSES",
    "REPAIR_RISK_HIGH",
    "REPAIR_RISK_LOW",
    "REPAIR_RISK_MEDIUM",
    "REPAIR_STATUS_APPROVAL_REQUIRED",
    "REPAIR_STATUS_COMPLETED",
    "REPAIR_STATUS_DRY_RUN",
    "REPAIR_STATUS_FAILED",
    "REPAIR_STATUS_SKIPPED_UNSAFE",
    "ROOT_CAUSE_AUDIT_LOG_MUTATED",
    "ROOT_CAUSE_CANONICALIZATION_VERSION_DRIFT",
    "ROOT_CAUSE_DIRECT_POST_LEGACY_GAP",
    "ROOT_CAUSE_HMAC_KEY_MISSING_ONLY",
    "ROOT_CAUSE_MANUAL_DATABASE_CHANGE",
    "ROOT_CAUSE_TEST_TAMPER_NOT_RESTORED",
    "ROOT_CAUSE_UNKNOWN",
    "VerificationResult",
    "analyse_record",
    "build_canonical_payload",
    "canonical_json",
    "classify_chain_root_cause",
    "compute_payload_hash",
    "compute_row_hash",
    "create_integrity_record_in_txn",
    "filter_safe_keyring_rows",
    "keyring_metadata_rows",
    "plan_repair",
    "redact_summary",
    "resolve_verify_mode",
]
