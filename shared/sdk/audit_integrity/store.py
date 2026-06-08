"""asyncpg-backed store for audit_integrity_records + verification runs.

The store is intentionally small. The audit-worker calls
``create_integrity_record_for_audit_log`` immediately after a
successful ``write_audit_log``; the backfill script calls
``backfill_missing_integrity_records`` once over the existing rows;
the verifier writes one ``record_verification_run`` row per pass.

Every method opens a short-lived connection -- the audit-worker is a
low-frequency consumer, so connection pooling is unnecessary here and
the simpler shape avoids holding a long-lived txn while computing
hashes.
"""

from __future__ import annotations

import json
import os
from typing import Any

import asyncpg

from .canonical import build_canonical_payload
from .hasher import compute_payload_hash, compute_row_hash
from .models import (
    CHAIN_VERSION,
    INTEGRITY_STATUS_ACTIVE,
    INTEGRITY_STATUS_BACKFILLED,
    SIGNATURE_STATUS_NOT_CONFIGURED,
    SIGNATURE_STATUS_UNSIGNED,
    AuditChainVerificationRun,
    AuditIntegrityRecord,
)
from .signer import AuditSigner

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

_INTEGRITY_RETURNING = (
    "integrity_id, audit_log_id, chain_version, sequence_number, "
    "prev_hash, row_hash, canonical_payload_hash, hmac_signature, "
    "signing_key_id, signature_status, integrity_status, created_at"
)

_VERIFICATION_RETURNING = (
    "verification_id, chain_version, status, total_records, verified_records, "
    "failed_records, first_failure_sequence, first_failure_audit_log_id, "
    "failure_reason, started_at, completed_at, metadata"
)


def _row_to_integrity(row: asyncpg.Record) -> AuditIntegrityRecord:
    return AuditIntegrityRecord(
        integrity_id=str(row["integrity_id"]),
        audit_log_id=str(row["audit_log_id"]),
        chain_version=int(row["chain_version"]),
        sequence_number=int(row["sequence_number"]),
        prev_hash=row["prev_hash"],
        row_hash=row["row_hash"],
        canonical_payload_hash=row["canonical_payload_hash"],
        hmac_signature=row["hmac_signature"],
        signing_key_id=row["signing_key_id"],
        signature_status=row["signature_status"],
        integrity_status=row["integrity_status"],
        created_at=row["created_at"],
    )


