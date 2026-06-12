"""Stage 34 -- AuditIntegrityStore.backfill_missing_integrity_records.

We back the asyncpg surface with a small in-memory fake so backfill +
chain building can be exercised without Postgres. The fake honours the
single SELECT/INSERT shapes the store actually issues.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import asyncpg

from shared.sdk.audit_integrity import AuditIntegrityStore, AuditSigner
from shared.sdk.audit_integrity.models import SIGNATURE_STATUS_NOT_CONFIGURED


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeRow(dict):
    def __getitem__(self, key: str):
        return dict.__getitem__(self, key)


class _FakeTxn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Fixture:
    """Holds the two tables in memory and patches asyncpg.connect."""

    def __init__(self):
        self.audit_logs: list[dict[str, Any]] = []
        self.integrity_records: list[dict[str, Any]] = []
        self.verification_runs: list[dict[str, Any]] = []

    def add_audit_log(self, summary: str = "ok") -> str:
        audit_id = uuid4()
        self.audit_logs.append(
            {
                "id": audit_id,
                "task_id": f"T-{summary}",
                "agent": "x",
                "decision_type": "d",
                "summary": summary,
                "result": "ok",
                "artifact_refs": {"k": summary},
                "created_at": datetime(2026, 6, 1, tzinfo=timezone.utc)
                + timedelta(seconds=len(self.audit_logs)),
            }
        )
        return str(audit_id)

    def make_conn(self):
        fx = self

        class _Conn:
            def transaction(self_inner):
                return _FakeTxn()

            async def fetchval(self_inner, sql: str, *params):
                if "FROM audit_logs" in sql and "COUNT" in sql:
                    return len(fx.audit_logs)
                if "FROM audit_integrity_records" in sql and "COUNT" in sql:
                    chain_version = params[0] if params else 1
                    return sum(
                        1 for r in fx.integrity_records if r["chain_version"] == chain_version
                    )
                return 0

            async def fetchrow(self_inner, sql: str, *params):
                if "FROM audit_integrity_records" in sql and "WHERE audit_log_id = $1" in sql:
                    aid = params[0]
                    if isinstance(aid, str):
                        aid = UUID(aid)
                    for r in fx.integrity_records:
                        if r["audit_log_id"] == aid:
                            return _FakeRow(r)
                    # uniqueness probe returns None when not found
                    return None
                if "SELECT sequence_number, row_hash" in sql:
                    chain_version = params[0]
                    rows = [r for r in fx.integrity_records if r["chain_version"] == chain_version]
                    if not rows:
                        return None
                    latest = max(rows, key=lambda r: r["sequence_number"])
                    return _FakeRow(
                        {
                            "sequence_number": latest["sequence_number"],
                            "row_hash": latest["row_hash"],
                        }
                    )
                if "INSERT INTO audit_integrity_records" in sql:
                    (
                        audit_log_id,
                        chain_version,
                        sequence_number,
                        prev_hash,
                        row_hash,
                        canonical_payload_hash,
                        hmac_signature,
                        signing_key_id,
                        signature_status,
                        integrity_status,
                    ) = params
                    aid = audit_log_id
                    if isinstance(aid, str):
                        aid = UUID(aid)
                    record = {
                        "integrity_id": uuid4(),
                        "audit_log_id": aid,
                        "chain_version": chain_version,
                        "sequence_number": sequence_number,
                        "prev_hash": prev_hash,
                        "row_hash": row_hash,
                        "canonical_payload_hash": canonical_payload_hash,
                        "hmac_signature": hmac_signature,
                        "signing_key_id": signing_key_id,
                        "signature_status": signature_status,
                        "integrity_status": integrity_status,
                        "created_at": datetime.now(timezone.utc),
                    }
                    fx.integrity_records.append(record)
                    return _FakeRow(record)
                return None

            async def fetch(self_inner, sql: str, *params):
                if "LEFT JOIN audit_integrity_records" in sql:
                    # Missing integrity records: audit rows lacking
                    # an entry in fx.integrity_records.
                    have = {r["audit_log_id"] for r in fx.integrity_records}
                    out = []
                    for a in fx.audit_logs:
                        if a["id"] not in have:
                            out.append(_FakeRow(a))
                    out.sort(key=lambda r: (r["created_at"], str(r["id"])))
                    return out
                return []

            async def execute(self_inner, sql: str, *params):
                # Accept the Stage 39 advisory lock SELECT + any other
                # execute() calls (e.g. keyring metadata UPSERT).
                return None

            async def close(self_inner):
                return None

        return _Conn()

    def patch(self, monkeypatch):
        async def _connect(*args, **kwargs):
            return self.make_conn()

        monkeypatch.setattr(asyncpg, "connect", _connect)


def test_backfill_creates_records_in_sorted_order(monkeypatch):
    fx = _Fixture()
    a1 = fx.add_audit_log("first")
    a2 = fx.add_audit_log("second")
    a3 = fx.add_audit_log("third")
    fx.patch(monkeypatch)

    store = AuditIntegrityStore(dsn="postgresql://x", signer=AuditSigner(env={}))
    summary = _run(store.backfill_missing_integrity_records())
    assert summary["audit_logs"] == 3
    assert summary["integrity_records_before"] == 0
    assert summary["created"] == 3
    assert summary["integrity_records_after"] == 3
    assert summary["not_configured"] == 3  # no AUDIT_HMAC_KEY in env

    # Chain is contiguous + ordered by audit_logs.created_at, id.
    seqs = sorted(r["sequence_number"] for r in fx.integrity_records)
    assert seqs == [1, 2, 3]
    # prev_hash chain matches.
    by_seq = {r["sequence_number"]: r for r in fx.integrity_records}
    assert by_seq[1]["prev_hash"] is None
    assert by_seq[2]["prev_hash"] == by_seq[1]["row_hash"]
    assert by_seq[3]["prev_hash"] == by_seq[2]["row_hash"]
    # Records map back to audit_log ids.
    audit_ids_in_order = [str(a) for a in (a1, a2, a3)]
    integrity_ids_in_order = [str(by_seq[i]["audit_log_id"]) for i in (1, 2, 3)]
    assert audit_ids_in_order == integrity_ids_in_order


def test_backfill_idempotent_second_run_is_noop(monkeypatch):
    fx = _Fixture()
    fx.add_audit_log("only")
    fx.patch(monkeypatch)

    store = AuditIntegrityStore(dsn="postgresql://x", signer=AuditSigner(env={}))
    first = _run(store.backfill_missing_integrity_records())
    second = _run(store.backfill_missing_integrity_records())
    assert first["created"] == 1
    assert second["created"] == 0
    assert second["integrity_records_after"] == 1


def test_backfill_records_signing_status_when_hmac_key_present(monkeypatch):
    fx = _Fixture()
    fx.add_audit_log("signed")
    fx.patch(monkeypatch)

    signer = AuditSigner(env={"AUDIT_HMAC_KEY": "k"})
    store = AuditIntegrityStore(dsn="postgresql://x", signer=signer)
    summary = _run(store.backfill_missing_integrity_records())
    assert summary["signed"] == 1
    assert summary["not_configured"] == 0
    assert fx.integrity_records[0]["signature_status"] == "signed"
    assert fx.integrity_records[0]["hmac_signature"] is not None


def test_backfill_unsigned_status_label_is_signing_key_not_configured(monkeypatch):
    fx = _Fixture()
    fx.add_audit_log("unsigned")
    fx.patch(monkeypatch)

    signer = AuditSigner(env={})  # no key
    store = AuditIntegrityStore(dsn="postgresql://x", signer=signer)
    _run(store.backfill_missing_integrity_records())
    assert fx.integrity_records[0]["signature_status"] == SIGNATURE_STATUS_NOT_CONFIGURED
    assert fx.integrity_records[0]["hmac_signature"] is None
