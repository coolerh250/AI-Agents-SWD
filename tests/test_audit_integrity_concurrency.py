"""Stage 39 -- advisory lock + sequence collision retry (no real DB).

The integration concurrency proof lives in the verify script
(``scripts/verify_audit_direct_post_integrity.sh``); these unit tests
pin the in-process pieces:

* every integrity write inside the shared writer acquires the
  ``pg_advisory_xact_lock`` advisory lock first;
* a ``UniqueViolationError`` triggers a transparent retry.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import asyncpg
import pytest

from shared.sdk.audit_integrity import (
    ADVISORY_LOCK_NAME,
    AuditIntegrityStore,
    AuditSigner,
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _FakeTxn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Conn:
    def __init__(self, *, fail_first: bool = False) -> None:
        self.execute_calls: list[tuple[str, tuple]] = []
        self.fetchrow_calls: list[tuple[str, tuple]] = []
        self._fail_first = fail_first
        self._fail_count = 0

    def transaction(self):
        return _FakeTxn()

    async def execute(self, sql: str, *params: Any) -> Any:
        self.execute_calls.append((sql, params))
        return None

    async def fetchrow(self, sql: str, *params: Any) -> Any:
        self.fetchrow_calls.append((sql, params))
        if "WHERE audit_log_id = $1" in sql:
            return None  # not yet recorded
        if "ORDER BY sequence_number DESC LIMIT 1" in sql:
            return None  # genesis row
        if "INSERT INTO audit_integrity_records" in sql:
            if self._fail_first and self._fail_count == 0:
                self._fail_count += 1
                raise asyncpg.UniqueViolationError("duplicate key value violates unique constraint")
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


def _payload() -> dict:
    return {
        "audit_log_id": str(uuid4()),
        "task_id": "T",
        "agent": "a",
        "decision_type": "d",
        "summary": "s",
        "result": "ok",
        "artifact_refs": {"k": "v"},
        "created_at": datetime(2026, 6, 1, tzinfo=timezone.utc),
    }


@pytest.fixture
def signer():
    return AuditSigner(env={})


def test_create_integrity_acquires_advisory_lock(monkeypatch, signer):
    conn = _Conn()

    async def _connect(*a, **kw):
        return conn

    monkeypatch.setattr(asyncpg, "connect", _connect)
    store = AuditIntegrityStore(dsn="postgresql://x", signer=signer)
    out = _run(store.create_integrity_record_for_audit_log(_payload()))
    assert out is not None
    advisory_calls = [sql for sql, _ in conn.execute_calls if "pg_advisory_xact_lock" in sql]
    assert advisory_calls, "advisory lock must be acquired before sequence insert"
    # Confirm the lock name is the documented chain marker.
    lock_params = [params for sql, params in conn.execute_calls if "pg_advisory_xact_lock" in sql]
    assert any(ADVISORY_LOCK_NAME in p for p in lock_params)


def test_unique_violation_triggers_retry(monkeypatch, signer):
    conn = _Conn(fail_first=True)

    async def _connect(*a, **kw):
        return conn

    monkeypatch.setattr(asyncpg, "connect", _connect)
    store = AuditIntegrityStore(dsn="postgresql://x", signer=signer)
    # Even with one synthetic UniqueViolationError, the writer must
    # succeed transparently on retry.
    out = _run(store.create_integrity_record_for_audit_log(_payload()))
    assert out is not None
    # Two attempts means two advisory-lock acquisitions.
    advisory_calls = [sql for sql, _ in conn.execute_calls if "pg_advisory_xact_lock" in sql]
    assert len(advisory_calls) >= 2