def _row_to_verification(row: asyncpg.Record) -> AuditChainVerificationRun:
    metadata = row["metadata"] if row["metadata"] is not None else {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (TypeError, ValueError):
            metadata = {}
    return AuditChainVerificationRun(
        verification_id=str(row["verification_id"]),
        chain_version=int(row["chain_version"]),
        status=row["status"],
        total_records=int(row["total_records"] or 0),
        verified_records=int(row["verified_records"] or 0),
        failed_records=int(row["failed_records"] or 0),
        first_failure_sequence=(
            int(row["first_failure_sequence"])
            if row["first_failure_sequence"] is not None
            else None
        ),
        first_failure_audit_log_id=(
            str(row["first_failure_audit_log_id"])
            if row["first_failure_audit_log_id"] is not None
            else None
        ),
        failure_reason=row["failure_reason"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        metadata=metadata or {},
    )


class AuditIntegrityStore:
    """Read+writer for ``audit_integrity_records`` + verification runs."""

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

    async def get_integrity_record(self, audit_log_id: str) -> AuditIntegrityRecord | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {_INTEGRITY_RETURNING} FROM audit_integrity_records "
                "WHERE audit_log_id = $1",
                audit_log_id,
            )
        finally:
            await conn.close()
        return _row_to_integrity(row) if row else None

    async def get_latest_integrity_record(
        self, chain_version: int = CHAIN_VERSION
    ) -> AuditIntegrityRecord | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {_INTEGRITY_RETURNING} FROM audit_integrity_records "
                "WHERE chain_version = $1 "
                "ORDER BY sequence_number DESC LIMIT 1",
                chain_version,
            )
        finally:
            await conn.close()
        return _row_to_integrity(row) if row else None

    async def list_integrity_records(
        self,
        *,
        chain_version: int = CHAIN_VERSION,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditIntegrityRecord]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                f"SELECT {_INTEGRITY_RETURNING} FROM audit_integrity_records "
                "WHERE chain_version = $1 "
                "ORDER BY sequence_number ASC "
                "LIMIT $2 OFFSET $3",
                chain_version,
                max(1, min(int(limit or 100), 1000)),
                max(0, int(offset or 0)),
            )
        finally:
            await conn.close()
        return [_row_to_integrity(r) for r in rows]

    async def count_audit_logs(self) -> int:
        conn = await self._connect()
        try:
            return int(await conn.fetchval("SELECT COUNT(*) FROM audit_logs"))
        finally:
            await conn.close()

    async def count_integrity_records(self, chain_version: int = CHAIN_VERSION) -> int:
        conn = await self._connect()
        try:
            return int(
                await conn.fetchval(
                    "SELECT COUNT(*) FROM audit_integrity_records " "WHERE chain_version = $1",
                    chain_version,
                )
            )
        finally:
            await conn.close()

    async def create_integrity_record_for_audit_log(
        self,
        audit_log_row: dict[str, Any],
        *,
        integrity_status: str = INTEGRITY_STATUS_ACTIVE,
    ) -> AuditIntegrityRecord | None:
        """Append one integrity record for ``audit_log_row``.

        Returns ``None`` when an integrity record already exists for
        the same ``audit_log_id`` (idempotent re-runs are safe).
        """
        audit_log_id = (
            audit_log_row.get("audit_log_id")
            or audit_log_row.get("audit_id")
            or audit_log_row.get("id")
        )
        if not audit_log_id:
            raise ValueError("audit_log_row missing audit_log_id / audit_id / id")

        canonical = build_canonical_payload(audit_log_row)
        canonical_hash = compute_payload_hash(canonical)

        conn = await self._connect()
        try:
            async with conn.transaction():
                # Skip if already recorded.
                existing = await conn.fetchrow(
                    "SELECT 1 FROM audit_integrity_records " "WHERE audit_log_id = $1",
                    audit_log_id,
                )
                if existing:
                    return None
                prev = await conn.fetchrow(
                    "SELECT sequence_number, row_hash "
                    "FROM audit_integrity_records "
                    "WHERE chain_version = $1 "
                    "ORDER BY sequence_number DESC LIMIT 1 "
                    "FOR UPDATE",
                    CHAIN_VERSION,
                )
                if prev is None:
                    sequence_number = 1
                    prev_hash: str | None = None
                else:
                    sequence_number = int(prev["sequence_number"]) + 1
                    prev_hash = prev["row_hash"]
                row_hash = compute_row_hash(
                    chain_version=CHAIN_VERSION,
                    sequence_number=sequence_number,
                    audit_log_id=str(audit_log_id),
                    prev_hash=prev_hash,
                    canonical_payload_hash=canonical_hash,
                )
                signature, sig_status, key_id = self._signer.sign(row_hash)
                row = await conn.fetchrow(
                    "INSERT INTO audit_integrity_records "
                    "(audit_log_id, chain_version, sequence_number, "
                    "prev_hash, row_hash, canonical_payload_hash, "
                    "hmac_signature, signing_key_id, signature_status, "
                    "integrity_status) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) "
                    f"RETURNING {_INTEGRITY_RETURNING}",
                    audit_log_id,
                    CHAIN_VERSION,
                    sequence_number,
                    prev_hash,
                    row_hash,
                    canonical_hash,
                    signature,
                    key_id,
                    sig_status,
                    integrity_status,
                )
        finally:
            await conn.close()
        return _row_to_integrity(row) if row else None

    async def backfill_missing_integrity_records(self) -> dict[str, int]:
        """Add integrity records for every audit_logs row that lacks one.

        Returns counts: ``{audit_logs, integrity_records_before,
        created, integrity_records_after, signed, unsigned, not_configured}``.
        """
        conn = await self._connect()
        try:
            audit_count = int(await conn.fetchval("SELECT COUNT(*) FROM audit_logs"))
            before = int(
                await conn.fetchval(
                    "SELECT COUNT(*) FROM audit_integrity_records " "WHERE chain_version = $1",
                    CHAIN_VERSION,
                )
            )
            missing = await conn.fetch(
                "SELECT al.id, al.task_id, al.agent, al.decision_type, "
                "al.summary, al.result, al.artifact_refs, al.created_at "
                "FROM audit_logs al "
                "LEFT JOIN audit_integrity_records r "
                "  ON r.audit_log_id = al.id "
                "  AND r.chain_version = $1 "
                "WHERE r.audit_log_id IS NULL "
                "ORDER BY al.created_at ASC, al.id ASC",
                CHAIN_VERSION,
            )
        finally:
            await conn.close()

        created = 0
        signed = 0
        unsigned = 0
        not_configured = 0
        for row in missing:
            payload = {
                "audit_log_id": str(row["id"]),
                "task_id": row["task_id"],
                "agent": row["agent"],
                "decision_type": row["decision_type"],
                "summary": row["summary"],
                "result": row["result"],
                "artifact_refs": row["artifact_refs"],
                "created_at": row["created_at"],
            }
            result = await self.create_integrity_record_for_audit_log(
                payload, integrity_status=INTEGRITY_STATUS_BACKFILLED
            )
            if result is None:
                # Race / already present -- skip silently.
                continue
            created += 1
            if result.signature_status == SIGNATURE_STATUS_NOT_CONFIGURED:
                not_configured += 1
            elif result.signature_status == SIGNATURE_STATUS_UNSIGNED:
                unsigned += 1
            else:
                signed += 1

        after = before + created
        return {
            "audit_logs": audit_count,
            "integrity_records_before": before,
            "created": created,
            "integrity_records_after": after,
            "signed": signed,
            "unsigned": unsigned,
            "not_configured": not_configured,
        }

    async def record_verification_run(
        self,
        *,
        run: AuditChainVerificationRun,
    ) -> AuditChainVerificationRun:
        meta_json = json.dumps(run.metadata or {})
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "INSERT INTO audit_chain_verification_runs "
                "(chain_version, status, total_records, verified_records, "
                "failed_records, first_failure_sequence, "
                "first_failure_audit_log_id, failure_reason, "
                "started_at, completed_at, metadata) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11::jsonb) "
                f"RETURNING {_VERIFICATION_RETURNING}",
                run.chain_version,
                run.status,
                run.total_records,
                run.verified_records,
                run.failed_records,
                run.first_failure_sequence,
                run.first_failure_audit_log_id,
                run.failure_reason,
                run.started_at,
                run.completed_at,
                meta_json,
            )
        finally:
            await conn.close()
        return _row_to_verification(row)

    async def get_latest_verification_run(
        self, chain_version: int = CHAIN_VERSION
    ) -> AuditChainVerificationRun | None:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                f"SELECT {_VERIFICATION_RETURNING} "
                "FROM audit_chain_verification_runs "
                "WHERE chain_version = $1 "
                "ORDER BY started_at DESC LIMIT 1",
                chain_version,
            )
        finally:
            await conn.close()
        return _row_to_verification(row) if row else None

    async def count_failed_verifications(self, chain_version: int = CHAIN_VERSION) -> int:
        conn = await self._connect()
        try:
            return int(
                await conn.fetchval(
                    "SELECT COUNT(*) FROM audit_chain_verification_runs "
                    "WHERE chain_version = $1 AND status IN ('failed','error')",
                    chain_version,
                )
            )
        finally:
            await conn.close()


__all__ = ["AuditIntegrityStore"]
