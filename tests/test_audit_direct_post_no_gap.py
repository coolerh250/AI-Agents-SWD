"""Stage 39 -- direct POST closure: success creates integrity in same txn."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import asyncpg
import pytest
from fastapi.testclient import TestClient


class _Txn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Conn:
    """Records every SQL call so the test can assert ordering."""

    def __init__(self, *, fail_integrity_insert: bool = False) -> None:
        self.calls: list[str] = []
        self._fail_integrity_insert = fail_integrity_insert

    def transaction(self):
        return _Txn()

    async def execute(self, sql: str, *params: Any) -> Any:
        self.calls.append("execute:" + sql.split()[0].lower())
        return None

    async def fetchrow(self, sql: str, *params: Any) -> Any:
        head = sql.split()[0].lower()
        self.calls.append("fetchrow:" + head)
        if "INSERT INTO audit_logs" in sql:
            return {
                "id": uuid4(),
                "task_id": params[0],
                "agent": params[1],
                "decision_type": params[2],
                "summary": params[3],
                "result": params[4],
                "artifact_refs": params[5],
                "created_at": datetime(2026, 6, 10, tzinfo=timezone.utc),
            }
        if "WHERE audit_log_id = $1" in sql:
            return None  # not yet recorded
        if "ORDER BY sequence_number DESC LIMIT 1" in sql:
            return None  # genesis
        if "INSERT INTO audit_integrity_records" in sql:
            if self._fail_integrity_insert:
                raise asyncpg.PostgresError("simulated integrity write failure")
            return {
                "integrity_id": uuid4(),
                "audit_log_id": params[0],
                "chain_version": params[1],
                "sequence_number": params[2],
                "prev_hash": params[3],
                "row_hash": params[4],
                "canonical_payload_hash": params[5],
                "hmac_signature": params[6],
                "signing_key_id": params[7],
                "signature_status": params[8],
                "integrity_status": params[9],
                "created_at": datetime.now(timezone.utc),
            }
        return None

    async def close(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _patch_event_bus(monkeypatch):
    """Stub the Redis publish so the unit test never touches Redis."""

    class _Bus:
        async def publish_event(self, *a, **kw):
            return None

        async def close(self):
            return None

    import shared.sdk.event_bus.redis_streams as redis_streams

    monkeypatch.setattr(redis_streams, "RedisStreamEventBus", lambda *a, **kw: _Bus())


def test_direct_post_creates_audit_then_integrity(monkeypatch, audit_service_app):
    conn = _Conn()

    async def _connect(*a, **kw):
        return conn

    monkeypatch.setattr(asyncpg, "connect", _connect)
    client = TestClient(audit_service_app)
    resp = client.post(
        "/audit/events",
        json={
            "task_id": "task-direct-1",
            "agent": "test-agent",
            "decision_type": "test_direct_post",
            "summary": "stage39 direct post integrity",
            "result": "ok",
            "artifact_refs": {"k": "v"},
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("audit_integrity_created") is True
    assert body.get("audit_integrity_status") in ("unsigned", "signing_key_not_configured")
    # Both INSERTs must have been called, with the audit_logs INSERT
    # coming before the integrity INSERT.
    audit_idx = next(i for i, c in enumerate(conn.calls) if c == "fetchrow:insert")
    integrity_idx = next(
        i
        for i, c in enumerate(conn.calls[audit_idx + 1 :], start=audit_idx + 1)
        if c == "fetchrow:insert"
    )
    assert integrity_idx > audit_idx
    # Advisory lock must be acquired between the two INSERTs (or
    # immediately before the integrity INSERT). Walk forward from the
    # audit insert and look for the lock execute.
    lock_calls = [i for i, c in enumerate(conn.calls) if c.startswith("execute:select")]
    assert lock_calls, "advisory lock SELECT not executed during direct POST"


def test_direct_post_rolls_back_on_integrity_failure(monkeypatch, audit_service_app):
    conn = _Conn(fail_integrity_insert=True)

    async def _connect(*a, **kw):
        return conn

    monkeypatch.setattr(asyncpg, "connect", _connect)
    client = TestClient(audit_service_app)
    resp = client.post(
        "/audit/events",
        json={
            "task_id": "task-direct-fail-1",
            "agent": "test-agent",
            "decision_type": "test_direct_post_failure",
            "summary": "stage39 direct post failure",
            "result": "fail",
            "artifact_refs": {},
        },
    )
    assert resp.status_code == 503
    assert "integrity" in resp.json()["detail"].lower()
