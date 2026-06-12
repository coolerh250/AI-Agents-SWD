"""Stage 34 -- AuditChainVerifier tests with in-memory tables.

Exercises the four detection paths the verifier promises: passed,
partial (missing integrity record), failed (canonical_payload_hash
mismatch), failed (prev_hash mismatch). Also confirms HMAC verification
on a per-row basis when a key is configured.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import asyncpg

from shared.sdk.audit_integrity import (
    AuditChainVerifier,
    AuditIntegrityStore,
    AuditSigner,
    build_canonical_payload,
    compute_payload_hash,
    compute_row_hash,
)
from shared.sdk.audit_integrity.models import (
    SIGNATURE_STATUS_SIGNED,
    VERIFICATION_STATUS_FAILED,
    VERIFICATION_STATUS_PARTIAL,
    VERIFICATION_STATUS_PASSED,
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeRow(dict):
    def __getitem__(self, key: str) -> Any:
        return dict.__getitem__(self, key)


class _Fixture:
    def __init__(self):
        self.audit_logs: list[dict[str, Any]] = []
        self.integrity_records: list[dict[str, Any]] = []
        self.signer_for_seed = AuditSigner(env={})

    def seed(self, n: int):
        """Insert ``n`` audit rows + a valid integrity chain for them."""
        prev_hash: str | None = None
        for i in range(n):
            audit_id = uuid4()
            created = datetime(2026, 6, 1, tzinfo=timezone.utc) + timedelta(seconds=i)
            audit = {
                "id": audit_id,
                "task_id": f"T-{i}",
                "agent": "x",
                "decision_type": "d",
                "summary": f"row {i}",
                "result": "ok",
                "artifact_refs": {"i": i},
                "created_at": created,
            }
            self.audit_logs.append(audit)
            canonical = build_canonical_payload(audit)
            payload_hash = compute_payload_hash(canonical)
            seq = i + 1
            row_hash = compute_row_hash(
                chain_version=1,
                sequence_number=seq,
                audit_log_id=str(audit_id),
                prev_hash=prev_hash,
                canonical_payload_hash=payload_hash,
            )
            signature, sig_status, key_id = self.signer_for_seed.sign(row_hash)
            self.integrity_records.append(
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

    def make_conn(self):
        fx = self

        class _Conn:
            async def fetchval(self_inner, sql, *params):
                if "FROM audit_logs" in sql:
                    return len(fx.audit_logs)
                if "FROM audit_integrity_records" in sql:
                    return len(fx.integrity_records)
                return 0

            async def fetch(self_inner, sql, *params):
                # The verifier issues a single JOIN ordered by sequence.
                rows = []
                by_audit = {a["id"]: a for a in fx.audit_logs}
                for r in sorted(fx.integrity_records, key=lambda x: x["sequence_number"]):
                    audit = by_audit.get(r["audit_log_id"])
                    if audit is None:
                        # Integrity record without audit row -- skip (the
                        # JOIN would also exclude it).
                        continue
                    rows.append(
                        _FakeRow(
                            {
                                "sequence_number": r["sequence_number"],
                                "audit_log_id": r["audit_log_id"],
                                "prev_hash": r["prev_hash"],
                                "row_hash": r["row_hash"],
                                "canonical_payload_hash": r["canonical_payload_hash"],
                                "hmac_signature": r["hmac_signature"],
                                "signature_status": r["signature_status"],
                                "signing_key_id": r["signing_key_id"],
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

            async def fetchrow(self_inner, sql, *params):
                return None

            async def close(self_inner):
                return None

        return _Conn()

    def patch(self, monkeypatch):
        async def _connect(*args, **kwargs):
            return self.make_conn()

        monkeypatch.setattr(asyncpg, "connect", _connect)


def test_verify_chain_passes_on_intact_chain(monkeypatch):
    fx = _Fixture()
    fx.seed(5)
    fx.patch(monkeypatch)
    verifier = AuditChainVerifier(dsn="postgresql://x", signer=AuditSigner(env={}))
    result = _run(verifier.verify_chain())
    assert result.status == VERIFICATION_STATUS_PASSED
    assert result.verified_records == 5
    assert result.failed_records == 0
    assert result.missing_integrity_records == 0


def test_verify_chain_partial_when_audit_logs_missing_integrity(monkeypatch):
    fx = _Fixture()
    fx.seed(3)
    # Add a 4th audit_log row without an integrity record.
    fx.audit_logs.append(
        {
            "id": uuid4(),
            "task_id": "T-x",
            "agent": "x",
            "decision_type": "d",
            "summary": "extra",
            "result": "ok",
            "artifact_refs": {},
            "created_at": datetime(2026, 6, 2, tzinfo=timezone.utc),
        }
    )
    fx.patch(monkeypatch)
    verifier = AuditChainVerifier(dsn="postgresql://x", signer=AuditSigner(env={}))
    result = _run(verifier.verify_chain())
    assert result.status == VERIFICATION_STATUS_PARTIAL
    assert result.missing_integrity_records == 1
    assert result.failure_reason and "lack an integrity record" in result.failure_reason


def test_verify_chain_failed_on_payload_mutation(monkeypatch):
    fx = _Fixture()
    fx.seed(3)
    # Tamper the audit row for sequence 2.
    target = next(
        r for r in fx.audit_logs if str(r["id"]) == str(fx.integrity_records[1]["audit_log_id"])
    )
    target["summary"] = "TAMPERED"
    fx.patch(monkeypatch)
    verifier = AuditChainVerifier(dsn="postgresql://x", signer=AuditSigner(env={}))
    result = _run(verifier.verify_chain())
    assert result.status == VERIFICATION_STATUS_FAILED
    assert result.first_failure_sequence == 2
    assert result.failure_reason == "canonical_payload_hash_mismatch"
    assert result.expected_hash != result.actual_hash


def test_verify_chain_failed_on_prev_hash_mutation(monkeypatch):
    fx = _Fixture()
    fx.seed(3)
    # Break the link by mutating prev_hash on the 3rd record only.
    fx.integrity_records[2]["prev_hash"] = "deadbeef"
    fx.patch(monkeypatch)
    verifier = AuditChainVerifier(dsn="postgresql://x", signer=AuditSigner(env={}))
    result = _run(verifier.verify_chain())
    assert result.status == VERIFICATION_STATUS_FAILED
    assert result.first_failure_sequence == 3
    # When prev_hash is mutated, the recomputed row_hash also changes,
    # so the row_hash check fires first. Either reason is correct
    # detection of the tamper.
    assert result.failure_reason in {"row_hash_mismatch", "prev_hash_mismatch"}


def test_verify_chain_failed_on_hmac_invalid(monkeypatch):
    fx = _Fixture()
    # Seed signed chain by configuring the seed signer.
    fx.signer_for_seed = AuditSigner(env={"AUDIT_HMAC_KEY": "real-key"})
    fx.seed(2)
    # Sanity: rows are signed.
    assert fx.integrity_records[0]["signature_status"] == SIGNATURE_STATUS_SIGNED
    # Mutate the stored signature so verify fails.
    fx.integrity_records[1]["hmac_signature"] = "0" * 64
    fx.patch(monkeypatch)

    verifier = AuditChainVerifier(
        dsn="postgresql://x", signer=AuditSigner(env={"AUDIT_HMAC_KEY": "real-key"})
    )
    result = _run(verifier.verify_chain())
    assert result.status == VERIFICATION_STATUS_FAILED
    assert result.failure_reason == "hmac_signature_invalid"
    # The verifier must NOT echo signature bytes.
    assert result.expected_hash is None
    assert result.actual_hash is None


def test_to_run_carries_metadata_for_audit_log(monkeypatch):
    fx = _Fixture()
    fx.seed(1)
    fx.patch(monkeypatch)
    verifier = AuditChainVerifier(dsn="postgresql://x", signer=AuditSigner(env={}))
    result = _run(verifier.verify_chain())
    run = verifier.to_run(result)
    assert run.metadata["audit_logs_count"] == 1
    assert run.metadata["integrity_records_count"] == 1
    assert run.metadata["hmac_enabled"] is False


def test_store_record_verification_run_persists(monkeypatch):
    """The store accepts the verifier's run dataclass and INSERTs it."""

    captured: dict[str, Any] = {}

    class _Conn:
        async def fetchrow(self_inner, sql, *params):
            captured["sql"] = sql
            captured["params"] = params
            # Return what the store expects.
            return _FakeRow(
                {
                    "verification_id": uuid4(),
                    "chain_version": params[0],
                    "status": params[1],
                    "total_records": params[2],
                    "verified_records": params[3],
                    "failed_records": params[4],
                    "first_failure_sequence": params[5],
                    "first_failure_audit_log_id": params[6],
                    "failure_reason": params[7],
                    "started_at": params[8],
                    "completed_at": params[9],
                    "metadata": params[10],
                }
            )

        async def close(self_inner):
            return None

    async def _connect(*args, **kwargs):
        return _Conn()

    monkeypatch.setattr(asyncpg, "connect", _connect)
    store = AuditIntegrityStore(dsn="postgresql://x")
    fx = _Fixture()
    fx.seed(1)
    verifier = AuditChainVerifier(dsn="postgresql://x", signer=AuditSigner(env={}))
    fx.patch(monkeypatch)
    result = _run(verifier.verify_chain())
    # Re-patch back to the captured-conn for the INSERT.
    monkeypatch.setattr(asyncpg, "connect", _connect)
    run = verifier.to_run(result)
    persisted = _run(store.record_verification_run(run=run))
    assert persisted.status == result.status
    assert "INSERT INTO audit_chain_verification_runs" in captured["sql"]


def test_uuid_imports_unused():
    # Silence pyflakes: UUID is exported in the fake module to make
    # asyncpg.Record-equivalents type-check.
    _ = UUID
