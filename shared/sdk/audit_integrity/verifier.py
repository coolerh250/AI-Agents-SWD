"""Walk audit_logs + audit_integrity_records and verify the chain.

Reads both tables, joins by ``audit_log_id``, walks them by ascending
``sequence_number``, and for each row:

* re-builds the canonical payload from the audit_logs row,
* re-computes ``canonical_payload_hash`` and ``row_hash``,
* confirms the stored ``prev_hash`` matches the previous row's
  ``row_hash``,
* if a signature is present, re-verifies the HMAC with the configured
  key (when configured).

Stops at the first mismatch and returns a :class:`VerificationResult`
with the failure coordinates. The verifier never auto-repairs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import asyncpg

from .canonical import build_canonical_payload
from .hasher import compute_payload_hash, compute_row_hash
from .models import (
    CHAIN_VERSION,
    SIGNATURE_STATUS_SIGNED,
    VERIFICATION_STATUS_ERROR,
    VERIFICATION_STATUS_FAILED,
    VERIFICATION_STATUS_PARTIAL,
    VERIFICATION_STATUS_PASSED,
    AuditChainVerificationRun,
)
from .signer import AuditSigner

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"


@dataclass
class VerificationResult:
    status: str
    chain_version: int
    total_records: int
    verified_records: int
    failed_records: int
    first_failure_sequence: int | None = None
    first_failure_audit_log_id: str | None = None
    failure_reason: str | None = None
    missing_integrity_records: int = 0
    extra_integrity_records: int = 0
    audit_logs_count: int = 0
    integrity_records_count: int = 0
    hmac_enabled: bool = False
    signing_key_id: str | None = None
    expected_hash: str | None = None
    actual_hash: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "chain_version": self.chain_version,
            "total_records": self.total_records,
            "verified_records": self.verified_records,
            "failed_records": self.failed_records,
            "first_failure_sequence": self.first_failure_sequence,
            "first_failure_audit_log_id": self.first_failure_audit_log_id,
            "failure_reason": self.failure_reason,
            "missing_integrity_records": self.missing_integrity_records,
            "extra_integrity_records": self.extra_integrity_records,
            "audit_logs_count": self.audit_logs_count,
            "integrity_records_count": self.integrity_records_count,
            "hmac_enabled": self.hmac_enabled,
            "signing_key_id": self.signing_key_id,
            # expected/actual hashes intentionally excluded from the
            # operator-facing dict by default; the caller can opt in.
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (self.completed_at.isoformat() if self.completed_at else None),
            "metadata": self.metadata or {},
        }


class AuditChainVerifier:
    """Read-only verifier. Never mutates audit_logs or integrity records."""

    def __init__(
        self,
        dsn: str | None = None,
        *,
        signer: AuditSigner | None = None,
    ) -> None:
        self.dsn = dsn or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
        self._signer = signer or AuditSigner()

    @property
    def signer(self) -> AuditSigner:
        return self._signer

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.dsn, timeout=5)

    async def verify_chain(self, chain_version: int = CHAIN_VERSION) -> VerificationResult:
        started = datetime.now(timezone.utc)
        result = VerificationResult(
            status=VERIFICATION_STATUS_PASSED,
            chain_version=chain_version,
            total_records=0,
            verified_records=0,
            failed_records=0,
            hmac_enabled=self._signer.configured,
            signing_key_id=self._signer.key_id,
            started_at=started,
        )

        conn = await self._connect()
        try:
            audit_count = int(await conn.fetchval("SELECT COUNT(*) FROM audit_logs"))
            integrity_count = int(
                await conn.fetchval(
                    "SELECT COUNT(*) FROM audit_integrity_records " "WHERE chain_version = $1",
                    chain_version,
                )
            )
            rows = await conn.fetch(
                "SELECT r.sequence_number, r.audit_log_id, r.prev_hash, "
                "r.row_hash, r.canonical_payload_hash, r.hmac_signature, "
                "r.signature_status, "
                "al.task_id, al.agent, al.decision_type, al.summary, "
                "al.result, al.artifact_refs, al.created_at "
                "FROM audit_integrity_records r "
                "JOIN audit_logs al ON al.id = r.audit_log_id "
                "WHERE r.chain_version = $1 "
                "ORDER BY r.sequence_number ASC",
                chain_version,
            )
        finally:
            await conn.close()

        result.audit_logs_count = audit_count
        result.integrity_records_count = integrity_count
        result.total_records = len(rows)
        result.missing_integrity_records = max(0, audit_count - integrity_count)
        result.extra_integrity_records = max(0, integrity_count - audit_count)

        prev_seq = 0
        prev_row_hash: str | None = None
        for row in rows:
            seq = int(row["sequence_number"])
            audit_log_id = str(row["audit_log_id"])
            canonical = build_canonical_payload(
                {
                    "audit_log_id": audit_log_id,
                    "task_id": row["task_id"],
                    "agent": row["agent"],
                    "decision_type": row["decision_type"],
                    "summary": row["summary"],
                    "result": row["result"],
                    "artifact_refs": row["artifact_refs"],
                    "created_at": row["created_at"],
                }
            )
            recomputed_payload_hash = compute_payload_hash(canonical)
            recomputed_row_hash = compute_row_hash(
                chain_version=chain_version,
                sequence_number=seq,
                audit_log_id=audit_log_id,
                prev_hash=row["prev_hash"],
                canonical_payload_hash=recomputed_payload_hash,
            )

            if seq != prev_seq + 1:
                result.status = VERIFICATION_STATUS_FAILED
                result.failed_records += 1
                result.first_failure_sequence = seq
                result.first_failure_audit_log_id = audit_log_id
                result.failure_reason = f"sequence_gap: expected {prev_seq + 1}, got {seq}"
                result.expected_hash = str(prev_seq + 1)
                result.actual_hash = str(seq)
                break

            if recomputed_payload_hash != row["canonical_payload_hash"]:
                result.status = VERIFICATION_STATUS_FAILED
                result.failed_records += 1
                result.first_failure_sequence = seq
                result.first_failure_audit_log_id = audit_log_id
                result.failure_reason = "canonical_payload_hash_mismatch"
                result.expected_hash = row["canonical_payload_hash"]
                result.actual_hash = recomputed_payload_hash
                break

            if recomputed_row_hash != row["row_hash"]:
                result.status = VERIFICATION_STATUS_FAILED
                result.failed_records += 1
                result.first_failure_sequence = seq
                result.first_failure_audit_log_id = audit_log_id
                result.failure_reason = "row_hash_mismatch"
                result.expected_hash = row["row_hash"]
                result.actual_hash = recomputed_row_hash
                break

            if seq > 1 and row["prev_hash"] != prev_row_hash:
                result.status = VERIFICATION_STATUS_FAILED
                result.failed_records += 1
                result.first_failure_sequence = seq
                result.first_failure_audit_log_id = audit_log_id
                result.failure_reason = "prev_hash_mismatch"
                result.expected_hash = prev_row_hash or ""
                result.actual_hash = row["prev_hash"] or ""
                break

            if (
                row["signature_status"] == SIGNATURE_STATUS_SIGNED
                and self._signer.configured
                and not self._signer.verify(row["row_hash"], row["hmac_signature"])
            ):
                result.status = VERIFICATION_STATUS_FAILED
                result.failed_records += 1
                result.first_failure_sequence = seq
                result.first_failure_audit_log_id = audit_log_id
                result.failure_reason = "hmac_signature_invalid"
                # Do not surface signature bytes themselves.
                result.expected_hash = None
                result.actual_hash = None
                break

            result.verified_records += 1
            prev_seq = seq
            prev_row_hash = row["row_hash"]

        # If chain is fine BUT we are missing rows, downgrade to partial.
        if result.status == VERIFICATION_STATUS_PASSED and result.missing_integrity_records > 0:
            result.status = VERIFICATION_STATUS_PARTIAL
            result.failure_reason = (
                f"{result.missing_integrity_records} audit_logs row(s) " "lack an integrity record"
            )

        result.completed_at = datetime.now(timezone.utc)
        return result

    def to_run(self, result: VerificationResult) -> AuditChainVerificationRun:
        """Adapt a verifier result into an ``audit_chain_verification_runs`` row."""
        meta = {
            "missing_integrity_records": result.missing_integrity_records,
            "extra_integrity_records": result.extra_integrity_records,
            "audit_logs_count": result.audit_logs_count,
            "integrity_records_count": result.integrity_records_count,
            "hmac_enabled": result.hmac_enabled,
            "signing_key_id": result.signing_key_id,
        }
        return AuditChainVerificationRun(
            verification_id="",  # filled by INSERT default
            chain_version=result.chain_version,
            status=result.status,
            total_records=result.total_records,
            verified_records=result.verified_records,
            failed_records=result.failed_records,
            first_failure_sequence=result.first_failure_sequence,
            first_failure_audit_log_id=result.first_failure_audit_log_id,
            failure_reason=result.failure_reason,
            started_at=result.started_at,
            completed_at=result.completed_at,
            metadata=meta,
        )


__all__ = [
    "AuditChainVerifier",
    "VerificationResult",
    "VERIFICATION_STATUS_ERROR",
]
