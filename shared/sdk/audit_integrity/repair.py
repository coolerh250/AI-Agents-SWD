"""Stage 42 -- controlled audit chain integrity repair.

This module repairs ``audit_integrity_records`` ONLY. It never modifies,
deletes, or reorders ``audit_logs``. A repair recomputes the integrity
hashes so the chain re-binds to the current (authoritative) audit_logs
content, cascading the ``prev_hash`` linkage from the first failed
sequence to the chain tail.

Hard safety properties:

* Dry-run by default. ``apply()`` makes no DB change unless ``approved``
  is True AND ``dry_run`` is False.
* Only runs when the forensic classification marks the chain
  ``repair_allowed`` and the root cause is in ``REPAIRABLE_ROOT_CAUSES``.
* Transaction-scoped advisory lock (shared with the writer) so no
  concurrent integrity write races the repair.
* Re-verifies the chain on the SAME connection before COMMIT; any
  remaining mismatch triggers ROLLBACK (no partial repair is persisted).
* Records before/after hashes for the originally-failed records.

It never reads or writes a key value.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import asyncpg

from .canonical import build_canonical_payload
from .forensics import (
    REPAIRABLE_ROOT_CAUSES,
    FailedRecordAnalysis,
)
from .hasher import compute_payload_hash, compute_row_hash
from .models import CHAIN_VERSION, INTEGRITY_STATUS_ACTIVE
from .store import ADVISORY_LOCK_NAME

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

REPAIR_STATUS_DRY_RUN = "dry_run"
REPAIR_STATUS_SKIPPED_UNSAFE = "skipped_unsafe"
REPAIR_STATUS_APPROVAL_REQUIRED = "approval_required"
REPAIR_STATUS_COMPLETED = "completed"
REPAIR_STATUS_FAILED = "failed"
REPAIR_STATUS_VERIFIED = "verified"

_MAX_HASH_SAMPLE = 25


@dataclass
class RepairPlan:
    """A deterministic, inspectable plan. Building it touches no DB rows."""

    root_cause: str
    repair_allowed: bool
    repair_risk: str
    first_failed_sequence: int | None
    affected_sequences: list[int] = field(default_factory=list)
    reason: str = ""

    @property
    def changed_records_count(self) -> int:
        return len(self.affected_sequences)

    def to_dict(self) -> dict[str, Any]:
        seqs = self.affected_sequences
        sample = seqs[:_MAX_HASH_SAMPLE]
        return {
            "root_cause": self.root_cause,
            "repair_allowed": self.repair_allowed,
            "repair_risk": self.repair_risk,
            "first_failed_sequence": self.first_failed_sequence,
            "affected_sequences_count": len(seqs),
            "affected_sequences_sample": sample,
            "affected_sequence_range": [seqs[0], seqs[-1]] if seqs else None,
            "reason": self.reason,
        }


def plan_repair(
    *,
    failed: list[FailedRecordAnalysis],
    root_cause: str,
    repair_allowed: bool,
    repair_risk: str,
    chain_tail_sequence: int | None,
    reason: str = "",
) -> RepairPlan:
    """Build a repair plan from forensic findings.

    The affected set is every sequence from the first failed record to the
    chain tail (a canonical/row hash change cascades through ``prev_hash``).
    """
    if not failed or chain_tail_sequence is None:
        return RepairPlan(
            root_cause=root_cause,
            repair_allowed=False,
            repair_risk=repair_risk,
            first_failed_sequence=None,
            affected_sequences=[],
            reason=reason or "no failed records",
        )
    first = min(r.sequence_number for r in failed)
    affected = list(range(first, int(chain_tail_sequence) + 1))
    return RepairPlan(
        root_cause=root_cause,
        repair_allowed=repair_allowed and root_cause in REPAIRABLE_ROOT_CAUSES,
        repair_risk=repair_risk,
        first_failed_sequence=first,
        affected_sequences=affected,
        reason=reason,
    )


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditChainRepairer:
    """Applies a :class:`RepairPlan` to ``audit_integrity_records`` only."""

    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.dsn, timeout=15)

    async def chain_tail_sequence(self, chain_version: int = CHAIN_VERSION) -> int | None:
        conn = await self._connect()
        try:
            val = await conn.fetchval(
                "SELECT MAX(sequence_number) FROM audit_integrity_records "
                "WHERE chain_version = $1",
                chain_version,
            )
        finally:
            await conn.close()
        return int(val) if val is not None else None

    async def apply(
        self,
        plan: RepairPlan,
        *,
        approved: bool,
        dry_run: bool = True,
        chain_version: int = CHAIN_VERSION,
    ) -> dict[str, Any]:
        """Apply (or simulate) a repair.

        Returns a report dict. Makes NO DB change unless
        ``approved and not dry_run`` and ``plan.repair_allowed``.
        """
        report: dict[str, Any] = {
            "started_at": _iso_now(),
            "completed_at": None,
            "dry_run": dry_run,
            "approved": approved,
            "root_cause": plan.root_cause,
            "repair_allowed": plan.repair_allowed,
            "repair_risk": plan.repair_risk,
            "first_failed_sequence": plan.first_failed_sequence,
            "affected_sequences_count": plan.changed_records_count,
            "changed_records_count": 0,
            "audit_logs_modified": False,
            "audit_integrity_records_modified": False,
            "before_hash_summary": [],
            "after_hash_summary": [],
            "verification_after_repair": None,
            "production_executed": False,
            "status": REPAIR_STATUS_DRY_RUN,
            "warnings": [],
        }

        if not plan.repair_allowed:
            report["status"] = REPAIR_STATUS_SKIPPED_UNSAFE
            report["warnings"].append(f"repair not allowed: {plan.reason}")
            report["completed_at"] = _iso_now()
            return report

        if not approved:
            report["status"] = REPAIR_STATUS_APPROVAL_REQUIRED
            report["warnings"].append(
                "AUDIT_CHAIN_REPAIR_APPROVED not set -- repair gated; no DB change"
            )
            report["completed_at"] = _iso_now()
            return report

        if dry_run:
            # Compute the would-be before/after for the originally-failed
            # records without writing anything.
            report["before_hash_summary"], report["after_hash_summary"] = await self._preview(
                plan, chain_version
            )
            report["status"] = REPAIR_STATUS_DRY_RUN
            report["completed_at"] = _iso_now()
            return report

        # ---- approved, non-dry-run: apply transactionally --------------
        conn = await self._connect()
        try:
            async with conn.transaction():
                await conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtext($1)::bigint)",
                    ADVISORY_LOCK_NAME,
                )
                before, after, changed = await self._recompute_and_update(conn, plan, chain_version)
                report["before_hash_summary"] = before
                report["after_hash_summary"] = after
                report["changed_records_count"] = changed
                report["audit_integrity_records_modified"] = changed > 0

                ok, fail_seq, reason = await self._verify_in_txn(conn, chain_version)
                report["verification_after_repair"] = {
                    "passed": ok,
                    "first_failure_sequence": fail_seq,
                    "failure_reason": reason,
                }
                if not ok:
                    report["status"] = REPAIR_STATUS_FAILED
                    report["warnings"].append(
                        f"post-repair verify failed at seq={fail_seq} ({reason}); rolled back"
                    )
                    raise _RollbackRepair()
                report["status"] = REPAIR_STATUS_COMPLETED
        except _RollbackRepair:
            report["audit_integrity_records_modified"] = False
            report["changed_records_count"] = 0
        finally:
            await conn.close()
        report["completed_at"] = _iso_now()
        return report

    async def _fetch_rows(
        self, conn: asyncpg.Connection, start_seq: int, chain_version: int
    ) -> list[asyncpg.Record]:
        return await conn.fetch(
            "SELECT r.integrity_id, r.sequence_number, r.audit_log_id, "
            "r.prev_hash, r.row_hash, r.canonical_payload_hash, "
            "al.task_id, al.agent, al.decision_type, al.summary, "
            "al.result, al.artifact_refs, al.created_at "
            "FROM audit_integrity_records r "
            "JOIN audit_logs al ON al.id = r.audit_log_id "
            "WHERE r.chain_version = $1 AND r.sequence_number >= $2 "
            "ORDER BY r.sequence_number ASC",
            chain_version,
            start_seq,
        )

    def _recompute_chain(
        self, rows: list[asyncpg.Record], chain_version: int, start_prev_hash: str | None
    ) -> list[dict[str, Any]]:
        """Pure: produce the new (canonical_hash, row_hash, prev_hash) per row."""
        out: list[dict[str, Any]] = []
        prev_hash = start_prev_hash
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
            new_canonical = compute_payload_hash(canonical)
            new_row = compute_row_hash(
                chain_version=chain_version,
                sequence_number=seq,
                audit_log_id=audit_log_id,
                prev_hash=prev_hash,
                canonical_payload_hash=new_canonical,
            )
            out.append(
                {
                    "integrity_id": row["integrity_id"],
                    "sequence_number": seq,
                    "audit_log_id": audit_log_id,
                    "stored_canonical": row["canonical_payload_hash"],
                    "stored_row": row["row_hash"],
                    "stored_prev": row["prev_hash"],
                    "new_canonical": new_canonical,
                    "new_row": new_row,
                    "new_prev": prev_hash,
                }
            )
            prev_hash = new_row
        return out

    async def _start_prev_hash(
        self, conn: asyncpg.Connection, start_seq: int, chain_version: int
    ) -> str | None:
        if start_seq <= 1:
            return None
        return await conn.fetchval(
            "SELECT row_hash FROM audit_integrity_records "
            "WHERE chain_version = $1 AND sequence_number = $2",
            chain_version,
            start_seq - 1,
        )

    async def _preview(self, plan: RepairPlan, chain_version: int) -> tuple[list[dict], list[dict]]:
        start = plan.first_failed_sequence or 1
        conn = await self._connect()
        try:
            start_prev = await self._start_prev_hash(conn, start, chain_version)
            rows = await self._fetch_rows(conn, start, chain_version)
        finally:
            await conn.close()
        recomputed = self._recompute_chain(rows, chain_version, start_prev)
        return self._hash_summaries(recomputed)

    def _hash_summaries(self, recomputed: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
        changed = [
            r
            for r in recomputed
            if r["new_canonical"] != r["stored_canonical"]
            or r["new_row"] != r["stored_row"]
            or r["new_prev"] != r["stored_prev"]
        ]
        before = [
            {
                "sequence_number": r["sequence_number"],
                "canonical_payload_hash": r["stored_canonical"],
                "row_hash": r["stored_row"],
                "prev_hash": r["stored_prev"],
            }
            for r in changed[:_MAX_HASH_SAMPLE]
        ]
        after = [
            {
                "sequence_number": r["sequence_number"],
                "canonical_payload_hash": r["new_canonical"],
                "row_hash": r["new_row"],
                "prev_hash": r["new_prev"],
            }
            for r in changed[:_MAX_HASH_SAMPLE]
        ]
        return before, after

    async def _recompute_and_update(
        self, conn: asyncpg.Connection, plan: RepairPlan, chain_version: int
    ) -> tuple[list[dict], list[dict], int]:
        start = plan.first_failed_sequence or 1
        start_prev = await self._start_prev_hash(conn, start, chain_version)
        rows = await self._fetch_rows(conn, start, chain_version)
        recomputed = self._recompute_chain(rows, chain_version, start_prev)
        before, after = self._hash_summaries(recomputed)
        changed = 0
        for r in recomputed:
            if (
                r["new_canonical"] == r["stored_canonical"]
                and r["new_row"] == r["stored_row"]
                and r["new_prev"] == r["stored_prev"]
            ):
                continue
            await conn.execute(
                "UPDATE audit_integrity_records "
                "SET canonical_payload_hash = $1, row_hash = $2, prev_hash = $3, "
                "    integrity_status = $4 "
                "WHERE integrity_id = $5",
                r["new_canonical"],
                r["new_row"],
                r["new_prev"],
                INTEGRITY_STATUS_ACTIVE,
                r["integrity_id"],
            )
            changed += 1
        return before, after, changed

    async def _verify_in_txn(
        self, conn: asyncpg.Connection, chain_version: int
    ) -> tuple[bool, int | None, str | None]:
        """Re-walk the chain on the SAME connection (sees pending writes)."""
        rows = await conn.fetch(
            "SELECT r.sequence_number, r.audit_log_id, r.prev_hash, "
            "r.row_hash, r.canonical_payload_hash, "
            "al.task_id, al.agent, al.decision_type, al.summary, "
            "al.result, al.artifact_refs, al.created_at "
            "FROM audit_integrity_records r "
            "JOIN audit_logs al ON al.id = r.audit_log_id "
            "WHERE r.chain_version = $1 "
            "ORDER BY r.sequence_number ASC",
            chain_version,
        )
        prev_seq = 0
        prev_row_hash: str | None = None
        for row in rows:
            seq = int(row["sequence_number"])
            audit_log_id = str(row["audit_log_id"])
            if seq != prev_seq + 1:
                return False, seq, "sequence_gap"
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
            rec_canonical = compute_payload_hash(canonical)
            if rec_canonical != row["canonical_payload_hash"]:
                return False, seq, "canonical_payload_hash_mismatch"
            rec_row = compute_row_hash(
                chain_version=chain_version,
                sequence_number=seq,
                audit_log_id=audit_log_id,
                prev_hash=row["prev_hash"],
                canonical_payload_hash=rec_canonical,
            )
            if rec_row != row["row_hash"]:
                return False, seq, "row_hash_mismatch"
            if seq > 1 and row["prev_hash"] != prev_row_hash:
                return False, seq, "prev_hash_mismatch"
            prev_seq = seq
            prev_row_hash = row["row_hash"]
        return True, None, None


class _RollbackRepair(Exception):
    """Internal sentinel to force a transaction rollback after a failed verify."""


__all__ = [
    "REPAIR_STATUS_DRY_RUN",
    "REPAIR_STATUS_SKIPPED_UNSAFE",
    "REPAIR_STATUS_APPROVAL_REQUIRED",
    "REPAIR_STATUS_COMPLETED",
    "REPAIR_STATUS_FAILED",
    "REPAIR_STATUS_VERIFIED",
    "RepairPlan",
    "AuditChainRepairer",
    "plan_repair",
]
