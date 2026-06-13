"""Stage 43 -- controlled audit_log restore exception for test-tamper residue.

This is the forensically-cleaner alternative to the Stage 42 integrity-record
repair. Instead of re-binding the integrity chain to a contaminated payload
(and cascading prev_hash), it restores ONE test-tampered ``audit_logs.summary``
so the row re-matches its already-correct integrity record:

* modifies ``audit_logs.summary`` for exactly one record,
* modifies **zero** ``audit_integrity_records`` (no cascade),
* only removes a forensically-proven tamper marker,
* only when the forensic report classified the row
  ``test_tamper_not_restored`` with ``production_executed=false``.

Dry-run by default. A DB change requires both ``repair_allowed`` (proven by
the precheck) AND an explicit operator approval flag. The restore action
itself is recorded as a new audit row whose integrity record is appended to
the tail of the chain (this is expected; the latest sequence advances).

Never reads or emits a key value. Free text is hashed, not stored raw.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import asyncpg

from .canonical import build_canonical_payload
from .forensics import (
    KNOWN_TAMPER_MARKERS,
    REPAIR_RISK_LOW,
    ROOT_CAUSE_TEST_TAMPER_NOT_RESTORED,
)
from .hasher import compute_payload_hash
from .models import CHAIN_VERSION
from .store import ADVISORY_LOCK_NAME, create_integrity_record_in_txn
from .audit_events import DECISION_AUDIT_LOG_RESTORE_COMPLETED

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

RESTORE_STATUS_DRY_RUN = "dry_run"
RESTORE_STATUS_APPROVAL_REQUIRED = "approval_required"
RESTORE_STATUS_REJECTED_UNSAFE = "rejected_unsafe"
RESTORE_STATUS_COMPLETED = "completed"
RESTORE_STATUS_FAILED = "failed"

RESTORE_TYPE_TEST_TAMPER_RESIDUE = "test_tamper_residue"


def _sha256(text: str | None) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _strip_marker(summary: str | None) -> tuple[str | None, str | None]:
    if not summary:
        return None, None
    for marker in KNOWN_TAMPER_MARKERS:
        if summary.endswith(marker):
            return summary[: -len(marker)], marker
    return None, None


@dataclass
class RestorePrecheck:
    """Read-only validation result. Carries hashes, never raw secrets."""

    ok: bool = False
    reason: str = ""
    affected_audit_log_id: str | None = None
    affected_sequence_number: int | None = None
    root_cause: str | None = None
    restore_type: str = RESTORE_TYPE_TEST_TAMPER_RESIDUE
    production_executed: bool | None = None
    before_contains_tamper_marker: bool = False
    after_contains_tamper_marker: bool = False
    before_summary_hash: str | None = None
    after_summary_hash: str | None = None
    stored_canonical_payload_hash: str | None = None
    recomputed_after_canonical_payload_hash: str | None = None
    hash_match_after: bool = False
    missing_integrity_records: int | None = None
    prev_chain_linkage_intact: bool = False
    signature_blocking: bool = False
    # internal-only (not serialised): the restored summary to write.
    _restored_summary: str | None = field(default=None, repr=False)
    _current_summary: str | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reason": self.reason,
            "affected_audit_log_id": self.affected_audit_log_id,
            "affected_sequence_number": self.affected_sequence_number,
            "root_cause": self.root_cause,
            "restore_type": self.restore_type,
            "production_executed": self.production_executed,
            "before_contains_tamper_marker": self.before_contains_tamper_marker,
            "after_contains_tamper_marker": self.after_contains_tamper_marker,
            "before_summary_hash": self.before_summary_hash,
            "after_summary_hash": self.after_summary_hash,
            "stored_canonical_payload_hash": self.stored_canonical_payload_hash,
            "recomputed_after_canonical_payload_hash": (
                self.recomputed_after_canonical_payload_hash
            ),
            "hash_match_after": self.hash_match_after,
            "missing_integrity_records": self.missing_integrity_records,
            "prev_chain_linkage_intact": self.prev_chain_linkage_intact,
            "signature_blocking": self.signature_blocking,
        }


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditLogRestorer:
    """Restores a single test-tampered audit_logs.summary. audit_logs only."""

    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.dsn, timeout=15)

    async def precheck(
        self,
        forensic_report: dict[str, Any],
        *,
        audit_log_id: str | None = None,
        sequence_number: int | None = None,
        chain_version: int = CHAIN_VERSION,
    ) -> RestorePrecheck:
        """Validate every restore precondition. Read-only."""
        pc = RestorePrecheck()

        # ---- forensic report level gates -------------------------------
        root = forensic_report.get("root_cause_classification")
        pc.root_cause = root
        if root != ROOT_CAUSE_TEST_TAMPER_NOT_RESTORED:
            pc.reason = f"root_cause={root!r} != test_tamper_not_restored"
            return pc
        if not forensic_report.get("repair_allowed"):
            pc.reason = "forensic repair_allowed is not true"
            return pc
        if forensic_report.get("repair_risk") != REPAIR_RISK_LOW:
            pc.reason = f"repair_risk={forensic_report.get('repair_risk')!r} != low"
            return pc
        failed_records = forensic_report.get("failed_records") or []
        if (forensic_report.get("failed_records_count") or len(failed_records)) != 1:
            pc.reason = "forensic report does not describe exactly one failed record"
            return pc

        report_id = forensic_report.get("first_failed_sequence")
        report_audit_id = None
        if failed_records:
            report_audit_id = failed_records[0].get("audit_log_id")
        affected_seq = sequence_number or report_id
        affected_id = audit_log_id or report_audit_id
        if affected_seq is None or affected_id is None:
            pc.reason = "could not resolve affected sequence / audit_log_id"
            return pc
        if report_id is not None and affected_seq != report_id:
            pc.reason = f"sequence {affected_seq} != forensic first_failed_sequence {report_id}"
            return pc
        if report_audit_id is not None and affected_id != report_audit_id:
            pc.reason = "audit_log_id does not match forensic report"
            return pc
        pc.affected_sequence_number = int(affected_seq)
        pc.affected_audit_log_id = str(affected_id)

        # ---- DB level gates (read-only) --------------------------------
        conn = await self._connect()
        try:
            rec = await conn.fetchrow(
                "SELECT r.sequence_number, r.audit_log_id, r.prev_hash, r.row_hash, "
                "r.canonical_payload_hash, r.signature_status, "
                "al.task_id, al.agent, al.decision_type, al.summary, al.result, "
                "al.artifact_refs, al.created_at "
                "FROM audit_integrity_records r JOIN audit_logs al ON al.id = r.audit_log_id "
                "WHERE r.chain_version = $1 AND r.sequence_number = $2",
                chain_version,
                pc.affected_sequence_number,
            )
            if rec is None:
                pc.reason = f"no integrity record at sequence {pc.affected_sequence_number}"
                return pc
            if str(rec["audit_log_id"]) != pc.affected_audit_log_id:
                pc.reason = "integrity record audit_log_id mismatch"
                return pc

            pc.missing_integrity_records = int(
                await conn.fetchval(
                    "SELECT COUNT(*) FROM audit_logs al "
                    "LEFT JOIN audit_integrity_records r ON r.audit_log_id = al.id "
                    "WHERE r.audit_log_id IS NULL"
                )
            )
            prev_row_hash = await conn.fetchval(
                "SELECT row_hash FROM audit_integrity_records "
                "WHERE chain_version = $1 AND sequence_number = $2",
                chain_version,
                pc.affected_sequence_number - 1,
            )
            next_prev_hash = await conn.fetchval(
                "SELECT prev_hash FROM audit_integrity_records "
                "WHERE chain_version = $1 AND sequence_number = $2",
                chain_version,
                pc.affected_sequence_number + 1,
            )
        finally:
            await conn.close()

        # production_executed must be false.
        pc.production_executed = _production_executed(rec["artifact_refs"])
        if pc.production_executed is not False:
            pc.reason = f"production_executed={pc.production_executed!r} (must be false)"
            return pc

        # signature must not be the blocking failure.
        pc.signature_blocking = rec["signature_status"] == "signed"
        if pc.signature_blocking:
            pc.reason = "signed row -- signature issue must be handled separately"
            return pc

        # missing integrity records must be zero.
        if pc.missing_integrity_records != 0:
            pc.reason = f"missing_integrity_records={pc.missing_integrity_records} (must be 0)"
            return pc

        # prev/next chain linkage must be intact (stored hashes).
        prev_ok = (pc.affected_sequence_number == 1) or (rec["prev_hash"] == prev_row_hash)
        next_ok = (next_prev_hash is None) or (next_prev_hash == rec["row_hash"])
        pc.prev_chain_linkage_intact = bool(prev_ok and next_ok)
        if not pc.prev_chain_linkage_intact:
            pc.reason = "prev/next chain linkage not intact -- not a simple residue case"
            return pc

        # current summary must carry a known tamper marker.
        current_summary = rec["summary"]
        restored_summary, marker = _strip_marker(current_summary)
        pc.before_contains_tamper_marker = marker is not None
        if marker is None:
            pc.reason = "current summary does not contain a known tamper marker"
            return pc

        # restored summary must reproduce the stored canonical hash exactly.
        restored_row = {
            "audit_log_id": pc.affected_audit_log_id,
            "task_id": rec["task_id"],
            "agent": rec["agent"],
            "decision_type": rec["decision_type"],
            "summary": restored_summary,
            "result": rec["result"],
            "artifact_refs": rec["artifact_refs"],
            "created_at": rec["created_at"],
        }
        recomputed_after = compute_payload_hash(build_canonical_payload(restored_row))
        pc.stored_canonical_payload_hash = rec["canonical_payload_hash"]
        pc.recomputed_after_canonical_payload_hash = recomputed_after
        pc.hash_match_after = recomputed_after == rec["canonical_payload_hash"]
        pc.before_summary_hash = _sha256(current_summary)
        pc.after_summary_hash = _sha256(restored_summary)
        _, after_marker = _strip_marker(restored_summary)
        pc.after_contains_tamper_marker = after_marker is not None
        pc._restored_summary = restored_summary
        pc._current_summary = current_summary

        if not pc.hash_match_after:
            pc.reason = "restored summary does not reproduce the stored canonical hash"
            return pc

        pc.ok = True
        pc.reason = "all preconditions satisfied"
        return pc

    async def apply(
        self,
        precheck: RestorePrecheck,
        *,
        approved: bool,
        dry_run: bool = True,
        chain_version: int = CHAIN_VERSION,
    ) -> dict[str, Any]:
        """Apply (or simulate) the restore. audit_logs.summary only."""
        report: dict[str, Any] = {
            "created_at": _iso_now(),
            "dry_run": dry_run,
            "approved": approved,
            "affected_audit_log_id": precheck.affected_audit_log_id,
            "affected_sequence_number": precheck.affected_sequence_number,
            "root_cause": precheck.root_cause,
            "restore_type": precheck.restore_type,
            "before_summary_hash": precheck.before_summary_hash,
            "after_summary_hash": precheck.after_summary_hash,
            "before_contains_tamper_marker": precheck.before_contains_tamper_marker,
            "after_contains_tamper_marker": precheck.after_contains_tamper_marker,
            "stored_canonical_payload_hash": precheck.stored_canonical_payload_hash,
            "recomputed_after_canonical_payload_hash": (
                precheck.recomputed_after_canonical_payload_hash
            ),
            "hash_match_after": precheck.hash_match_after,
            "audit_logs_modified_count": 0,
            "audit_integrity_records_modified_count": 0,
            "verifier_after_restore": None,
            "restore_audit_event_id": None,
            "production_executed": False,
            "status": RESTORE_STATUS_DRY_RUN,
            "warnings": [],
        }

        if not precheck.ok:
            report["status"] = RESTORE_STATUS_REJECTED_UNSAFE
            report["warnings"].append(f"precheck failed: {precheck.reason}")
            return report
        if not approved:
            report["status"] = RESTORE_STATUS_APPROVAL_REQUIRED
            report["warnings"].append(
                "AUDIT_LOG_RESTORE_APPROVED not set -- restore gated; no DB change"
            )
            return report
        if dry_run:
            report["status"] = RESTORE_STATUS_DRY_RUN
            return report

        conn = await self._connect()
        try:
            async with conn.transaction():
                await conn.execute(
                    "SELECT pg_advisory_xact_lock(hashtext($1)::bigint)",
                    ADVISORY_LOCK_NAME,
                )
                # Snapshot is taken by the calling script before this runs.
                result = await conn.execute(
                    "UPDATE audit_logs SET summary = $1 WHERE id = $2 AND summary = $3",
                    precheck._restored_summary,
                    precheck.affected_audit_log_id,
                    precheck._current_summary,
                )
                modified = _rowcount(result)
                report["audit_logs_modified_count"] = modified
                if modified != 1:
                    report["status"] = RESTORE_STATUS_FAILED
                    report["warnings"].append(
                        f"expected to modify exactly 1 row, modified {modified}; rolled back"
                    )
                    raise _RollbackRestore()

                # In-txn confirm the restored row now matches the stored hash.
                row = await conn.fetchrow(
                    "SELECT r.canonical_payload_hash, al.task_id, al.agent, "
                    "al.decision_type, al.summary, al.result, al.artifact_refs, al.created_at "
                    "FROM audit_integrity_records r JOIN audit_logs al ON al.id = r.audit_log_id "
                    "WHERE r.audit_log_id = $1",
                    precheck.affected_audit_log_id,
                )
                recomputed = compute_payload_hash(
                    build_canonical_payload(
                        {
                            "audit_log_id": precheck.affected_audit_log_id,
                            "task_id": row["task_id"],
                            "agent": row["agent"],
                            "decision_type": row["decision_type"],
                            "summary": row["summary"],
                            "result": row["result"],
                            "artifact_refs": row["artifact_refs"],
                            "created_at": row["created_at"],
                        }
                    )
                )
                if recomputed != row["canonical_payload_hash"]:
                    report["status"] = RESTORE_STATUS_FAILED
                    report["warnings"].append(
                        "post-restore canonical hash still mismatches; rolled back"
                    )
                    raise _RollbackRestore()

                # Emit the restore audit event into the chain (tail append).
                event_id = await self._emit_restore_event(conn, precheck)
                report["restore_audit_event_id"] = event_id
                report["status"] = RESTORE_STATUS_COMPLETED
        except _RollbackRestore:
            report["audit_logs_modified_count"] = 0
            report["audit_integrity_records_modified_count"] = 0
        finally:
            await conn.close()
        return report

    async def _emit_restore_event(
        self, conn: asyncpg.Connection, precheck: RestorePrecheck
    ) -> str | None:
        """Insert audit_log + integrity record for the restore action.

        Appends to the chain tail. Carries hashes + ids only, no raw payload.
        """
        import json

        from .signer import AuditSigner

        refs = {
            "affected_audit_log_id": precheck.affected_audit_log_id,
            "affected_sequence_number": precheck.affected_sequence_number,
            "root_cause": precheck.root_cause,
            "restore_type": precheck.restore_type,
            "before_summary_hash": precheck.before_summary_hash,
            "after_summary_hash": precheck.after_summary_hash,
            "production_executed": False,
            "dry_run": False,
        }
        row = await conn.fetchrow(
            "INSERT INTO audit_logs (agent, decision_type, summary, result, task_id, "
            "artifact_refs) VALUES ($1, $2, $3, $4, $5, $6::jsonb) "
            "RETURNING id, task_id, agent, decision_type, summary, result, "
            "artifact_refs, created_at",
            "orchestrator",
            DECISION_AUDIT_LOG_RESTORE_COMPLETED,
            "audit_log test-tamper residue restored",
            "completed",
            "audit-log-restore",
            json.dumps(refs),
        )
        audit_log_row = {
            "audit_log_id": str(row["id"]),
            "task_id": row["task_id"],
            "agent": row["agent"],
            "decision_type": row["decision_type"],
            "summary": row["summary"],
            "result": row["result"],
            "artifact_refs": row["artifact_refs"],
            "created_at": row["created_at"],
        }
        await create_integrity_record_in_txn(
            conn, audit_log_row=audit_log_row, signer=AuditSigner()
        )
        return str(row["id"])


def _production_executed(artifact_refs: Any) -> bool | None:
    refs = artifact_refs
    if isinstance(refs, str):
        import json

        try:
            refs = json.loads(refs)
        except (TypeError, ValueError):
            return None
    if not isinstance(refs, dict):
        return None
    if "production_executed" in refs:
        return bool(refs["production_executed"])
    nested = refs.get("original_event")
    if isinstance(nested, dict) and "production_executed" in nested:
        return bool(nested["production_executed"])
    return None


def _rowcount(execute_result: str) -> int:
    # asyncpg returns e.g. "UPDATE 1"
    try:
        return int(str(execute_result).split()[-1])
    except (ValueError, IndexError):
        return 0


class _RollbackRestore(Exception):
    """Internal sentinel to force a transaction rollback."""


__all__ = [
    "RESTORE_STATUS_DRY_RUN",
    "RESTORE_STATUS_APPROVAL_REQUIRED",
    "RESTORE_STATUS_REJECTED_UNSAFE",
    "RESTORE_STATUS_COMPLETED",
    "RESTORE_STATUS_FAILED",
    "RESTORE_TYPE_TEST_TAMPER_RESIDUE",
    "RestorePrecheck",
    "AuditLogRestorer",
]
