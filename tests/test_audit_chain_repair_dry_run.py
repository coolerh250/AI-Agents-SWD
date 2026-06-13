"""Stage 42 -- repair dry-run makes no DB change."""

from __future__ import annotations

import asyncio

import asyncpg

from shared.sdk.audit_integrity.forensics import (
    AuditChainForensicAnalyzer,
    classify_chain_root_cause,
)
from shared.sdk.audit_integrity.repair import (
    AuditChainRepairer,
    REPAIR_STATUS_APPROVAL_REQUIRED,
    REPAIR_STATUS_DRY_RUN,
    plan_repair,
)

from audit_chain_fixtures import InMemoryChain


def _run(coro):
    return asyncio.run(coro)


def _patch(monkeypatch, chain):
    async def _connect(*args, **kwargs):
        return chain.make_conn()

    monkeypatch.setattr(asyncpg, "connect", _connect)


def _plan_for(chain):
    failed = _run(AuditChainForensicAnalyzer(dsn="postgresql://x").scan())
    classification = classify_chain_root_cause(failed)
    tail = _run(AuditChainRepairer(dsn="postgresql://x").chain_tail_sequence())
    return failed, plan_repair(
        failed=failed,
        root_cause=classification["root_cause_classification"] or "unknown",
        repair_allowed=bool(classification["repair_allowed"]),
        repair_risk=classification["repair_risk"] or "high",
        chain_tail_sequence=tail,
        reason=classification["repair_policy_reason"] or "",
    )


def test_dry_run_default_no_update(monkeypatch):
    chain = InMemoryChain()
    chain.seed(6)
    chain.tamper_summary(3)
    _patch(monkeypatch, chain)
    _, plan = _plan_for(chain)
    repairer = AuditChainRepairer(dsn="postgresql://x")
    # dry-run even though approved.
    result = _run(repairer.apply(plan, approved=True, dry_run=True))
    assert result["status"] == REPAIR_STATUS_DRY_RUN
    assert result["audit_integrity_records_modified"] is False
    assert result["changed_records_count"] == 0
    # Chain still has the tamper -> still 1 failed record.
    failed_after = _run(AuditChainForensicAnalyzer(dsn="postgresql://x").scan())
    assert len(failed_after) == 1


def test_not_approved_is_approval_required(monkeypatch):
    chain = InMemoryChain()
    chain.seed(6)
    chain.tamper_summary(3)
    _patch(monkeypatch, chain)
    _, plan = _plan_for(chain)
    repairer = AuditChainRepairer(dsn="postgresql://x")
    result = _run(repairer.apply(plan, approved=False, dry_run=True))
    assert result["status"] == REPAIR_STATUS_APPROVAL_REQUIRED
    assert result["audit_logs_modified"] is False
    assert result["audit_integrity_records_modified"] is False


def test_dry_run_preview_has_before_after(monkeypatch):
    chain = InMemoryChain()
    chain.seed(6)
    chain.tamper_summary(3)
    _patch(monkeypatch, chain)
    _, plan = _plan_for(chain)
    repairer = AuditChainRepairer(dsn="postgresql://x")
    result = _run(repairer.apply(plan, approved=True, dry_run=True))
    # Preview shows what WOULD change (seq 3..tail), without writing.
    assert result["before_hash_summary"]
    assert result["after_hash_summary"]
    assert result["audit_integrity_records_modified"] is False
