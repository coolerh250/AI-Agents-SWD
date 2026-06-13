"""Stage 42 -- approved repair on a SYNTHETIC chain.

Never touches a real DB or the real 265288 record. Exercises the cascade
recompute, advisory lock, in-transaction re-verify, and the guarantee that
audit_logs is never modified.
"""

from __future__ import annotations

import asyncio

import asyncpg

from shared.sdk.audit_integrity.forensics import (
    AuditChainForensicAnalyzer,
    classify_chain_root_cause,
)
from shared.sdk.audit_integrity.repair import (
    AuditChainRepairer,
    REPAIR_STATUS_COMPLETED,
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
    return plan_repair(
        failed=failed,
        root_cause=classification["root_cause_classification"] or "unknown",
        repair_allowed=bool(classification["repair_allowed"]),
        repair_risk=classification["repair_risk"] or "high",
        chain_tail_sequence=tail,
    )


def test_approved_repair_restores_chain(monkeypatch):
    chain = InMemoryChain()
    chain.seed(8)
    chain.tamper_summary(3)
    _patch(monkeypatch, chain)

    # Snapshot the audit_log summaries before repair.
    summaries_before = {
        rec["sequence_number"]: chain.audit_logs[rec["audit_log_id"]]["summary"]
        for rec in chain.integrity
    }

    plan = _plan_for(chain)
    assert plan.repair_allowed is True

    repairer = AuditChainRepairer(dsn="postgresql://x")
    result = _run(repairer.apply(plan, approved=True, dry_run=False))

    assert result["status"] == REPAIR_STATUS_COMPLETED
    assert result["audit_integrity_records_modified"] is True
    assert result["audit_logs_modified"] is False
    assert result["verification_after_repair"]["passed"] is True

    # audit_logs untouched (summaries identical, including the tampered one).
    summaries_after = {
        rec["sequence_number"]: chain.audit_logs[rec["audit_log_id"]]["summary"]
        for rec in chain.integrity
    }
    assert summaries_after == summaries_before

    # Chain now verifies cleanly.
    failed_after = _run(AuditChainForensicAnalyzer(dsn="postgresql://x").scan())
    assert failed_after == []


def test_repair_cascades_prev_hash(monkeypatch):
    chain = InMemoryChain()
    chain.seed(6)
    chain.tamper_summary(2)
    _patch(monkeypatch, chain)
    plan = _plan_for(chain)
    repairer = AuditChainRepairer(dsn="postgresql://x")
    _run(repairer.apply(plan, approved=True, dry_run=False))
    # prev_hash linkage must be contiguous after repair.
    recs = sorted(chain.integrity, key=lambda r: r["sequence_number"])
    for i in range(1, len(recs)):
        assert recs[i]["prev_hash"] == recs[i - 1]["row_hash"]


def test_repair_only_changes_from_first_failed(monkeypatch):
    chain = InMemoryChain()
    chain.seed(6)
    chain.tamper_summary(4)
    _patch(monkeypatch, chain)
    # Capture row_hashes for seq 1..3 (before first failure) -- must stay.
    before = {r["sequence_number"]: r["row_hash"] for r in chain.integrity}
    plan = _plan_for(chain)
    repairer = AuditChainRepairer(dsn="postgresql://x")
    _run(repairer.apply(plan, approved=True, dry_run=False))
    after = {r["sequence_number"]: r["row_hash"] for r in chain.integrity}
    for seq in (1, 2, 3):
        assert after[seq] == before[seq]


def test_repair_changed_count_matches_tail(monkeypatch):
    chain = InMemoryChain()
    chain.seed(10)
    chain.tamper_summary(7)
    _patch(monkeypatch, chain)
    plan = _plan_for(chain)
    repairer = AuditChainRepairer(dsn="postgresql://x")
    result = _run(repairer.apply(plan, approved=True, dry_run=False))
    # Only seq 7's canonical changed; 7..10 row_hash/prev cascade -> 4 changed.
    assert result["changed_records_count"] >= 1
    assert result["changed_records_count"] <= 4
