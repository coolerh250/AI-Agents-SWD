"""Stage 43 -- unsafe restores are rejected with no DB change."""

from __future__ import annotations

import asyncio

import asyncpg

from shared.sdk.audit_integrity.forensics import AuditChainForensicAnalyzer
from shared.sdk.audit_integrity.log_restore import (
    AuditLogRestorer,
    RESTORE_STATUS_REJECTED_UNSAFE,
    RestorePrecheck,
)

from audit_chain_fixtures import InMemoryChain, forensic_report_for


def _run(coro):
    return asyncio.run(coro)


def _patch(monkeypatch, chain):
    async def _connect(*args, **kwargs):
        return chain.make_conn()

    monkeypatch.setattr(asyncpg, "connect", _connect)


def test_apply_rejects_failed_precheck():
    pc = RestorePrecheck(ok=False, reason="root_cause unknown")
    result = _run(AuditLogRestorer(dsn="postgresql://x").apply(pc, approved=True, dry_run=False))
    assert result["status"] == RESTORE_STATUS_REJECTED_UNSAFE
    assert result["audit_logs_modified_count"] == 0
    assert result["audit_integrity_records_modified_count"] == 0


def test_non_synthetic_mutation_rejected(monkeypatch):
    chain = InMemoryChain()
    chain.seed(6)
    chain.set_summary(3, "real mutation no marker")
    _patch(monkeypatch, chain)
    failed = _run(AuditChainForensicAnalyzer(dsn="postgresql://x").scan())
    report = forensic_report_for(failed)
    restorer = AuditLogRestorer(dsn="postgresql://x")
    pc = _run(restorer.precheck(report))
    assert pc.ok is False
    result = _run(restorer.apply(pc, approved=True, dry_run=False))
    assert result["status"] == RESTORE_STATUS_REJECTED_UNSAFE
    # The contaminated chain is untouched.
    failed_after = _run(AuditChainForensicAnalyzer(dsn="postgresql://x").scan())
    assert len(failed_after) == 1


def test_clean_chain_has_nothing_to_restore(monkeypatch):
    chain = InMemoryChain()
    chain.seed(5)
    _patch(monkeypatch, chain)
    failed = _run(AuditChainForensicAnalyzer(dsn="postgresql://x").scan())
    report = forensic_report_for(failed)  # no failed records
    restorer = AuditLogRestorer(dsn="postgresql://x")
    pc = _run(restorer.precheck(report))
    assert pc.ok is False
    result = _run(restorer.apply(pc, approved=True, dry_run=False))
    assert result["status"] == RESTORE_STATUS_REJECTED_UNSAFE
