"""Stage 43 -- approved restore on a SYNTHETIC chain.

Restores ONE audit_logs.summary, modifies zero integrity records, appends a
restore event, and leaves the chain verifying. Never touches a real DB.
"""

from __future__ import annotations

import asyncio

import asyncpg

from shared.sdk.audit_integrity.forensics import AuditChainForensicAnalyzer
from shared.sdk.audit_integrity.log_restore import (
    AuditLogRestorer,
    RESTORE_STATUS_COMPLETED,
)

from audit_chain_fixtures import InMemoryChain, forensic_report_for


def _run(coro):
    return asyncio.run(coro)


def _patch(monkeypatch, chain):
    async def _connect(*args, **kwargs):
        return chain.make_conn()

    monkeypatch.setattr(asyncpg, "connect", _connect)


def _setup(monkeypatch, n=6, seq=3):
    chain = InMemoryChain()
    chain.seed(n)
    chain.tamper_summary(seq)
    _patch(monkeypatch, chain)
    failed = _run(AuditChainForensicAnalyzer(dsn="postgresql://x").scan())
    report = forensic_report_for(failed)
    restorer = AuditLogRestorer(dsn="postgresql://x")
    pc = _run(restorer.precheck(report))
    return chain, restorer, pc


def test_approved_restore_completes_and_chain_clean(monkeypatch):
    chain, restorer, pc = _setup(monkeypatch)
    integrity_count_before = len(chain.integrity)

    result = _run(restorer.apply(pc, approved=True, dry_run=False))

    assert result["status"] == RESTORE_STATUS_COMPLETED
    assert result["audit_logs_modified_count"] == 1
    assert result["audit_integrity_records_modified_count"] == 0
    assert result["after_contains_tamper_marker"] is False
    assert result["hash_match_after"] is True
    # A restore event was appended to the chain tail (+1 audit_log, +1 integrity).
    assert len(chain.integrity) == integrity_count_before + 1
    assert result["restore_audit_event_id"] is not None
    # Chain now has no failing records.
    failed_after = _run(AuditChainForensicAnalyzer(dsn="postgresql://x").scan())
    assert failed_after == []


def test_restore_modifies_summary_only(monkeypatch):
    chain, restorer, pc = _setup(monkeypatch)
    tampered_id = chain.synthetic_tamper_audit_id()
    # Existing integrity records' hashes must be unchanged by the restore.
    integ_before = {r["integrity_id"]: dict(r) for r in chain.integrity}
    _run(restorer.apply(pc, approved=True, dry_run=False))
    for iid, before in integ_before.items():
        after = next(r for r in chain.integrity if r["integrity_id"] == iid)
        assert after["canonical_payload_hash"] == before["canonical_payload_hash"]
        assert after["row_hash"] == before["row_hash"]
        assert after["prev_hash"] == before["prev_hash"]
    # The summary no longer carries the marker.
    assert not chain.audit_logs[
        next(k for k in chain.audit_logs if str(k) == tampered_id)
    ]["summary"].endswith("[TAMPER-SIMULATION]")


def test_restore_event_enters_chain(monkeypatch):
    chain, restorer, pc = _setup(monkeypatch)
    result = _run(restorer.apply(pc, approved=True, dry_run=False))
    event_id = result["restore_audit_event_id"]
    # The restore event has both an audit_log row and an integrity record.
    assert any(str(k) == event_id for k in chain.audit_logs)
    assert any(str(r["audit_log_id"]) == event_id for r in chain.integrity)


def test_restore_verifier_passes_after(monkeypatch):
    chain, restorer, pc = _setup(monkeypatch, n=8, seq=5)
    result = _run(restorer.apply(pc, approved=True, dry_run=False))
    assert result["status"] == RESTORE_STATUS_COMPLETED
    # full forensic scan finds nothing wrong now
    failed_after = _run(AuditChainForensicAnalyzer(dsn="postgresql://x").scan())
    assert failed_after == []
