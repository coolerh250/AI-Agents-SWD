"""Stage 43 -- audit_log restore precheck validation."""

from __future__ import annotations

import asyncio

import asyncpg

from shared.sdk.audit_integrity.forensics import AuditChainForensicAnalyzer
from shared.sdk.audit_integrity.log_restore import AuditLogRestorer

from audit_chain_fixtures import InMemoryChain, forensic_report_for


def _run(coro):
    return asyncio.run(coro)


def _patch(monkeypatch, chain):
    async def _connect(*args, **kwargs):
        return chain.make_conn()

    monkeypatch.setattr(asyncpg, "connect", _connect)


def _report(chain):
    failed = _run(AuditChainForensicAnalyzer(dsn="postgresql://x").scan())
    return failed, forensic_report_for(failed)


def test_precheck_ok_for_test_tamper_residue(monkeypatch):
    chain = InMemoryChain()
    chain.seed(6)
    chain.tamper_summary(3)
    _patch(monkeypatch, chain)
    _, report = _report(chain)
    pc = _run(AuditLogRestorer(dsn="postgresql://x").precheck(report))
    assert pc.ok is True
    assert pc.affected_sequence_number == 3
    assert pc.before_contains_tamper_marker is True
    assert pc.after_contains_tamper_marker is False
    assert pc.hash_match_after is True
    assert pc.production_executed is False
    assert pc.missing_integrity_records == 0
    assert pc.prev_chain_linkage_intact is True


def test_precheck_rejects_wrong_root_cause(monkeypatch):
    chain = InMemoryChain()
    chain.seed(6)
    chain.tamper_summary(3)
    _patch(monkeypatch, chain)
    _, report = _report(chain)
    report["root_cause_classification"] = "unknown"
    pc = _run(AuditLogRestorer(dsn="postgresql://x").precheck(report))
    assert pc.ok is False
    assert "test_tamper_not_restored" in pc.reason


def test_precheck_rejects_repair_not_allowed(monkeypatch):
    chain = InMemoryChain()
    chain.seed(6)
    chain.tamper_summary(3)
    _patch(monkeypatch, chain)
    _, report = _report(chain)
    report["repair_allowed"] = False
    pc = _run(AuditLogRestorer(dsn="postgresql://x").precheck(report))
    assert pc.ok is False


def test_precheck_rejects_wrong_sequence(monkeypatch):
    chain = InMemoryChain()
    chain.seed(6)
    chain.tamper_summary(3)
    _patch(monkeypatch, chain)
    _, report = _report(chain)
    pc = _run(
        AuditLogRestorer(dsn="postgresql://x").precheck(report, sequence_number=99)
    )
    assert pc.ok is False
    assert "sequence" in pc.reason


def test_precheck_rejects_wrong_audit_log_id(monkeypatch):
    chain = InMemoryChain()
    chain.seed(6)
    chain.tamper_summary(3)
    _patch(monkeypatch, chain)
    _, report = _report(chain)
    pc = _run(
        AuditLogRestorer(dsn="postgresql://x").precheck(report, audit_log_id="not-a-match")
    )
    assert pc.ok is False
    assert "audit_log_id" in pc.reason


def test_precheck_rejects_missing_tamper_marker(monkeypatch):
    chain = InMemoryChain()
    chain.seed(6)
    # A real mutation without a recoverable marker -> forensics says
    # audit_log_mutated -> repair not allowed -> precheck rejects.
    chain.set_summary(3, "genuinely altered, no marker")
    _patch(monkeypatch, chain)
    _, report = _report(chain)
    pc = _run(AuditLogRestorer(dsn="postgresql://x").precheck(report))
    assert pc.ok is False


def test_precheck_rejects_production_executed(monkeypatch):
    chain = InMemoryChain()
    chain.seed(6, production_executed=True)
    chain.tamper_summary(3)
    _patch(monkeypatch, chain)
    failed = _run(AuditChainForensicAnalyzer(dsn="postgresql://x").scan())
    # Force the report to claim test_tamper to exercise the DB-level
    # production_executed guard inside precheck.
    report = forensic_report_for(failed)
    report["root_cause_classification"] = "test_tamper_not_restored"
    report["repair_allowed"] = True
    report["repair_risk"] = "low"
    pc = _run(AuditLogRestorer(dsn="postgresql://x").precheck(report))
    assert pc.ok is False
    assert "production_executed" in pc.reason
