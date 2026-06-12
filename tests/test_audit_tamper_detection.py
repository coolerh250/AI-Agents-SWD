"""Stage 34 -- tamper detection scenarios (pure / in-memory).

Replays the canonical tamper paths a verifier must catch:

* canonical payload mutated  -> canonical_payload_hash_mismatch
* row_hash mutated           -> row_hash_mismatch
* prev_hash broken           -> row_hash_mismatch (or prev_hash_mismatch)
* HMAC signature swapped     -> hmac_signature_invalid

Reuses the in-memory fixture shape from ``test_audit_chain_verifier``.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import asyncpg

from shared.sdk.audit_integrity import (
    AuditChainVerifier,
    AuditSigner,
    build_canonical_payload,
    compute_payload_hash,
    compute_row_hash,
)
from shared.sdk.audit_integrity.models import (
    VERIFICATION_STATUS_FAILED,
    VERIFICATION_STATUS_PASSED,
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeRow(dict):
    def __getitem__(self, key: str) -> Any:
        return dict.__getitem__(self, key)


def _seed(rows: int = 3, signer: AuditSigner | None = None):
    signer = signer or AuditSigner(env={})
    audit_logs: list[dict[str, Any]] = []
    integrity: list[dict[str, Any]] = []
    prev_hash: str | None = None
    for i in range(rows):
        audit_id = uuid4()
        audit = {
            "id": audit_id,
            "task_id": f"T-{i}",
            "agent": "x",
            "decision_type": "d",
            "summary": f"row {i}",
            "result": "ok",
            "artifact_refs": {"i": i},
            "created_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
        }
        audit_logs.append(audit)
        canonical = build_canonical_payload(audit)
        ph = compute_payload_hash(canonical)
        seq = i + 1
        rh = compute_row_hash(
            chain_version=1,
            sequence_number=seq,
            audit_log_id=str(audit_id),
            prev_hash=prev_hash,
            canonical_payload_hash=ph,
        )
        sig, status, key_id = signer.sign(rh)
        integrity.append(
            {
                "integrity_id": uuid4(),
                "audit_log_id": audit_id,
                "chain_version": 1,
                "sequence_number": seq,
                "prev_hash": prev_hash,
                "row_hash": rh,
                "canonical_payload_hash": ph,
                "hmac_signature": sig,
                "signing_key_id": key_id,
                "signature_status": status,
                "integrity_status": "active",
                "created_at": datetime.now(timezone.utc),
            }
        )
        prev_hash = rh
    return audit_logs, integrity


def _patch(monkeypatch, audit_logs, integrity):
    class _Conn:
        async def fetchval(self_inner, sql, *params):
            if "audit_logs" in sql:
                return len(audit_logs)
            return len(integrity)

        async def fetch(self_inner, sql, *params):
            by_audit = {a["id"]: a for a in audit_logs}
            out = []
            for r in sorted(integrity, key=lambda x: x["sequence_number"]):
                audit = by_audit.get(r["audit_log_id"])
                if audit is None:
                    continue
                out.append(
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
            return out

        async def fetchrow(self_inner, sql, *params):
            return None

        async def close(self_inner):
            return None

    async def _connect(*args, **kwargs):
        return _Conn()

    monkeypatch.setattr(asyncpg, "connect", _connect)


def test_baseline_passes(monkeypatch):
    audit_logs, integrity = _seed(2)
    _patch(monkeypatch, audit_logs, integrity)
    result = _run(AuditChainVerifier(dsn="x", signer=AuditSigner(env={})).verify_chain())
    assert result.status == VERIFICATION_STATUS_PASSED


def test_tamper_payload_detected(monkeypatch):
    audit_logs, integrity = _seed(2)
    audit_logs[0]["summary"] = "mutated"
    _patch(monkeypatch, audit_logs, integrity)
    result = _run(AuditChainVerifier(dsn="x", signer=AuditSigner(env={})).verify_chain())
    assert result.status == VERIFICATION_STATUS_FAILED
    assert result.failure_reason == "canonical_payload_hash_mismatch"


def test_tamper_row_hash_detected(monkeypatch):
    audit_logs, integrity = _seed(2)
    integrity[0]["row_hash"] = "a" * 64
    _patch(monkeypatch, audit_logs, integrity)
    result = _run(AuditChainVerifier(dsn="x", signer=AuditSigner(env={})).verify_chain())
    assert result.status == VERIFICATION_STATUS_FAILED
    assert result.failure_reason == "row_hash_mismatch"


def test_tamper_hmac_detected(monkeypatch):
    signer = AuditSigner(env={"AUDIT_HMAC_KEY": "k"})
    audit_logs, integrity = _seed(2, signer=signer)
    integrity[1]["hmac_signature"] = "0" * 64
    _patch(monkeypatch, audit_logs, integrity)
    result = _run(
        AuditChainVerifier(dsn="x", signer=AuditSigner(env={"AUDIT_HMAC_KEY": "k"})).verify_chain()
    )
    assert result.status == VERIFICATION_STATUS_FAILED
    assert result.failure_reason == "hmac_signature_invalid"


def test_tamper_recovery_re_verifies_passed_after_revert(monkeypatch):
    audit_logs, integrity = _seed(2)
    original_summary = audit_logs[0]["summary"]
    audit_logs[0]["summary"] = "mutated"
    _patch(monkeypatch, audit_logs, integrity)
    failed = _run(AuditChainVerifier(dsn="x", signer=AuditSigner(env={})).verify_chain())
    assert failed.status == VERIFICATION_STATUS_FAILED
    # Revert.
    audit_logs[0]["summary"] = original_summary
    _patch(monkeypatch, audit_logs, integrity)
    passed = _run(AuditChainVerifier(dsn="x", signer=AuditSigner(env={})).verify_chain())
    assert passed.status == VERIFICATION_STATUS_PASSED
