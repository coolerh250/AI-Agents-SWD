"""Stage 34 -- AuditIntegrityStore tests with stubbed asyncpg."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import asyncpg

from shared.sdk.audit_integrity import AuditIntegrityStore, AuditSigner


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeRow(dict):
    def __getitem__(self, key: str) -> Any:
        return dict.__getitem__(self, key)


class _FakeTxn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeConn:
    last_sql: str = ""
    last_params: tuple = ()

    def __init__(self, scripted_responses=None):
        # scripted_responses is a list of (kind, value).
        # kind: 'fetchrow' or 'fetch' or 'fetchval'
        self._scripted = list(scripted_responses or [])

    def transaction(self):
        return _FakeTxn()

    async def fetchrow(self, sql: str, *params: Any):
        _FakeConn.last_sql = sql
        _FakeConn.last_params = params
        # Pop matching scripted entry.
        for i, (kind, value) in enumerate(self._scripted):
            if kind == "fetchrow":
                self._scripted.pop(i)
                return value
        return None

    async def fetch(self, sql: str, *params: Any):
        _FakeConn.last_sql = sql
        _FakeConn.last_params = params
        for i, (kind, value) in enumerate(self._scripted):
            if kind == "fetch":
                self._scripted.pop(i)
                return value
        return []

    async def fetchval(self, sql: str, *params: Any):
        _FakeConn.last_sql = sql
        _FakeConn.last_params = params
        for i, (kind, value) in enumerate(self._scripted):
            if kind == "fetchval":
                self._scripted.pop(i)
                return value
        return 0

    async def execute(self, sql: str, *params: Any):
        _FakeConn.last_sql = sql
        _FakeConn.last_params = params
        return None

    async def close(self):
        return None


def _patch_connect(monkeypatch, conn: _FakeConn) -> None:
    async def _connect(*args, **kwargs):
        return conn

    monkeypatch.setattr(asyncpg, "connect", _connect)


def _audit_row(audit_id: str = "audit-1") -> dict[str, Any]:
    return {
        "audit_id": audit_id,
        "task_id": "T",
        "agent": "a",
        "decision_type": "d",
        "summary": "s",
        "result": "ok",
        "artifact_refs": {"k": "v"},
        "created_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
    }


def _integrity_row(seq: int, prev_hash: str | None, row_hash: str) -> _FakeRow:
    return _FakeRow(
        {
            "integrity_id": uuid4(),
            "audit_log_id": "audit-1",
            "chain_version": 1,
            "sequence_number": seq,
            "prev_hash": prev_hash,
            "row_hash": row_hash,
            "canonical_payload_hash": "ph-" + str(seq),
            "hmac_signature": None,
            "signing_key_id": "unsigned",
            "signature_status": "unsigned",
            "integrity_status": "active",
            "created_at": datetime.now(timezone.utc),
        }
    )


def test_create_integrity_record_first_row_uses_genesis_prev(monkeypatch):
    conn = _FakeConn(
        scripted_responses=[
            ("fetchrow", None),  # uniqueness probe -> not seen
            ("fetchrow", None),  # latest -> no rows yet
            ("fetchrow", _integrity_row(1, None, "row-hash-1")),  # INSERT RETURNING
        ]
    )
    _patch_connect(monkeypatch, conn)
    store = AuditIntegrityStore(dsn="postgresql://x", signer=AuditSigner(env={}))
    out = _run(store.create_integrity_record_for_audit_log(_audit_row()))
    assert out is not None
    assert out.sequence_number == 1
    assert out.prev_hash is None
    assert "INSERT INTO audit_integrity_records" in _FakeConn.last_sql


def test_create_integrity_record_idempotent_when_already_exists(monkeypatch):
    conn = _FakeConn(
        scripted_responses=[
            ("fetchrow", _FakeRow({"exists": 1})),  # uniqueness probe -> found
        ]
    )
    _patch_connect(monkeypatch, conn)
    store = AuditIntegrityStore(dsn="postgresql://x", signer=AuditSigner(env={}))
    out = _run(store.create_integrity_record_for_audit_log(_audit_row()))
    assert out is None  # no insert


def test_get_latest_integrity_record_returns_row(monkeypatch):
    row = _integrity_row(42, "p", "r")
    conn = _FakeConn(scripted_responses=[("fetchrow", row)])
    _patch_connect(monkeypatch, conn)
    store = AuditIntegrityStore(dsn="postgresql://x")
    out = _run(store.get_latest_integrity_record())
    assert out is not None
    assert out.sequence_number == 42


def test_list_integrity_records_passes_limit_offset(monkeypatch):
    conn = _FakeConn(scripted_responses=[("fetch", [_integrity_row(1, None, "a")])])
    _patch_connect(monkeypatch, conn)
    store = AuditIntegrityStore(dsn="postgresql://x")
    rows = _run(store.list_integrity_records(limit=5, offset=2))
    assert len(rows) == 1
    assert _FakeConn.last_params[-2:] == (5, 2)


def test_count_audit_logs_and_integrity(monkeypatch):
    conn = _FakeConn(scripted_responses=[("fetchval", 7)])
    _patch_connect(monkeypatch, conn)
    store = AuditIntegrityStore(dsn="postgresql://x")
    n = _run(store.count_audit_logs())
    assert n == 7
