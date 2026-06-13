"""Stage 43 -- restore dry-run / approval gating makes no DB change."""

from __future__ import annotations

import asyncio

import asyncpg

from shared.sdk.audit_integrity.forensics import AuditChainForensicAnalyzer
from shared.sdk.audit_integrity.log_restore import (
    AuditLogRestorer,
    RESTORE_STATUS_APPROVAL_REQUIRED,
    RESTORE_STATUS_DRY_RUN,
)

from audit_chain_fixtures import InMemoryChain, forensic_report_for


def _run(coro):
    return asyncio.run(coro)


def _patch(monkeypatch, chain):
    async def _connect(*args, **kwargs):
        return chain.make_conn()

    monkeypatch.setattr(asyncpg, "connect", _connect)


def _setup(monkeypatch):
    chain = InMemoryChain()
    chain.seed(6)
    chain.tamper_summary(3)
    _patch(monkeypatch, chain)
    failed = _run(AuditChainForensicAnalyzer(dsn="postgresql://x").scan())
    report = forensic_report_for(failed)
    restorer = AuditLogRestorer(dsn="postgresql://x")
    pc = _run(restorer.precheck(report))
    return chain, restorer, pc


def test_dry_run_no_db_change(monkeypatch):
    chain, restorer, pc = _setup(monkeypatch)
    summary_before = chain.audit_logs[list(chain.audit_logs)[2]]["summary"]
    result = _run(restorer.apply(pc, approved=True, dry_run=True))
    assert result["status"] == RESTORE_STATUS_DRY_RUN
    assert result["audit_logs_modified_count"] == 0
    assert result["audit_integrity_records_modified_count"] == 0
    # tamper marker still present (no change).
    failed_after = _run(AuditChainForensicAnalyzer(dsn="postgresql://x").scan())
    assert len(failed_after) == 1
    assert summary_before.endswith("[TAMPER-SIMULATION]")


def test_not_approved_is_approval_required(monkeypatch):
    chain, restorer, pc = _setup(monkeypatch)
    result = _run(restorer.apply(pc, approved=False, dry_run=True))
    assert result["status"] == RESTORE_STATUS_APPROVAL_REQUIRED
    assert result["audit_logs_modified_count"] == 0
    assert result["audit_integrity_records_modified_count"] == 0


def test_dry_run_reports_hashes(monkeypatch):
    _, restorer, pc = _setup(monkeypatch)
    result = _run(restorer.apply(pc, approved=True, dry_run=True))
    assert result["hash_match_after"] is True
    assert result["before_summary_hash"] != result["after_summary_hash"]
    assert result["stored_canonical_payload_hash"] == (
        result["recomputed_after_canonical_payload_hash"]
    )
