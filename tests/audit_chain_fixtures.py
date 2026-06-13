"""Stage 42 -- in-memory audit chain + fake asyncpg connection.

Shared test helper (NOT a test module -- no ``test_`` prefix so pytest will
not collect it). Builds a valid integrity chain over synthetic audit_logs
rows and a fake asyncpg connection that supports the queries issued by the
forensic analyzer and the repairer (fetch / fetchval / fetchrow / execute /
transaction). UPDATE statements mutate the in-memory integrity records so an
in-transaction re-verify observes the change.

Nothing here touches a real database.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from shared.sdk.audit_integrity import (
    AuditSigner,
    build_canonical_payload,
    compute_payload_hash,
    compute_row_hash,
)

TAMPER_MARKER = " [TAMPER-SIMULATION]"


class _Row(dict):
    def __getitem__(self, key: str) -> Any:
        return dict.__getitem__(self, key)


class InMemoryChain:
    """A synthetic audit_logs + audit_integrity_records pair."""

    def __init__(self, *, signer: AuditSigner | None = None) -> None:
        self.audit_logs: dict[Any, dict[str, Any]] = {}
        self.integrity: list[dict[str, Any]] = []
        self._signer = signer or AuditSigner(env={})

    def seed(self, n: int, *, decision_type: str = "d", production_executed: bool = False) -> None:
        prev_hash: str | None = None
        for i in range(n):
            audit_id = uuid4()
            created = datetime(2026, 6, 1, tzinfo=timezone.utc) + timedelta(seconds=i)
            audit = {
                "id": audit_id,
                "task_id": f"T-{i}",
                "agent": "x",
                "decision_type": decision_type,
                "summary": f"row {i}",
                "result": "ok",
                "artifact_refs": {"i": i, "production_executed": production_executed},
                "created_at": created,
            }
            self.audit_logs[audit_id] = audit
            seq = i + 1
            payload_hash = compute_payload_hash(build_canonical_payload(audit))
            row_hash = compute_row_hash(
                chain_version=1,
                sequence_number=seq,
                audit_log_id=str(audit_id),
                prev_hash=prev_hash,
                canonical_payload_hash=payload_hash,
            )
            signature, sig_status, key_id = self._signer.sign(row_hash)
            self.integrity.append(
                {
                    "integrity_id": uuid4(),
                    "audit_log_id": audit_id,
                    "chain_version": 1,
                    "sequence_number": seq,
                    "prev_hash": prev_hash,
                    "row_hash": row_hash,
                    "canonical_payload_hash": payload_hash,
                    "hmac_signature": signature,
                    "signing_key_id": key_id,
                    "signature_status": sig_status,
                    "integrity_status": "active",
                    "created_at": created,
                }
            )
            prev_hash = row_hash

    def tamper_summary(self, seq: int, *, marker: str = TAMPER_MARKER) -> None:
        """Append a tamper marker to the audit_log of ``seq`` (integrity intact)."""
        rec = self._by_seq(seq)
        audit = self.audit_logs[rec["audit_log_id"]]
        audit["summary"] = (audit["summary"] or "") + marker

    def set_summary(self, seq: int, summary: str) -> None:
        rec = self._by_seq(seq)
        self.audit_logs[rec["audit_log_id"]]["summary"] = summary

    def _by_seq(self, seq: int) -> dict[str, Any]:
        return next(r for r in self.integrity if r["sequence_number"] == seq)

    def joined_rows(self, *, min_seq: int | None = None) -> list[_Row]:
        rows: list[_Row] = []
        by_id = {str(k): v for k, v in self.audit_logs.items()}
        for r in sorted(self.integrity, key=lambda x: x["sequence_number"]):
            if min_seq is not None and r["sequence_number"] < min_seq:
                continue
            audit = by_id.get(str(r["audit_log_id"]))
            if audit is None:
                continue
            rows.append(
                _Row(
                    {
                        "integrity_id": r["integrity_id"],
                        "sequence_number": r["sequence_number"],
                        "audit_log_id": r["audit_log_id"],
                        "prev_hash": r["prev_hash"],
                        "row_hash": r["row_hash"],
                        "canonical_payload_hash": r["canonical_payload_hash"],
                        "hmac_signature": r["hmac_signature"],
                        "signing_key_id": r["signing_key_id"],
                        "signature_status": r["signature_status"],
                        "integrity_status": r["integrity_status"],
                        "task_id": audit["task_id"],
                        "agent": audit["agent"],
                        "decision_type": audit["decision_type"],
                        "summary": audit["summary"],
                        "result": audit["result"],
                        "artifact_refs": audit["artifact_refs"],
                        "created_at": audit["created_at"],
                    }
                )
            )
        return rows

    def insert_audit_log(
        self,
        *,
        agent: str,
        decision_type: str,
        summary: str,
        result: str,
        task_id: str,
        artifact_refs: Any,
    ) -> _Row:
        audit_id = uuid4()
        created = datetime(2026, 6, 13, tzinfo=timezone.utc)
        audit = {
            "id": audit_id,
            "task_id": task_id,
            "agent": agent,
            "decision_type": decision_type,
            "summary": summary,
            "result": result,
            "artifact_refs": artifact_refs,
            "created_at": created,
        }
        self.audit_logs[audit_id] = audit
        return _Row(
            {
                "id": audit_id,
                "task_id": task_id,
                "agent": agent,
                "decision_type": decision_type,
                "summary": summary,
                "result": result,
                "artifact_refs": artifact_refs,
                "created_at": created,
            }
        )

    def insert_integrity(self, params: tuple) -> _Row:
        (
            audit_log_id,
            chain_version,
            sequence_number,
            prev_hash,
            row_hash,
            canonical_hash,
            signature,
            key_id,
            sig_status,
            integrity_status,
        ) = params
        rec = {
            "integrity_id": uuid4(),
            "audit_log_id": audit_log_id,
            "chain_version": chain_version,
            "sequence_number": sequence_number,
            "prev_hash": prev_hash,
            "row_hash": row_hash,
            "canonical_payload_hash": canonical_hash,
            "hmac_signature": signature,
            "signing_key_id": key_id,
            "signature_status": sig_status,
            "integrity_status": integrity_status,
            "created_at": datetime(2026, 6, 13, tzinfo=timezone.utc),
        }
        self.integrity.append(rec)
        return _Row(rec)

    def synthetic_tamper_audit_id(self):
        """Return the audit_log_id whose summary carries a tamper marker."""
        by_id = {str(k): v for k, v in self.audit_logs.items()}
        for r in self.integrity:
            audit = by_id.get(str(r["audit_log_id"]))
            if audit and (audit["summary"] or "").endswith(TAMPER_MARKER):
                return str(r["audit_log_id"])
        return None

    def make_conn(self) -> "_FakeConn":
        return _FakeConn(self)


def forensic_report_for(failed) -> dict:
    """Build a forensic-report dict (as analyze_audit_chain_mismatch.py would)."""
    from shared.sdk.audit_integrity.forensics import classify_chain_root_cause

    classification = classify_chain_root_cause(failed)
    return {
        "report_id": "audit_forensic_test",
        "first_failed_sequence": failed[0].sequence_number if failed else None,
        "failed_records_count": len(failed),
        "failed_records": [r.to_dict() for r in failed],
        "root_cause_classification": classification["root_cause_classification"],
        "repair_allowed": classification["repair_allowed"],
        "repair_risk": classification["repair_risk"],
        "production_executed": classification["production_executed_involved"],
    }


class _FakeTxn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeConn:
    """Routes the SQL the analyzer + repairer issue to the in-memory chain."""

    def __init__(self, chain: InMemoryChain) -> None:
        self.chain = chain
        self.executed: list[tuple[str, tuple]] = []

    def transaction(self) -> _FakeTxn:
        return _FakeTxn()

    async def fetchval(self, sql: str, *params):
        if "MAX(sequence_number)" in sql:
            seqs = [r["sequence_number"] for r in self.chain.integrity]
            return max(seqs) if seqs else None
        if "prev_hash FROM audit_integrity_records" in sql and "sequence_number = $2" in sql:
            try:
                return self.chain._by_seq(int(params[1]))["prev_hash"]
            except StopIteration:
                return None
        if "row_hash FROM audit_integrity_records" in sql and "sequence_number = $2" in sql:
            try:
                return self.chain._by_seq(int(params[1]))["row_hash"]
            except StopIteration:
                return None
        if "COUNT(*) FROM audit_logs al" in sql and "LEFT JOIN" in sql:
            # missing integrity records
            covered = {r["audit_log_id"] for r in self.chain.integrity}
            return sum(1 for aid in self.chain.audit_logs if aid not in covered)
        if "COUNT(*) FROM audit_logs" in sql:
            return len(self.chain.audit_logs)
        if "COUNT(*) FROM audit_integrity_records" in sql:
            return len(self.chain.integrity)
        return 0

    async def fetch(self, sql: str, *params):
        if "sequence_number >= $2" in sql:
            return self.chain.joined_rows(min_seq=int(params[1]))
        return self.chain.joined_rows()

    async def fetchrow(self, sql: str, *params):
        # precheck / apply join by a single sequence_number
        if "JOIN audit_logs al" in sql and "r.sequence_number = $2" in sql:
            for row in self.chain.joined_rows():
                if row["sequence_number"] == int(params[1]):
                    return row
            return None
        # apply re-read by audit_log_id
        if "JOIN audit_logs al" in sql and "r.audit_log_id = $1" in sql:
            for row in self.chain.joined_rows():
                if str(row["audit_log_id"]) == str(params[0]):
                    return row
            return None
        # INSERT a new audit_logs row (restore event)
        if sql.strip().upper().startswith("INSERT INTO AUDIT_LOGS"):
            return self.chain.insert_audit_log(
                agent=params[0],
                decision_type=params[1],
                summary=params[2],
                result=params[3],
                task_id=params[4],
                artifact_refs=params[5],
            )
        # create_integrity_record_in_txn: existence check
        if "SELECT 1 FROM audit_integrity_records WHERE audit_log_id = $1" in sql:
            return None
        # create_integrity_record_in_txn: latest record
        if "sequence_number, row_hash" in sql and "ORDER BY sequence_number DESC" in sql:
            if not self.chain.integrity:
                return None
            latest = max(self.chain.integrity, key=lambda r: r["sequence_number"])
            return _Row(
                {"sequence_number": latest["sequence_number"], "row_hash": latest["row_hash"]}
            )
        # create_integrity_record_in_txn: INSERT integrity record
        if sql.strip().upper().startswith("INSERT INTO AUDIT_INTEGRITY_RECORDS"):
            return self.chain.insert_integrity(params)
        return None

    async def execute(self, sql: str, *params):
        self.executed.append((sql, params))
        up = sql.strip().upper()
        if up.startswith("UPDATE AUDIT_INTEGRITY_RECORDS"):
            new_canonical, new_row, new_prev, status, integrity_id = params
            for r in self.chain.integrity:
                if r["integrity_id"] == integrity_id:
                    r["canonical_payload_hash"] = new_canonical
                    r["row_hash"] = new_row
                    r["prev_hash"] = new_prev
                    r["integrity_status"] = status
                    break
            return "UPDATE 1"
        if up.startswith("UPDATE AUDIT_LOGS SET SUMMARY"):
            # UPDATE audit_logs SET summary=$1 WHERE id=$2 AND summary=$3
            new_summary, audit_id, expected = params[0], params[1], params[2]
            n = 0
            for aid, audit in self.chain.audit_logs.items():
                if str(aid) == str(audit_id) and audit["summary"] == expected:
                    audit["summary"] = new_summary
                    n += 1
            return f"UPDATE {n}"
        return "OK"

    async def close(self):
        return None

    def audit_log_update_count(self) -> int:
        return sum(
            1
            for sql, _ in self.executed
            if sql.strip().upper().startswith("UPDATE AUDIT_LOGS")
        )

    def integrity_update_count(self) -> int:
        return sum(
            1
            for sql, _ in self.executed
            if sql.strip().upper().startswith("UPDATE AUDIT_INTEGRITY_RECORDS")
        )
