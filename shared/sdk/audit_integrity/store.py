"""asyncpg-backed store for audit_integrity_records + verification runs.

Stage 39 hardens the writer:

* the sequence-assign + insert block is now wrapped in a Postgres
  transaction-scoped advisory lock (``pg_advisory_xact_lock``) so two
  concurrent writers cannot race on ``latest_sequence + 1``. The lock
  is shared between the stream path (audit-worker), the direct POST
  path (audit-service), and the backfill script -- they all converge
  on this method.
* a unique-constraint conflict on the chain sequence triggers a small
  retry loop (one advisory-lock re-acquisition) so a transient race
  doesn't surface as a 500.
* ``create_integrity_record_in_txn`` exposes the same logic to a
  caller that already holds a transaction (audit-service uses it to
  insert audit_logs + integrity in one atomic transaction).
* ``upsert_keyring_metadata`` records observed key_ids without ever
  touching the key value.

Every method opens a short-lived connection -- low-frequency consumer.
"""

from __future__ import annotations

import json
import os
from typing import Any, Iterable

import asyncpg

from .canonical import build_canonical_payload
from .hasher import compute_payload_hash, compute_row_hash
from .keyring import (
    KEY_SOURCE_UNKNOWN,
    KeyringSnapshot,
    keyring_metadata_rows,
)
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

# ``hashtext('audit_integrity_chain_v1')`` is stable across processes.
# We resolve it from Postgres at lock time to keep the constant out of
# the codebase (and to make it easy to extend per chain_version later).
ADVISORY_LOCK_NAME = "audit_integrity_chain_v1"
MAX_SEQUENCE_RETRIES = 5

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


