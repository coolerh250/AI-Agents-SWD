"""Stage 34 -- tamper-evident audit chain SDK.

This package adds an integrity hash chain alongside the existing
``audit_logs`` table without modifying it. The flow is:

    audit_logs row written
        -> canonical_payload(audit_log row)            (canonical.py)
        -> canonical_payload_hash = SHA-256(canonical) (hasher.py)
        -> row_hash = SHA-256(chain_version || sequence ||
                               audit_log_id || prev_hash ||
                               canonical_payload_hash) (hasher.py)
        -> hmac_signature = HMAC-SHA256(key, row_hash) (signer.py)
                                                       optional
        -> audit_integrity_records INSERT              (store.py)

A verifier (``verifier.py``) walks the chain by ``sequence_number`` and
re-computes both hashes (and the HMAC if the key is configured). Any
divergence is reported with ``first_failure_sequence`` +
``first_failure_audit_log_id`` -- the verifier never auto-repairs.

The module is pure for canonicalisation + hashing; the store and the
verifier touch Postgres. None of these functions ever reads, returns,
or logs a key or token value.
"""

from __future__ import annotations

from .canonical import build_canonical_payload, canonical_json
from .hasher import GENESIS_PREV_HASH, compute_payload_hash, compute_row_hash
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
from .signer import AuditSigner
from .store import AuditIntegrityStore
from .verifier import AuditChainVerifier, VerificationResult

__all__ = [
    "CHAIN_VERSION",
    "GENESIS_PREV_HASH",
    "INTEGRITY_STATUS_ACTIVE",
    "INTEGRITY_STATUS_BACKFILLED",
    "INTEGRITY_STATUS_INVALIDATED",
    "SIGNATURE_STATUS_NOT_CONFIGURED",
    "SIGNATURE_STATUS_SIGNED",
    "SIGNATURE_STATUS_UNSIGNED",
    "VERIFICATION_STATUS_ERROR",
    "VERIFICATION_STATUS_FAILED",
    "VERIFICATION_STATUS_PARTIAL",
    "VERIFICATION_STATUS_PASSED",
    "AuditChainVerificationRun",
    "AuditChainVerifier",
    "AuditIntegrityRecord",
    "AuditIntegrityStore",
    "AuditSigner",
    "VerificationResult",
    "build_canonical_payload",
    "canonical_json",
    "compute_payload_hash",
    "compute_row_hash",
]
