"""Walk audit_logs + audit_integrity_records and verify the chain.

Stage 39 adds:

* per-row key lookup -- a row's signature is verified with the key
  named by its ``signing_key_id``, not the currently-active key. This
  is what makes HMAC key rotation safe.
* verification modes -- ``permissive`` (default), ``strict``, and
  ``chain_only``. ``strict`` fails the run when a signed row's key is
  missing or unsigned-legacy rows appear; ``chain_only`` ignores
  HMAC entirely.
* keyring metadata in the verification run -- ``keyring_mode``,
  ``active_key_id``, signed/unsigned/missing/failed counters, and the
  effective verification mode.

The verifier still never auto-repairs. Failure coordinates are
captured on the result so an operator can locate the bad row.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import asyncpg

from .canonical import build_canonical_payload
from .hasher import compute_payload_hash, compute_row_hash
from .keyring import KEYRING_MODE_NONE
from .models import (
    CHAIN_VERSION,
    SIGNATURE_STATUS_NOT_CONFIGURED,
    SIGNATURE_STATUS_SIGNED,
    SIGNATURE_STATUS_UNSIGNED,
    VERIFICATION_STATUS_ERROR,
    VERIFICATION_STATUS_FAILED,
    VERIFICATION_STATUS_PARTIAL,
    VERIFICATION_STATUS_PASSED,
    AuditChainVerificationRun,
)
from .signer import (
    VERIFY_OUTCOME_KEY_MISSING,
    VERIFY_OUTCOME_NO_KEYRING,
    VERIFY_OUTCOME_SIGNATURE_FAILED,
    AuditSigner,
)

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

VERIFY_MODE_PERMISSIVE = "permissive"
VERIFY_MODE_STRICT = "strict"
VERIFY_MODE_CHAIN_ONLY = "chain_only"

_VALID_VERIFY_MODES = (
    VERIFY_MODE_PERMISSIVE,
    VERIFY_MODE_STRICT,
    VERIFY_MODE_CHAIN_ONLY,
)


def resolve_verify_mode(requested: str | None) -> str:
    """Map a caller-supplied mode (or env default) to a valid mode."""
    candidate = (requested or "").strip().lower()
    if candidate in _VALID_VERIFY_MODES:
        return candidate
    env_default = (os.environ.get("AUDIT_VERIFY_SIGNATURE_MODE", "") or "").strip().lower()
    if env_default in _VALID_VERIFY_MODES:
        return env_default
    return VERIFY_MODE_PERMISSIVE


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
    # Stage 39 fields.
    mode: str = VERIFY_MODE_PERMISSIVE
    keyring_mode: str = KEYRING_MODE_NONE
    active_signing_key_id: str | None = None
    known_key_ids: list[str] = field(default_factory=list)
    signed_records: int = 0
    unsigned_records: int = 0
    key_missing_records: int = 0
    signature_failed_records: int = 0
    warnings: list[str] = field(default_factory=list)

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
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (self.completed_at.isoformat() if self.completed_at else None),
            "metadata": self.metadata or {},
            "mode": self.mode,
            "keyring_mode": self.keyring_mode,
            "active_signing_key_id": self.active_signing_key_id,
            "known_key_ids": list(self.known_key_ids),
            "signed_records": self.signed_records,
            "unsigned_records": self.unsigned_records,
            "key_missing_records": self.key_missing_records,
            "signature_failed_records": self.signature_failed_records,
            "warnings": list(self.warnings),
        }


class AuditChainVerifier:
    """Read-only verifier. Never mutates audit_logs or integrity records."""

    def __init__(
        self,
        dsn: str | None = None,
        *,
        signer: AuditSigner | None = None,
        mode: str | None = None,
    ) -> None:
        self.dsn = dsn or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
        self._signer = signer or AuditSigner()
        self._mode = resolve_verify_mode(mode)

    @property
    def signer(self) -> AuditSigner:
        return self._signer

    @property
    def mode(self) -> str:
        return self._mode

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.dsn, timeout=5)

    async def verify_chain(self, chain_version: int = CHAIN_VERSION) -> VerificationResult:
        keyring = self._signer.keyring
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
            mode=self._mode,
            keyring_mode=keyring.mode,
            active_signing_key_id=keyring.active_key_id,
            known_key_ids=keyring.known_key_ids,
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
                "r.signature_status, r.signing_key_id, "
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

            # Per-row signature verification (Stage 39 -- keyring aware).
            sig_status = row["signature_status"]
            row_failed = False
            if self._mode == VERIFY_MODE_CHAIN_ONLY:
                pass  # ignore HMAC entirely
            elif sig_status == SIGNATURE_STATUS_SIGNED:
                ok, outcome = self._signer.verify_with(
                    row_hash=row["row_hash"],
                    signature=row["hmac_signature"],
                    signing_key_id=row["signing_key_id"],
                )
                if ok:
                    result.signed_records += 1
                else:
                    if outcome == VERIFY_OUTCOME_KEY_MISSING:
                        result.key_missing_records += 1
                        if self._mode == VERIFY_MODE_STRICT:
                            result.status = VERIFICATION_STATUS_FAILED
                            result.failed_records += 1
                            result.first_failure_sequence = seq
                            result.first_failure_audit_log_id = audit_log_id
                            result.failure_reason = "hmac_signing_key_missing"
                            result.expected_hash = None
                            result.actual_hash = None
                            row_failed = True
                        else:
                            result.warnings.append(
                                f"seq={seq} signing_key_id "
                                f"'{row['signing_key_id']}' missing from keyring"
                            )
                    elif outcome == VERIFY_OUTCOME_NO_KEYRING:
                        # signed row but no keyring is loaded
                        result.key_missing_records += 1
                        if self._mode == VERIFY_MODE_STRICT:
                            result.status = VERIFICATION_STATUS_FAILED
                            result.failed_records += 1
                            result.first_failure_sequence = seq
                            result.first_failure_audit_log_id = audit_log_id
                            result.failure_reason = "hmac_keyring_not_configured"
                            row_failed = True
                        else:
                            result.warnings.append(
                                f"seq={seq} signed row found but no HMAC " f"keyring is configured"
                            )
                    elif outcome == VERIFY_OUTCOME_SIGNATURE_FAILED:
                        result.signature_failed_records += 1
                        result.status = VERIFICATION_STATUS_FAILED
                        result.failed_records += 1
                        result.first_failure_sequence = seq
                        result.first_failure_audit_log_id = audit_log_id
                        result.failure_reason = "hmac_signature_invalid"
                        result.expected_hash = None
                        result.actual_hash = None
                        row_failed = True
            elif sig_status == SIGNATURE_STATUS_NOT_CONFIGURED:
                result.unsigned_records += 1
                if self._mode == VERIFY_MODE_STRICT and not _allow_unsigned_legacy():
                    result.status = VERIFICATION_STATUS_FAILED
                    result.failed_records += 1
                    result.first_failure_sequence = seq
                    result.first_failure_audit_log_id = audit_log_id
                    result.failure_reason = "unsigned_row_under_strict_mode"
                    row_failed = True
            elif sig_status == SIGNATURE_STATUS_UNSIGNED:
                result.unsigned_records += 1
            else:
                result.warnings.append(f"seq={seq} unknown signature_status={sig_status!r}")

            if row_failed:
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

        # Permissive mode: a row marked key_missing keeps the run PASS
        # but is downgraded to partial when nothing else has gone wrong.
        if (
            result.status == VERIFICATION_STATUS_PASSED
            and result.key_missing_records > 0
            and self._mode == VERIFY_MODE_PERMISSIVE
        ):
            result.status = VERIFICATION_STATUS_PARTIAL
            result.failure_reason = (
                f"{result.key_missing_records} signed row(s) lack a known signing key"
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
            "verification_mode": result.mode,
            "keyring_mode": result.keyring_mode,
            "active_signing_key_id": result.active_signing_key_id,
            "signed_records": result.signed_records,
            "unsigned_records": result.unsigned_records,
            "key_missing_records": result.key_missing_records,
            "signature_failed_records": result.signature_failed_records,
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


def _allow_unsigned_legacy() -> bool:
    """Strict mode escape hatch for pre-existing unsigned rows."""
    return (os.environ.get("AUDIT_VERIFY_ALLOW_UNSIGNED_LEGACY", "") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


__all__ = [
    "AuditChainVerifier",
    "VerificationResult",
    "VERIFICATION_STATUS_ERROR",
    "VERIFY_MODE_PERMISSIVE",
    "VERIFY_MODE_STRICT",
    "VERIFY_MODE_CHAIN_ONLY",
    "resolve_verify_mode",
]