async def create_integrity_record_in_txn(
    conn: asyncpg.Connection,
    *,
    audit_log_row: dict[str, Any],
    signer: AuditSigner,
    integrity_status: str = INTEGRITY_STATUS_ACTIVE,
) -> AuditIntegrityRecord | None:
    """Insert one integrity record inside an existing transaction.

    The caller MUST already be inside ``async with conn.transaction()``.
    The function acquires ``pg_advisory_xact_lock`` (released on
    commit/rollback) and then performs the sequence-assign + insert.

    Returns ``None`` when an integrity record already exists for the
    same ``audit_log_id`` (idempotent re-runs are safe).
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

    # Acquire the chain advisory lock for this transaction. Released on
    # COMMIT/ROLLBACK by Postgres.
    await conn.execute("SELECT pg_advisory_xact_lock(hashtext($1)::bigint)", ADVISORY_LOCK_NAME)

    existing = await conn.fetchrow(
        "SELECT 1 FROM audit_integrity_records WHERE audit_log_id = $1",
        audit_log_id,
    )
    if existing:
        return None

    prev = await conn.fetchrow(
        "SELECT sequence_number, row_hash "
        "FROM audit_integrity_records "
        "WHERE chain_version = $1 "
        "ORDER BY sequence_number DESC LIMIT 1",
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
    signature, sig_status, key_id = signer.sign(row_hash)
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
    return _row_to_integrity(row) if row else None


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

    async def count_missing_integrity_records(self, chain_version: int = CHAIN_VERSION) -> int:
        conn = await self._connect()
        try:
            return int(
                await conn.fetchval(
                    "SELECT COUNT(*) FROM audit_logs al "
                    "LEFT JOIN audit_integrity_records r "
                    "  ON r.audit_log_id = al.id "
                    "  AND r.chain_version = $1 "
                    "WHERE r.audit_log_id IS NULL",
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
        Retries once on a unique-constraint conflict (race on
        ``sequence_number``).
        """
        last_exc: Exception | None = None
        for _ in range(MAX_SEQUENCE_RETRIES):
            conn = await self._connect()
            try:
                async with conn.transaction():
                    return await create_integrity_record_in_txn(
                        conn,
                        audit_log_row=audit_log_row,
                        signer=self._signer,
                        integrity_status=integrity_status,
                    )
            except asyncpg.UniqueViolationError as exc:
                last_exc = exc
                continue
            finally:
                await conn.close()
        if last_exc is not None:
            raise last_exc
        return None

    async def backfill_missing_integrity_records(self) -> dict[str, int]:
        """Add integrity records for every audit_logs row that lacks one.

        Returns counts: ``{audit_logs, integrity_records_before,
        created, integrity_records_after, signed, unsigned, not_configured,
        missing_before, missing_after}``.
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
                continue
            created += 1
            if result.signature_status == SIGNATURE_STATUS_NOT_CONFIGURED:
                not_configured += 1
            elif result.signature_status == SIGNATURE_STATUS_UNSIGNED:
                unsigned += 1
            else:
                signed += 1

        after = before + created
        missing_before = max(0, audit_count - before)
        missing_after = max(0, audit_count - after)
        return {
            "audit_logs": audit_count,
            "integrity_records_before": before,
            "created": created,
            "integrity_records_after": after,
            "missing_before": missing_before,
            "missing_after": missing_after,
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

    # ------------------------------------------------------------------
    # Stage 39 -- keyring metadata
    # ------------------------------------------------------------------
    async def upsert_keyring_metadata(
        self,
        snapshot: KeyringSnapshot,
    ) -> dict[str, int]:
        """Record which key_ids we've seen. Never writes the key value."""
        rows = keyring_metadata_rows(snapshot)
        if not rows:
            return {"upserted": 0}
        upserted = 0
        conn = await self._connect()
        try:
            async with conn.transaction():
                # Demote previously-active rows that are no longer the
                # active key, so only one row stays at ``active``.
                active_id = snapshot.active_key_id
                if active_id:
                    await conn.execute(
                        "UPDATE audit_hmac_key_metadata "
                        "SET key_status = 'inactive', "
                        "    active_until = COALESCE(active_until, now()), "
                        "    updated_at = now() "
                        "WHERE key_status = 'active' AND key_id <> $1",
                        active_id,
                    )
                for row in rows:
                    await conn.execute(
                        "INSERT INTO audit_hmac_key_metadata "
                        "(key_id, key_status, source) "
                        "VALUES ($1, $2, $3) "
                        "ON CONFLICT (key_id) DO UPDATE SET "
                        "  key_status = EXCLUDED.key_status, "
                        "  source = EXCLUDED.source, "
                        "  last_seen_at = now(), "
                        "  active_from = CASE "
                        "      WHEN EXCLUDED.key_status = 'active' "
                        "        AND audit_hmac_key_metadata.key_status <> 'active' "
                        "      THEN now() "
                        "      ELSE audit_hmac_key_metadata.active_from END, "
                        "  active_until = CASE "
                        "      WHEN EXCLUDED.key_status = 'active' THEN NULL "
                        "      WHEN audit_hmac_key_metadata.key_status = 'active' "
                        "        AND EXCLUDED.key_status <> 'active' "
                        "      THEN now() "
                        "      ELSE audit_hmac_key_metadata.active_until END, "
                        "  updated_at = now()",
                        row["key_id"],
                        row["key_status"],
                        row["source"],
                    )
                    upserted += 1
        finally:
            await conn.close()
        return {"upserted": upserted}

    async def list_key_metadata(self) -> list[dict[str, Any]]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT key_id, key_status, source, first_seen_at, "
                "last_seen_at, active_from, active_until, created_at, "
                "updated_at, metadata "
                "FROM audit_hmac_key_metadata "
                "ORDER BY (key_status = 'active') DESC, last_seen_at DESC"
            )
        finally:
            await conn.close()
        result: list[dict[str, Any]] = []
        for row in rows:
            meta = row["metadata"]
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except (TypeError, ValueError):
                    meta = {}
            result.append(
                {
                    "key_id": row["key_id"],
                    "key_status": row["key_status"],
                    "source": row["source"] or KEY_SOURCE_UNKNOWN,
                    "first_seen_at": (
                        row["first_seen_at"].isoformat() if row["first_seen_at"] else None
                    ),
                    "last_seen_at": (
                        row["last_seen_at"].isoformat() if row["last_seen_at"] else None
                    ),
                    "active_from": row["active_from"].isoformat() if row["active_from"] else None,
                    "active_until": (
                        row["active_until"].isoformat() if row["active_until"] else None
                    ),
                    "metadata": meta or {},
                }
            )
        return result

    async def mark_key_status(self, key_id: str, key_status: str) -> bool:
        conn = await self._connect()
        try:
            row = await conn.fetchrow(
                "UPDATE audit_hmac_key_metadata "
                "SET key_status = $2, updated_at = now() "
                "WHERE key_id = $1 RETURNING key_id",
                key_id,
                key_status,
            )
        finally:
            await conn.close()
        return row is not None

    async def count_signed_records_by_key(self) -> dict[str, int]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT signing_key_id, COUNT(*) AS n "
                "FROM audit_integrity_records "
                "WHERE signature_status = 'signed' "
                "GROUP BY signing_key_id"
            )
        finally:
            await conn.close()
        return {str(row["signing_key_id"] or "unsigned"): int(row["n"]) for row in rows}


def filter_safe_keyring_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop anything that smells like a key value. Defensive belt-and-braces."""
    safe_keys = {
        "key_id",
        "key_status",
        "source",
        "first_seen_at",
        "last_seen_at",
        "active_from",
        "active_until",
        "metadata",
    }
    result: list[dict[str, Any]] = []
    for row in rows:
        result.append({k: v for k, v in row.items() if k in safe_keys})
    return result


__all__ = [
    "AuditIntegrityStore",
    "ADVISORY_LOCK_NAME",
    "create_integrity_record_in_txn",
    "filter_safe_keyring_rows",
]
