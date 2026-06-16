"""Stage 51 -- BackupDrStore SQL binding (fake asyncpg connection)."""

from __future__ import annotations

import uuid

import pytest

from shared.sdk.backup_dr.migration_catalog import build_migration_catalog
from shared.sdk.backup_dr.models import (
    BackupEncryptionConfig,
    BackupReadinessEvaluation,
    BackupRun,
)
from shared.sdk.backup_dr.store import BackupDrStore


class FakeConn:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self.closed = False

    async def fetchrow(self, sql, *args):
        self.calls.append((sql, args))
        return {"id": uuid.uuid4()}

    async def execute(self, sql, *args):
        self.calls.append((sql, args))
        return "OK"

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        return []

    def transaction(self):
        conn = self

        class _Tx:
            async def __aenter__(self_inner):
                return conn

            async def __aexit__(self_inner, *a):
                return False

        return _Tx()

    async def close(self):
        self.closed = True


@pytest.fixture
def store(monkeypatch):
    fake = FakeConn()
    s = BackupDrStore(database_url="postgresql://x")

    async def _connect():
        return fake

    monkeypatch.setattr(s, "_connect", _connect)
    s._fake = fake  # type: ignore[attr-defined]
    return s


async def test_upsert_encryption_config(store) -> None:
    rid = await store.upsert_encryption_config(
        BackupEncryptionConfig(config_key="c", status="configured", key_id="abc")
    )
    assert rid
    sql = store._fake.calls[-1][0]
    assert "backup_encryption_configs" in sql
    # no raw key column referenced
    assert "raw_key" not in sql


async def test_create_backup_run(store) -> None:
    rid = await store.create_backup_run(
        BackupRun(backup_key="b", source_database="aiagents", encrypted=True)
    )
    assert rid
    assert "backup_runs" in store._fake.calls[-1][0]


async def test_replace_migration_catalog(store) -> None:
    entries = build_migration_catalog("migrations")
    n = await store.replace_migration_catalog(entries)
    assert n == len(entries)
    assert any("migration_rollback_catalog" in c[0] for c in store._fake.calls)


async def test_create_readiness_evaluation_embeds_report(store) -> None:
    ev = BackupReadinessEvaluation(
        evaluation_key="e", status="passed_with_non_production_limitations"
    )
    await store.create_readiness_evaluation(ev, report={"readiness": {"status": "x"}})
    sql, args = store._fake.calls[-1]
    assert "backup_readiness_evaluations" in sql
    assert any("report" in str(a) for a in args)
