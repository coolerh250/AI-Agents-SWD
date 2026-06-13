"""Stage 42 -- unsafe / disallowed repairs make no DB change."""

from __future__ import annotations

import asyncio

import asyncpg

from shared.sdk.audit_integrity.forensics import (
    AuditChainForensicAnalyzer,
    ROOT_CAUSE_AUDIT_LOG_MUTATED,
    ROOT_CAUSE_UNKNOWN,
)
from shared.sdk.audit_integrity.repair import (
    AuditChainRepairer,
    REPAIR_STATUS_SKIPPED_UNSAFE,
    RepairPlan,
    plan_repair,
)

from audit_chain_fixtures import InMemoryChain


def _run(coro):
    return asyncio.run(coro)


def _patch(monkeypatch, chain):
    async def _connect(*args, **kwargs):
        return chain.make_conn()

    monkeypatch.setattr(asyncpg, "connect", _connect)


def test_disallowed_plan_skips_unsafe(monkeypatch):
    chain = InMemoryChain()
    chain.seed(6)
    chain.tamper_summary(3)
    _patch(monkeypatch, chain)
    failed = _run(AuditChainForensicAnalyzer(dsn="postgresql://x").scan())
    # Force an unknown root cause -> plan not allowed.
    plan = plan_repair(
        failed=failed,
        root_cause=ROOT_CAUSE_UNKNOWN,
        repair_allowed=True,
        repair_risk="high",
        chain_tail_sequence=6,
        reason="unknown root cause -> repair blocked",
    )
    assert plan.repair_allowed is False
    repairer = AuditChainRepairer(dsn="postgresql://x")
    result = _run(repairer.apply(plan, approved=True, dry_run=False))
    assert result["status"] == REPAIR_STATUS_SKIPPED_UNSAFE
    assert result["audit_integrity_records_modified"] is False
    # Tamper still present.
    failed_after = _run(AuditChainForensicAnalyzer(dsn="postgresql://x").scan())
    assert len(failed_after) == 1


def test_audit_log_mutated_blocks_repair(monkeypatch):
    chain = InMemoryChain()
    chain.seed(5)
    # A real mutation with no recoverable marker.
    chain.set_summary(2, "genuinely altered content")
    _patch(monkeypatch, chain)
    failed = _run(AuditChainForensicAnalyzer(dsn="postgresql://x").scan())
    assert len(failed) == 1
    assert failed[0].suspected_root_cause == ROOT_CAUSE_AUDIT_LOG_MUTATED
    plan = plan_repair(
        failed=failed,
        root_cause=ROOT_CAUSE_AUDIT_LOG_MUTATED,
        repair_allowed=False,
        repair_risk="high",
        chain_tail_sequence=5,
    )
    repairer = AuditChainRepairer(dsn="postgresql://x")
    result = _run(repairer.apply(plan, approved=True, dry_run=False))
    assert result["status"] == REPAIR_STATUS_SKIPPED_UNSAFE
    assert result["audit_integrity_records_modified"] is False


def test_empty_plan_skips_unsafe():
    plan = RepairPlan(
        root_cause="unknown",
        repair_allowed=False,
        repair_risk="low",
        first_failed_sequence=None,
        affected_sequences=[],
        reason="no failed records",
    )
    repairer = AuditChainRepairer(dsn="postgresql://x")
    result = _run(repairer.apply(plan, approved=True, dry_run=False))
    assert result["status"] == REPAIR_STATUS_SKIPPED_UNSAFE
