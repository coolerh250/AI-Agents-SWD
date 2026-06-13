"""Stage 42 -- audit chain forensic analysis + root cause classification.

This module is READ-ONLY against the database. It locates every failing
record in the integrity chain (the verifier itself stops at the first
mismatch), recomputes the canonical payload hash + row hash with the
current logic, compares stored vs recomputed values, inspects chain
continuity, classifies a root cause, and produces a redacted report.

Nothing here mutates ``audit_logs`` or ``audit_integrity_records``. The
classification functions are pure (no DB) so they can be unit-tested
without Postgres; only :class:`AuditChainForensicAnalyzer` touches the DB.

No secret, token, or HMAC key value is ever read or emitted. Free-text
fields (``summary``) are truncated and scrubbed before they enter a report.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import asyncpg

from .canonical import build_canonical_payload
from .hasher import compute_payload_hash, compute_row_hash
from .models import CHAIN_VERSION

DEFAULT_DATABASE_URL = "postgresql://postgres@localhost:5432/aiagents"

# ---------------------------------------------------------------------------
# Failure types (what diverged on a single record)
# ---------------------------------------------------------------------------
FAILURE_CANONICAL_PAYLOAD_HASH = "canonical_payload_hash_mismatch"
FAILURE_ROW_HASH = "row_hash_mismatch"
FAILURE_PREV_HASH = "prev_hash_mismatch"
FAILURE_SEQUENCE_GAP = "sequence_gap"
FAILURE_SIGNATURE_INVALID = "hmac_signature_invalid"
FAILURE_SIGNING_KEY_MISSING = "hmac_signing_key_missing"

# ---------------------------------------------------------------------------
# Root cause classification vocabulary
# ---------------------------------------------------------------------------
ROOT_CAUSE_TEST_TAMPER_NOT_RESTORED = "test_tamper_not_restored"
ROOT_CAUSE_CANONICALIZATION_VERSION_DRIFT = "canonicalization_version_drift"
ROOT_CAUSE_DIRECT_POST_LEGACY_GAP = "direct_post_legacy_gap"
ROOT_CAUSE_INTEGRITY_WRITER_BUG = "integrity_writer_bug"
ROOT_CAUSE_AUDIT_LOG_MUTATED = "audit_log_mutated_after_integrity"
ROOT_CAUSE_MANUAL_DATABASE_CHANGE = "manual_database_change"
ROOT_CAUSE_TIMESTAMP_SERIALIZATION_DRIFT = "timestamp_serialization_drift"
ROOT_CAUSE_JSONB_ORDERING_DRIFT = "jsonb_ordering_drift"
ROOT_CAUSE_HMAC_KEY_MISSING_ONLY = "hmac_key_missing_only"
ROOT_CAUSE_UNKNOWN = "unknown"

# Root causes for which a controlled repair MAY be allowed (subject to the
# repair policy: synthetic / non-production / deterministic). The final
# repair_allowed decision still requires every failed record to be repairable.
REPAIRABLE_ROOT_CAUSES = frozenset(
    {
        ROOT_CAUSE_TEST_TAMPER_NOT_RESTORED,
        ROOT_CAUSE_CANONICALIZATION_VERSION_DRIFT,
        ROOT_CAUSE_DIRECT_POST_LEGACY_GAP,
    }
)

# Repair risk levels.
REPAIR_RISK_LOW = "low"
REPAIR_RISK_MEDIUM = "medium"
REPAIR_RISK_HIGH = "high"

# Known synthetic tamper markers appended by test harnesses. If stripping a
# marker reproduces the stored canonical hash, the record is provably a
# self-inflicted test tamper rather than a real mutation.
KNOWN_TAMPER_MARKERS = (" [TAMPER-SIMULATION]",)

# task_id values that mark a synthetic / smoke-test audit row.
SYNTHETIC_TASK_IDS = frozenset({"smoke", "test", "smoke-test", "verify"})

_SUMMARY_MAX = 160
_SECRET_SCRUB = re.compile(r"(ghp_[A-Za-z0-9]{8,}|sk-[A-Za-z0-9]{8,}|xox[baprs]-[A-Za-z0-9-]{8,})")


def redact_summary(summary: str | None) -> str:
    """Truncate + scrub a free-text summary so it is safe to store in a report."""
    if not summary:
        return ""
    scrubbed = _SECRET_SCRUB.sub("[REDACTED]", summary)
    if len(scrubbed) > _SUMMARY_MAX:
        return scrubbed[:_SUMMARY_MAX] + "...[truncated]"
    return scrubbed


@dataclass
class FailedRecordAnalysis:
    """Per-record forensic findings. Redacted + safe to serialise."""

    sequence_number: int
    audit_log_id: str
    decision_type: str
    task_id: str | None
    created_at: str
    stored_canonical_payload_hash: str
    recomputed_canonical_payload_hash: str
    stored_row_hash: str
    recomputed_row_hash: str
    stored_prev_record_hash: str | None
    expected_prev_record_hash: str | None
    signature_status: str
    signature_verification_status: str
    failure_types: list[str] = field(default_factory=list)
    summary_redacted: str = ""
    tamper_marker_detected: bool = False
    recovered_original_matches: bool = False
    production_executed: bool | None = None
    suspected_root_cause: str = ROOT_CAUSE_UNKNOWN
    repairable: bool = False
    repair_risk: str = REPAIR_RISK_HIGH

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence_number": self.sequence_number,
            "audit_log_id": self.audit_log_id,
            "decision_type": self.decision_type,
            "task_id": self.task_id,
            "created_at": self.created_at,
            "stored_canonical_payload_hash": self.stored_canonical_payload_hash,
            "recomputed_canonical_payload_hash": self.recomputed_canonical_payload_hash,
            "stored_row_hash": self.stored_row_hash,
            "recomputed_row_hash": self.recomputed_row_hash,
            "stored_prev_record_hash": self.stored_prev_record_hash,
            "expected_prev_record_hash": self.expected_prev_record_hash,
            "signature_status": self.signature_status,
            "signature_verification_status": self.signature_verification_status,
            "failure_types": list(self.failure_types),
            "summary_redacted": self.summary_redacted,
            "tamper_marker_detected": self.tamper_marker_detected,
            "recovered_original_matches": self.recovered_original_matches,
            "production_executed": self.production_executed,
            "suspected_root_cause": self.suspected_root_cause,
            "repairable": self.repairable,
            "repair_risk": self.repair_risk,
        }


def _extract_production_executed(artifact_refs: Any) -> bool | None:
    """Best-effort read of artifact_refs.production_executed (bool or None)."""
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


def _strip_known_marker(summary: str | None) -> tuple[str | None, str | None]:
    """If ``summary`` ends with a known tamper marker, return (original, marker)."""
    if not summary:
        return None, None
    for marker in KNOWN_TAMPER_MARKERS:
        if summary.endswith(marker):
            return summary[: -len(marker)], marker
    return None, None


def analyse_record(
    *,
    sequence_number: int,
    audit_log_id: str,
    audit_log_row: dict[str, Any],
    stored_canonical_payload_hash: str,
    stored_row_hash: str,
    stored_prev_hash: str | None,
    signature_status: str,
    expected_prev_record_hash: str | None,
    signature_verification_status: str = "n/a",
    chain_version: int = CHAIN_VERSION,
) -> FailedRecordAnalysis:
    """Recompute hashes for one record and classify its failure.

    Pure function (no DB). ``audit_log_row`` is the current audit_logs row
    (``task_id``/``agent``/``decision_type``/``summary``/``result``/
    ``artifact_refs``/``created_at``). ``expected_prev_record_hash`` is the
    *previous* integrity record's stored ``row_hash`` (None for seq 1).
    """
    canonical = build_canonical_payload({"audit_log_id": audit_log_id, **audit_log_row})
    recomputed_canonical = compute_payload_hash(canonical)
    recomputed_row = compute_row_hash(
        chain_version=chain_version,
        sequence_number=sequence_number,
        audit_log_id=audit_log_id,
        prev_hash=stored_prev_hash,
        canonical_payload_hash=recomputed_canonical,
    )

    failure_types: list[str] = []
    if recomputed_canonical != stored_canonical_payload_hash:
        failure_types.append(FAILURE_CANONICAL_PAYLOAD_HASH)
    if recomputed_row != stored_row_hash:
        failure_types.append(FAILURE_ROW_HASH)
    if (
        expected_prev_record_hash is not None
        and stored_prev_hash is not None
        and stored_prev_hash != expected_prev_record_hash
    ):
        failure_types.append(FAILURE_PREV_HASH)
    if signature_verification_status in (FAILURE_SIGNATURE_INVALID, "signature_failed"):
        failure_types.append(FAILURE_SIGNATURE_INVALID)
    if signature_verification_status in (FAILURE_SIGNING_KEY_MISSING, "key_missing"):
        failure_types.append(FAILURE_SIGNING_KEY_MISSING)

    summary = audit_log_row.get("summary")
    original, marker = _strip_known_marker(summary)
    tamper_marker_detected = marker is not None
    recovered_original_matches = False
    if original is not None:
        recovered = dict(audit_log_row)
        recovered["summary"] = original
        recovered_hash = compute_payload_hash(
            build_canonical_payload({"audit_log_id": audit_log_id, **recovered})
        )
        recovered_original_matches = recovered_hash == stored_canonical_payload_hash

    production_executed = _extract_production_executed(audit_log_row.get("artifact_refs"))

    analysis = FailedRecordAnalysis(
        sequence_number=sequence_number,
        audit_log_id=audit_log_id,
        decision_type=str(audit_log_row.get("decision_type") or ""),
        task_id=audit_log_row.get("task_id"),
        created_at=_iso(audit_log_row.get("created_at")),
        stored_canonical_payload_hash=stored_canonical_payload_hash,
        recomputed_canonical_payload_hash=recomputed_canonical,
        stored_row_hash=stored_row_hash,
        recomputed_row_hash=recomputed_row,
        stored_prev_record_hash=stored_prev_hash,
        expected_prev_record_hash=expected_prev_record_hash,
        signature_status=signature_status,
        signature_verification_status=signature_verification_status,
        failure_types=failure_types,
        summary_redacted=redact_summary(summary),
        tamper_marker_detected=tamper_marker_detected,
        recovered_original_matches=recovered_original_matches,
        production_executed=production_executed,
    )
    _classify_record(analysis)
    return analysis


def _classify_record(a: FailedRecordAnalysis) -> None:
    """Set ``suspected_root_cause`` / ``repairable`` / ``repair_risk`` in place."""
    canonical_ok = FAILURE_CANONICAL_PAYLOAD_HASH not in a.failure_types
    row_ok = FAILURE_ROW_HASH not in a.failure_types
    prev_ok = FAILURE_PREV_HASH not in a.failure_types
    signature_failed = (
        FAILURE_SIGNATURE_INVALID in a.failure_types
        or FAILURE_SIGNING_KEY_MISSING in a.failure_types
    )

    # Signature-only: payload + chain are intact, only the HMAC failed.
    # Never repair the payload hash for a key issue.
    if canonical_ok and row_ok and prev_ok and signature_failed:
        a.suspected_root_cause = ROOT_CAUSE_HMAC_KEY_MISSING_ONLY
        a.repairable = False
        a.repair_risk = REPAIR_RISK_LOW
        return

    # Provable synthetic test tamper: stripping a known marker reproduces the
    # stored canonical hash, the row is non-production, and carries a marker.
    if (
        not canonical_ok
        and a.tamper_marker_detected
        and a.recovered_original_matches
        and a.production_executed is False
    ):
        a.suspected_root_cause = ROOT_CAUSE_TEST_TAMPER_NOT_RESTORED
        a.repairable = True
        a.repair_risk = REPAIR_RISK_LOW
        return

    # Canonical mismatch with no proof of synthetic origin -> the audit_log
    # was mutated after its integrity record was written. Not repairable
    # unless proven synthetic (handled above).
    if not canonical_ok:
        a.suspected_root_cause = ROOT_CAUSE_AUDIT_LOG_MUTATED
        a.repairable = False
        a.repair_risk = REPAIR_RISK_HIGH
        return

    # prev_hash diverges but payload is fine -> chain re-link / manual change.
    if not prev_ok:
        a.suspected_root_cause = ROOT_CAUSE_MANUAL_DATABASE_CHANGE
        a.repairable = False
        a.repair_risk = REPAIR_RISK_HIGH
        return

    a.suspected_root_cause = ROOT_CAUSE_UNKNOWN
    a.repairable = False
    a.repair_risk = REPAIR_RISK_HIGH


def classify_chain_root_cause(
    failed: list[FailedRecordAnalysis],
) -> dict[str, Any]:
    """Aggregate per-record findings into a chain-level classification.

    Returns a dict with ``root_cause_classification``, ``confidence``,
    ``repair_allowed``, ``repair_risk``, ``repair_policy_reason`` and the
    affected sequence range / decision types.
    """
    if not failed:
        return {
            "root_cause_classification": None,
            "confidence": "n/a",
            "repair_allowed": False,
            "repair_risk": REPAIR_RISK_LOW,
            "repair_policy_reason": "no failed records",
            "affected_sequence_range": None,
            "affected_decision_types": [],
            "production_executed_involved": False,
        }

    causes = {r.suspected_root_cause for r in failed}
    decision_types = sorted({r.decision_type for r in failed if r.decision_type})
    seqs = sorted(r.sequence_number for r in failed)
    seq_range = [seqs[0], seqs[-1]]
    production_involved = any(r.production_executed is True for r in failed)

    # Canonicalization drift heuristic: many records, same decision type, all
    # canonical mismatches, none carrying a synthetic marker.
    if (
        len(failed) >= 3
        and len(decision_types) == 1
        and all(
            FAILURE_CANONICAL_PAYLOAD_HASH in r.failure_types and not r.tamper_marker_detected
            for r in failed
        )
        and causes <= {ROOT_CAUSE_AUDIT_LOG_MUTATED, ROOT_CAUSE_CANONICALIZATION_VERSION_DRIFT}
    ):
        root = ROOT_CAUSE_CANONICALIZATION_VERSION_DRIFT
        repair_allowed = not production_involved
        return {
            "root_cause_classification": root,
            "confidence": "medium",
            "repair_allowed": repair_allowed,
            "repair_risk": _aggregate_risk(failed),
            "repair_policy_reason": (
                "uniform canonicalization drift across one decision_type"
                if repair_allowed
                else "production_executed involved -> repair blocked"
            ),
            "affected_sequence_range": seq_range,
            "affected_decision_types": decision_types,
            "production_executed_involved": production_involved,
        }

    # Single clean root cause shared by all failed records.
    if len(causes) == 1:
        root = next(iter(causes))
        all_repairable = all(r.repairable for r in failed)
        repair_allowed = (
            all_repairable and root in REPAIRABLE_ROOT_CAUSES and not production_involved
        )
        reason = _repair_reason(root, all_repairable, production_involved)
        return {
            "root_cause_classification": root,
            "confidence": "high" if root != ROOT_CAUSE_UNKNOWN else "low",
            "repair_allowed": repair_allowed,
            "repair_risk": _aggregate_risk(failed),
            "repair_policy_reason": reason,
            "affected_sequence_range": seq_range,
            "affected_decision_types": decision_types,
            "production_executed_involved": production_involved,
        }

    # Mixed / ambiguous causes -> conservative: unknown, no repair.
    return {
        "root_cause_classification": ROOT_CAUSE_UNKNOWN,
        "confidence": "low",
        "repair_allowed": False,
        "repair_risk": REPAIR_RISK_HIGH,
        "repair_policy_reason": (f"mixed root causes {sorted(causes)} -> cannot prove safe repair"),
        "affected_sequence_range": seq_range,
        "affected_decision_types": decision_types,
        "production_executed_involved": production_involved,
    }


def _repair_reason(root: str, all_repairable: bool, production_involved: bool) -> str:
    if production_involved:
        return "production_executed involved -> repair blocked"
    if root == ROOT_CAUSE_UNKNOWN:
        return "unknown root cause -> repair blocked"
    if root == ROOT_CAUSE_HMAC_KEY_MISSING_ONLY:
        return "signature/key-only failure -> payload repair not applicable"
    if root == ROOT_CAUSE_AUDIT_LOG_MUTATED:
        return "audit_log mutated after integrity, not proven synthetic -> repair blocked"
    if root == ROOT_CAUSE_MANUAL_DATABASE_CHANGE:
        return "manual database change -> repair blocked"
    if not all_repairable:
        return f"{root} present but not every record is repairable -> repair blocked"
    if root in REPAIRABLE_ROOT_CAUSES:
        return f"{root}: synthetic non-production artifact, deterministic repair"
    return "repair blocked"


def _aggregate_risk(failed: list[FailedRecordAnalysis]) -> str:
    """Aggregate per-record risk; the tail-size cascade dominates."""
    if any(r.repair_risk == REPAIR_RISK_HIGH for r in failed):
        return REPAIR_RISK_HIGH
    return REPAIR_RISK_MEDIUM if len(failed) > 1 else REPAIR_RISK_LOW


def _iso(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    return str(value)


class AuditChainForensicAnalyzer:
    """Read-only forensic scan over the integrity chain.

    Unlike the verifier (which stops at the first mismatch), this walks the
    full chain and collects EVERY failing record. It never writes.
    """

    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(dsn=self.dsn, timeout=10)

    async def scan(self, chain_version: int = CHAIN_VERSION) -> list[FailedRecordAnalysis]:
        conn = await self._connect()
        try:
            rows = await conn.fetch(
                "SELECT r.sequence_number, r.audit_log_id, r.prev_hash, "
                "r.row_hash, r.canonical_payload_hash, r.signature_status, "
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

        failed: list[FailedRecordAnalysis] = []
        prev_seq = 0
        prev_row_hash: str | None = None
        for row in rows:
            seq = int(row["sequence_number"])
            audit_log_id = str(row["audit_log_id"])
            expected_prev = prev_row_hash if seq > 1 else None
            analysis = analyse_record(
                sequence_number=seq,
                audit_log_id=audit_log_id,
                audit_log_row={
                    "task_id": row["task_id"],
                    "agent": row["agent"],
                    "decision_type": row["decision_type"],
                    "summary": row["summary"],
                    "result": row["result"],
                    "artifact_refs": row["artifact_refs"],
                    "created_at": row["created_at"],
                },
                stored_canonical_payload_hash=row["canonical_payload_hash"],
                stored_row_hash=row["row_hash"],
                stored_prev_hash=row["prev_hash"],
                signature_status=row["signature_status"],
                expected_prev_record_hash=expected_prev,
                chain_version=chain_version,
            )
            if seq != prev_seq + 1:
                analysis.failure_types.insert(0, FAILURE_SEQUENCE_GAP)
            if analysis.failure_types:
                failed.append(analysis)
            prev_seq = seq
            prev_row_hash = row["row_hash"]
        return failed


__all__ = [
    "FAILURE_CANONICAL_PAYLOAD_HASH",
    "FAILURE_ROW_HASH",
    "FAILURE_PREV_HASH",
    "FAILURE_SEQUENCE_GAP",
    "FAILURE_SIGNATURE_INVALID",
    "FAILURE_SIGNING_KEY_MISSING",
    "ROOT_CAUSE_TEST_TAMPER_NOT_RESTORED",
    "ROOT_CAUSE_CANONICALIZATION_VERSION_DRIFT",
    "ROOT_CAUSE_DIRECT_POST_LEGACY_GAP",
    "ROOT_CAUSE_INTEGRITY_WRITER_BUG",
    "ROOT_CAUSE_AUDIT_LOG_MUTATED",
    "ROOT_CAUSE_MANUAL_DATABASE_CHANGE",
    "ROOT_CAUSE_TIMESTAMP_SERIALIZATION_DRIFT",
    "ROOT_CAUSE_JSONB_ORDERING_DRIFT",
    "ROOT_CAUSE_HMAC_KEY_MISSING_ONLY",
    "ROOT_CAUSE_UNKNOWN",
    "REPAIRABLE_ROOT_CAUSES",
    "REPAIR_RISK_LOW",
    "REPAIR_RISK_MEDIUM",
    "REPAIR_RISK_HIGH",
    "KNOWN_TAMPER_MARKERS",
    "FailedRecordAnalysis",
    "AuditChainForensicAnalyzer",
    "analyse_record",
    "classify_chain_root_cause",
    "redact_summary",
]
