"""Data models + constants for the audit integrity SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

CHAIN_VERSION = 1

SIGNATURE_STATUS_UNSIGNED = "unsigned"
SIGNATURE_STATUS_SIGNED = "signed"
SIGNATURE_STATUS_NOT_CONFIGURED = "signing_key_not_configured"

INTEGRITY_STATUS_ACTIVE = "active"
INTEGRITY_STATUS_BACKFILLED = "backfilled"
INTEGRITY_STATUS_INVALIDATED = "invalidated"

VERIFICATION_STATUS_PASSED = "passed"
VERIFICATION_STATUS_FAILED = "failed"
VERIFICATION_STATUS_PARTIAL = "partial"
VERIFICATION_STATUS_ERROR = "error"


@dataclass
class AuditIntegrityRecord:
    """One row of ``audit_integrity_records``.

    The ``hmac_signature`` is a hex digest when signed; a missing key
    yields ``None`` and ``signature_status=signing_key_not_configured``.
    """

    integrity_id: str
    audit_log_id: str
    chain_version: int
    sequence_number: int
    prev_hash: str | None
    row_hash: str
    canonical_payload_hash: str
    hmac_signature: str | None
    signing_key_id: str | None
    signature_status: str
    integrity_status: str
    created_at: datetime | None

    def to_safe_dict(self, *, include_signature_preview: bool = True) -> dict[str, Any]:
        """Return a dict safe to expose via the operations API.

        The full HMAC signature is replaced by a presence boolean + a
        short prefix preview (max 8 chars). The signing key value is
        never included.
        """
        sig_present = bool(self.hmac_signature)
        sig_preview = ""
        if include_signature_preview and sig_present and self.hmac_signature:
            sig_preview = self.hmac_signature[:8]
        return {
            "integrity_id": self.integrity_id,
            "audit_log_id": self.audit_log_id,
            "chain_version": self.chain_version,
            "sequence_number": self.sequence_number,
            "prev_hash": self.prev_hash,
            "row_hash": self.row_hash,
            "canonical_payload_hash": self.canonical_payload_hash,
            "hmac_signature_present": sig_present,
            "hmac_signature_preview": sig_preview,
            "signing_key_id": self.signing_key_id,
            "signature_status": self.signature_status,
            "integrity_status": self.integrity_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class AuditChainVerificationRun:
    """One row of ``audit_chain_verification_runs``."""

    verification_id: str
    chain_version: int
    status: str
    total_records: int
    verified_records: int
    failed_records: int
    first_failure_sequence: int | None
    first_failure_audit_log_id: str | None
    failure_reason: str | None
    started_at: datetime | None
    completed_at: datetime | None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "chain_version": self.chain_version,
            "status": self.status,
            "total_records": self.total_records,
            "verified_records": self.verified_records,
            "failed_records": self.failed_records,
            "first_failure_sequence": self.first_failure_sequence,
            "first_failure_audit_log_id": self.first_failure_audit_log_id,
            "failure_reason": self.failure_reason,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (self.completed_at.isoformat() if self.completed_at else None),
            "metadata": self.metadata or {},
        }
