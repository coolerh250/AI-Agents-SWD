"""Stage 43 -- restore reports never leak secrets or raw payload."""

from __future__ import annotations

import asyncio
import json

import asyncpg

from shared.sdk.audit_integrity.forensics import AuditChainForensicAnalyzer
from shared.sdk.audit_integrity.log_restore import AuditLogRestorer

from audit_chain_fixtures import InMemoryChain, forensic_report_for

SECRETS = ["ghp_abcdefgh12345678ijklmnop", "sk-abcdefgh12345678ijklmnop", "xoxb-1-2-aaaaaaaa"]


def _run(coro):
    return asyncio.run(coro)


def _patch(monkeypatch, chain):
    async def _connect(*args, **kwargs):
        return chain.make_conn()

    monkeypatch.setattr(asyncpg, "connect", _connect)


def test_restore_report_has_no_raw_summary(monkeypatch):
    chain = InMemoryChain()
    chain.seed(6)
    # Put a secret-looking token in the (synthetic) tampered summary.
    chain.set_summary(3, "blocked ghp_abcdefgh12345678ijklmnop [TAMPER-SIMULATION]")
    _patch(monkeypatch, chain)
    failed = _run(AuditChainForensicAnalyzer(dsn="postgresql://x").scan())
    report = forensic_report_for(failed)
    restorer = AuditLogRestorer(dsn="postgresql://x")
    pc = _run(restorer.precheck(report))
    result = _run(restorer.apply(pc, approved=True, dry_run=True))
    blob = json.dumps(result)
    for s in SECRETS:
        assert s not in blob, f"secret {s} leaked into restore report"
    # The report carries hashes, not the raw summary text.
    assert "before_summary_hash" in blob
    assert "ghp_" not in blob


def test_precheck_dict_no_raw_summary():
    from shared.sdk.audit_integrity.log_restore import RestorePrecheck

    pc = RestorePrecheck(ok=True, before_summary_hash="h1", after_summary_hash="h2")
    pc._current_summary = "blocked ghp_secrettoken123456789 [TAMPER-SIMULATION]"
    blob = json.dumps(pc.to_dict())
    assert "ghp_secrettoken" not in blob
    assert "_current_summary" not in blob


def test_log_restore_module_no_key_reads():
    import shared.sdk.audit_integrity.log_restore as m

    src = open(m.__file__, encoding="utf-8").read()
    assert "AUDIT_HMAC_KEY" not in src
    assert "r.hmac_signature" not in src
