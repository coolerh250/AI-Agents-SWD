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
        for r in sorted(self.integrity, key=lambda x: x["sequence_number"]):
            if min_seq is not None and r["sequence_number"] < min_seq:
                continue
            audit = self.audit_logs[r["audit_log_id"]]
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

    def make_conn(self) -> "_FakeConn":
        return _FakeConn(self)


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
        if "row_hash FROM audit_integrity_records" in sql and "sequence_number = $2" in sql:
            seq = params[1]
            try:
                return self.chain._by_seq(int(seq))["row_hash"]
            except StopIteration:
                return None
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
        return None

    async def execute(self, sql: str, *params):
        self.executed.append((sql, params))
        if sql.strip().upper().startswith("UPDATE AUDIT_INTEGRITY_RECORDS"):
            # UPDATE ... SET canonical=$1, row=$2, prev=$3, status=$4 WHERE integrity_id=$5
            new_canonical, new_row, new_prev, status, integrity_id = params
            for r in self.chain.integrity:
                if r["integrity_id"] == integrity_id:
                    r["canonical_payload_hash"] = new_canonical
                    r["row_hash"] = new_row
                    r["prev_hash"] = new_prev
                    r["integrity_status"] = status
                    break
        return "OK"

    async def close(self):
        return None

    def update_count(self) -> int:
        return sum(
            1
            for sql, _ in self.executed
            if sql.strip().upper().startswith("UPDATE AUDIT_INTEGRITY_RECORDS")
        )
