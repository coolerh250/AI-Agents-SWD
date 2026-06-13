"""Stage 42 -- forensic analyzer scan + per-record recompute."""

from __future__ import annotations

import asyncio

import asyncpg

from shared.sdk.audit_integrity.forensics import (
    AuditChainForensicAnalyzer,
    FAILURE_CANONICAL_PAYLOAD_HASH,
    ROOT_CAUSE_AUDIT_LOG_MUTATED,
    ROOT_CAUSE_TEST_TAMPER_NOT_RESTORED,
    analyse_record,
)

from audit_chain_fixtures import InMemoryChain


def _run(coro):
    return asyncio.run(coro)


def _patch(monkeypatch, chain: InMemoryChain):
    async def _connect(*args, **kwargs):
        return chain.make_conn()

    monkeypatch.setattr(asyncpg, "connect", _connect)


def test_scan_clean_chain_returns_no_failures(monkeypatch):
    chain = InMemoryChain()
    chain.seed(5)
    _patch(monkeypatch, chain)
    failed = _run(AuditChainForensicAnalyzer(dsn="postgresql://x").scan())
    assert failed == []


def test_scan_detects_tampered_record(monkeypatch):
    chain = InMemoryChain()
    chain.seed(5)
    chain.tamper_summary(3)  # appends [TAMPER-SIMULATION] to seq 3
    _patch(monkeypatch, chain)
    failed = _run(AuditChainForensicAnalyzer(dsn="postgresql://x").scan())
    assert len(failed) == 1
    a = failed[0]
    assert a.sequence_number == 3
    assert FAILURE_CANONICAL_PAYLOAD_HASH in a.failure_types
    assert a.tamper_marker_detected is True
    assert a.recovered_original_matches is True
    assert a.suspected_root_cause == ROOT_CAUSE_TEST_TAMPER_NOT_RESTORED


def test_analyse_record_canonical_mismatch_detected():
    a = analyse_record(
        sequence_number=2,
        audit_log_id="abc",
        audit_log_row={
            "task_id": "T",
            "agent": "x",
            "decision_type": "d",
            "summary": "mutated text",
            "result": "ok",
            "artifact_refs": {"production_executed": False},
            "created_at": "2026-06-01T00:00:00+00:00",
        },
        stored_canonical_payload_hash="deadbeef",
        stored_row_hash="rr",
        stored_prev_hash="pp",
        signature_status="signing_key_not_configured",
        expected_prev_record_hash="pp",
    )
    assert FAILURE_CANONICAL_PAYLOAD_HASH in a.failure_types
    # No marker + can't recover original -> audit_log mutated.
    assert a.suspected_root_cause == ROOT_CAUSE_AUDIT_LOG_MUTATED
    assert a.repairable is False


def test_analyse_record_tamper_marker_synthetic_is_repairable():
    # Build a record whose stored hash matches the ORIGINAL (no marker).
    from shared.sdk.audit_integrity import build_canonical_payload, compute_payload_hash

    base = {
        "task_id": "smoke",
        "agent": "github-automation",
        "decision_type": "github_real_test_blocked",
        "summary": "blocked: missing_github_token",
        "result": "blocked",
        "artifact_refs": {"production_executed": False},
        "created_at": "2026-06-13T05:57:57+00:00",
    }
    stored = compute_payload_hash(build_canonical_payload({"audit_log_id": "id", **base}))
    tampered = dict(base)
    tampered["summary"] = base["summary"] + " [TAMPER-SIMULATION]"
    a = analyse_record(
        sequence_number=10,
        audit_log_id="id",
        audit_log_row=tampered,
        stored_canonical_payload_hash=stored,
        stored_row_hash="rr",
        stored_prev_hash="pp",
        signature_status="signing_key_not_configured",
        expected_prev_record_hash="pp",
    )
    assert a.tamper_marker_detected is True
    assert a.recovered_original_matches is True
    assert a.suspected_root_cause == ROOT_CAUSE_TEST_TAMPER_NOT_RESTORED
    assert a.repairable is True


def test_record_analysis_redacts_summary_and_serialises():
    a = analyse_record(
        sequence_number=1,
        audit_log_id="id",
        audit_log_row={
            "task_id": "T",
            "agent": "x",
            "decision_type": "d",
            "summary": "leak ghp_abcdefgh12345678ZZZ tail",
            "result": "ok",
            "artifact_refs": {},
            "created_at": "2026-06-01T00:00:00+00:00",
        },
        stored_canonical_payload_hash="x",
        stored_row_hash="y",
        stored_prev_hash=None,
        signature_status="signing_key_not_configured",
        expected_prev_record_hash=None,
    )
    d = a.to_dict()
    assert "ghp_" not in d["summary_redacted"]
    assert "[REDACTED]" in d["summary_redacted"]
