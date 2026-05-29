"""Unit tests for shared/sdk/notifications/store.NotificationDeliveryStore.

We stub asyncpg so the test does not need a Postgres. The store's contract
under test:

* create_delivery returns the row dict on success and ``None`` when the
  unique source_message_id collides.
* mark_delivered / mark_failed return the updated row.
* list_deliveries / counts build the expected SQL.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import asyncpg

from shared.sdk.notifications.store import NotificationDeliveryStore


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


class _Row(dict):
    def __getitem__(self, key: str) -> Any:  # noqa: D401
        return dict.__getitem__(self, key)


def _make_row(**overrides: Any) -> _Row:
    base = {
        "id": uuid4(),
        "task_id": "t-1",
        "event_type": "discord.task.received",
        "channel": "discord",
        "target": "sandbox-channel",
        "status": "simulated",
        "sandbox": True,
        "external_sent": False,
        "message_id": None,
        "error": None,
        "source_message_id": "1-0",
        "metadata": {},
        "created_at": datetime.now(timezone.utc),
        "delivered_at": None,
    }
    base.update(overrides)
    return _Row(base)


class _Conn:
    last_sql: str = ""
    last_params: tuple = ()

    def __init__(self, row: _Row | None = None, rows: list[_Row] | None = None) -> None:
        self._row = row
        self._rows = rows or []

    async def fetchrow(self, sql: str, *params: Any) -> _Row | None:
        _Conn.last_sql = sql
        _Conn.last_params = params
        return self._row

    async def fetch(self, sql: str, *params: Any) -> list[_Row]:
        _Conn.last_sql = sql
        _Conn.last_params = params
        return self._rows

    async def close(self) -> None:
        return None


def _patch(monkeypatch, conn: _Conn) -> None:
    async def _connect(*_a: Any, **_kw: Any) -> _Conn:
        return conn

    monkeypatch.setattr(asyncpg, "connect", _connect)


def test_create_delivery_returns_row(monkeypatch):
    row = _make_row()
    _patch(monkeypatch, _Conn(row=row))
    store = NotificationDeliveryStore(database_url="postgresql://example")
    out = _run(
        store.create_delivery(
            task_id="t-1",
            event_type="discord.task.received",
            channel="discord",
            target="sandbox-channel",
            status="simulated",
            sandbox=True,
            external_sent=False,
            source_message_id="1-0",
            metadata={"rendered_message": "x"},
        )
    )
    assert out is not None
    assert out["task_id"] == "t-1"
    assert out["status"] == "simulated"
    assert out["sandbox"] is True
    assert out["external_sent"] is False
    assert "ON CONFLICT (source_message_id) DO NOTHING" in _Conn.last_sql


def test_create_delivery_dedups_on_conflict(monkeypatch):
    _patch(monkeypatch, _Conn(row=None))
    store = NotificationDeliveryStore(database_url="postgresql://example")
    out = _run(
        store.create_delivery(
            task_id="t-1",
            event_type="discord.task.received",
            channel="discord",
            target="sandbox-channel",
            status="simulated",
            sandbox=True,
            external_sent=False,
            source_message_id="dup-1",
        )
    )
    assert out is None  # ON CONFLICT DO NOTHING returns no row


def test_mark_delivered_sets_status(monkeypatch):
    row = _make_row(status="delivered", external_sent=True, message_id="discord-123")
    _patch(monkeypatch, _Conn(row=row))
    store = NotificationDeliveryStore(database_url="postgresql://example")
    out = _run(
        store.mark_delivered("00000000-0000-0000-0000-000000000001", message_id="discord-123")
    )
    assert out is not None
    assert out["status"] == "delivered"
    assert out["external_sent"] is True
    assert "UPDATE notification_deliveries" in _Conn.last_sql
    assert "SET status = 'delivered'" in _Conn.last_sql


def test_mark_failed_records_error(monkeypatch):
    row = _make_row(status="failed", error="boom")
    _patch(monkeypatch, _Conn(row=row))
    store = NotificationDeliveryStore(database_url="postgresql://example")
    out = _run(store.mark_failed("id", error="boom"))
    assert out is not None
    assert out["status"] == "failed"
    assert out["error"] == "boom"


def test_list_deliveries_builds_where_clause(monkeypatch):
    _patch(monkeypatch, _Conn(rows=[_make_row(task_id="t-list")]))
    store = NotificationDeliveryStore(database_url="postgresql://example")
    rows = _run(store.list_deliveries(task_id="t-list", status="simulated", limit=10))
    assert len(rows) == 1
    assert "task_id = $1" in _Conn.last_sql
    assert "status = $2" in _Conn.last_sql
    assert _Conn.last_params == ("t-list", "simulated", 10)


def test_counts_returns_zeros_when_empty(monkeypatch):
    _patch(monkeypatch, _Conn(row=None, rows=[]))
    store = NotificationDeliveryStore(database_url="postgresql://example")
    counts = _run(store.counts())
    assert counts == {
        "total": 0,
        "simulated": 0,
        "delivered": 0,
        "failed": 0,
        "skipped": 0,
        "external_sent": 0,
    }


def test_counts_uses_aggregated_row(monkeypatch):
    row = _Row(
        {
            "total": 5,
            "simulated": 3,
            "delivered": 1,
            "failed": 1,
            "skipped": 0,
            "external_sent": 1,
        }
    )
    _patch(monkeypatch, _Conn(row=row))
    store = NotificationDeliveryStore(database_url="postgresql://example")
    counts = _run(store.counts(task_id="t-1"))
    assert counts["total"] == 5
    assert counts["simulated"] == 3
    assert counts["delivered"] == 1
    assert counts["external_sent"] == 1
    assert "task_id = $1" in _Conn.last_sql
