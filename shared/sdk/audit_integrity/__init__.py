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
    "AuditChainVerificationRun",
    "AuditChainVerifier",
    "AuditHmacKeyring",
    "AuditIntegrityRecord",
    "AuditIntegrityStore",
    "AuditSigner",
    "KeyringSnapshot",
    "VerificationResult",
    "build_canonical_payload",
    "canonical_json",
    "compute_payload_hash",
    "compute_row_hash",
    "create_integrity_record_in_txn",
    "filter_safe_keyring_rows",
    "keyring_metadata_rows",
    "resolve_verify_mode",
]
