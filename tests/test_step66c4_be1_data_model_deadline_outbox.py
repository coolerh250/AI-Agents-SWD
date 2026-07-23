"""Step 66C.4-BE1 -- data model, deadline CAS, disabled outbox foundation tests.

Three layers:
  * DB-less unit tests: outbox payload-safety guard, event-type allowlist, outbox row
    mapping, migration additivity (text), and the deadline predicate's presence in the
    answer CAS SQL. These run everywhere.
  * API test: the answer endpoint returns 409 invalid_state_for_answer:expired for a
    past-deadline clarification (in-memory store, mirroring the Step 66C.3 harness).
  * Real-Postgres integration tests: migration up/down/reapply, six nullable lifecycle
    fields, outbox table/indexes/constraints, existing-row compatibility, deadline CAS
    (future/past/boundary/answered/non-open/concurrent), and transaction-aware outbox
    insert/rollback/atomicity/idempotency. Gated by BE1_TEST_DATABASE_URL (an isolated,
    ephemeral test Postgres) -- skipped when unset, per this repo's stack-test convention.

No shared runtime is touched. Migrations run only against the isolated ephemeral DSN.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[1]
MIGRATIONS = REPO / "migrations"
UP_SQL = MIGRATIONS / "031_clarification_lifecycle_outbox_foundation.sql"
DOWN_SQL = MIGRATIONS / "031_clarification_lifecycle_outbox_foundation_down.sql"

# Canonical event naming (api-and-event-contract.md 11.2).
REMINDER_EVENT = "clarification.reminder_recorded"

LIFECYCLE_FIELDS = (
    "reminder_sent_at",
    "expired_at",
    "resume_eligible_at",
    "resume_requested_at",
    "resume_requested_by",
    "resume_authorized_at",
)


# --------------------------------------------------------------------------------------
# DB-less unit tests
# --------------------------------------------------------------------------------------


def _import_outbox():
    from shared.sdk.tasks import lifecycle_outbox

    return lifecycle_outbox


def test_migration_is_additive_and_nullable() -> None:
    up = UP_SQL.read_text(encoding="utf-8")
    # Additive: only ADD COLUMN / CREATE TABLE / CREATE INDEX / ADD CONSTRAINT.
    assert "ADD COLUMN IF NOT EXISTS" in up
    assert "CREATE TABLE IF NOT EXISTS clarification_lifecycle_outbox" in up
    # No destructive statements in the up migration.
    for banned in ("DROP TABLE", "DROP COLUMN", "ALTER COLUMN", "TRUNCATE", "DELETE FROM"):
        assert banned not in up, banned
    # Exactly the six lifecycle fields, and none of the forbidden ones.
    for field in LIFECYCLE_FIELDS:
        assert field in up, field
    for forbidden in ("resume_dispatched_at", "resume_authorized_by", "lock_version"):
        assert forbidden not in up, forbidden
    # Lifecycle columns are nullable: no NOT NULL is attached to the six ADD COLUMNs.
    for field in LIFECYCLE_FIELDS:
        assert f"{field} TIMESTAMPTZ NOT NULL" not in up
        assert f"{field} TEXT NOT NULL" not in up


def test_down_migration_removes_only_be1_objects() -> None:
    down = DOWN_SQL.read_text(encoding="utf-8")
    assert "DROP TABLE IF EXISTS clarification_lifecycle_outbox" in down
    for field in LIFECYCLE_FIELDS:
        assert f"DROP COLUMN IF EXISTS {field}" in down
    # It must not drop pre-existing tables/columns.
    for preexisting in ("operator_tasks", "task_messages", "due_at", "reminder_at", "status"):
        assert f"DROP TABLE IF EXISTS {preexisting}" not in down
        assert f"DROP COLUMN IF EXISTS {preexisting}" not in down


def test_answer_cas_sql_enforces_authoritative_deadline() -> None:
    src = (REPO / "shared" / "sdk" / "tasks" / "workroom_store.py").read_text(encoding="utf-8")
    # Step 66C.4-BE1-R1: the deadline uses statement_timestamp(), never now()/
    # transaction_timestamp() (which freeze at BEGIN and would let a transaction opened
    # before due_at claim after it).
    assert "due_at > statement_timestamp()" in src
    assert "due_at > now()" not in src
    assert "answered_at IS NULL" in src
    assert "status='open'" in src


def test_outbox_payload_guard_rejects_prohibited_keys() -> None:
    lifecycle_outbox = _import_outbox()
    for key in ("question", "answer", "body", "token", "secret", "password"):
        with pytest.raises(ValueError):
            lifecycle_outbox.assert_safe_outbox_payload({key: "x"}, event_type=REMINDER_EVENT)


def test_outbox_payload_guard_rejects_oversize() -> None:
    lifecycle_outbox = _import_outbox()
    with pytest.raises(ValueError):
        lifecycle_outbox.assert_safe_outbox_payload(
            {"reason": "x" * 5000}, event_type=REMINDER_EVENT
        )


def test_outbox_payload_guard_accepts_safe_minimal() -> None:
    lifecycle_outbox = _import_outbox()
    ok = lifecycle_outbox.assert_safe_outbox_payload(
        {"reason": "reminder_sent"}, event_type=REMINDER_EVENT
    )
    assert ok == {"reason": "reminder_sent"}
    assert lifecycle_outbox.assert_safe_outbox_payload(None, event_type=REMINDER_EVENT) == {}


def test_outbox_event_type_allowlist() -> None:
    lifecycle_outbox = _import_outbox()
    assert REMINDER_EVENT in lifecycle_outbox.ALLOWED_EVENT_TYPES
    assert "clarification.expired" in lifecycle_outbox.ALLOWED_EVENT_TYPES
    # dispatch/resume-dispatched events are NOT part of BE1's foundation scope.
    assert "clarification.resume_dispatched" not in lifecycle_outbox.ALLOWED_EVENT_TYPES


def test_outbox_module_has_no_live_producer_import() -> None:
    # Static guard: no runtime module imports lifecycle_outbox (disabled foundation).
    offenders = []
    for path in (REPO / "apps").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "lifecycle_outbox" in text:
            offenders.append(str(path.relative_to(REPO)))
    for path in (REPO / "shared").rglob("*.py"):
        if path.name == "lifecycle_outbox.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "lifecycle_outbox" in text:
            offenders.append(str(path.relative_to(REPO)))
    assert offenders == [], f"live runtime references to lifecycle_outbox: {offenders}"


# --------------------------------------------------------------------------------------
# API test -- past-deadline answer returns 409 invalid_state_for_answer:expired
# --------------------------------------------------------------------------------------


def _load_apis():
    src = REPO / "apps" / "orchestrator" / "src"
    sys.path.insert(0, str(src))
    try:
        sys.modules.pop("task_api", None)
        sys.modules.pop("workroom_api", None)
        task_api = importlib.import_module("task_api")
        workroom_api = importlib.import_module("workroom_api")
        return task_api, workroom_api
    finally:
        if str(src) in sys.path:
            sys.path.remove(str(src))


class _DeadlineWorkroomStore:
    """In-memory store whose claim mimics the deadline CAS: a past-due open row loses
    the claim (returns None) while its status stays 'open' (timeout worker not run yet)."""

    def __init__(self) -> None:
        self.clarifications: dict[str, dict[str, Any]] = {}
        self.messages: dict[str, dict[str, Any]] = {}

    def seed_clarification(self, task_id: str, *, past_due: bool) -> str:
        cid = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        due = now - timedelta(hours=1) if past_due else now + timedelta(hours=1)
        qid = str(uuid.uuid4())
        self.messages[qid] = {"id": qid, "task_id": task_id}
        self.clarifications[cid] = {
            "id": cid,
            "task_id": task_id,
            "question_message_id": qid,
            "status": "open",
            "due_at": due.isoformat(),
            "answered_at": None,
            "_past_due": past_due,
        }
        return cid

    async def get_clarification(self, cid: str) -> dict[str, Any] | None:
        row = self.clarifications.get(cid)
        return dict(row) if row else None

    async def claim_clarification_answer(self, cid: str) -> dict[str, Any] | None:
        row = self.clarifications[cid]
        if row["status"] != "open" or row["answered_at"] is not None or row["_past_due"]:
            return None
        row["status"] = "answered"
        row["answered_at"] = datetime.now(timezone.utc).isoformat()
        return dict(row)

    async def create_message(self, **kwargs: Any) -> dict[str, Any]:
        mid = str(uuid.uuid4())
        self.messages[mid] = {"id": mid, "correlation_id": str(uuid.uuid4()), **kwargs}
        return dict(self.messages[mid])

    async def set_answer_message(self, cid: str, *, answer_message_id: str) -> dict[str, Any]:
        self.clarifications[cid]["answer_message_id"] = answer_message_id
        return dict(self.clarifications[cid])


class _TaskStore:
    def __init__(self, task_id: str, created_by: str) -> None:
        self.task_id = task_id
        self.created_by = created_by

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        if task_id != self.task_id:
            return None
        return {"id": task_id, "created_by": self.created_by, "production_effect": False}

    async def set_clarification_state(
        self, task_id: str, *, status: str, clarification_status: str
    ) -> dict[str, Any]:
        return {
            "id": task_id,
            "status": status,
            "clarification_status": clarification_status,
        }


async def _noop_audit(*_a: Any, **_k: Any) -> None:
    return None


@pytest.fixture
def deadline_client(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    task_api, workroom_api = _load_apis()
    monkeypatch.setenv("TASK_API_TEST_AUTH_ENABLED", "true")
    task_id = str(uuid.uuid4())
    wstore = _DeadlineWorkroomStore()
    tstore = _TaskStore(task_id, created_by="alice")
    monkeypatch.setattr(task_api, "_store", lambda: tstore)
    monkeypatch.setattr(task_api, "_audit", _noop_audit)
    monkeypatch.setattr(workroom_api, "_workroom_store", lambda: wstore)
    app = FastAPI()
    app.include_router(workroom_api.router)
    return workroom_api, wstore, task_id, TestClient(app)


def _answer(client, task_id: str, cid: str):
    return client.post(
        f"/tasks/{task_id}/clarifications/{cid}/answer",
        json={"answer": "the answer"},
        headers={"X-Task-Actor": "alice", "X-Task-Role": "platform_admin"},
    )


def test_past_deadline_answer_returns_409_expired(deadline_client) -> None:
    _, wstore, task_id, client = deadline_client
    cid = wstore.seed_clarification(task_id, past_due=True)
    resp = _answer(client, task_id, cid)
    assert resp.status_code == 409
    assert resp.json()["detail"] == "invalid_state_for_answer:expired"


def test_within_deadline_answer_succeeds(deadline_client) -> None:
    _, wstore, task_id, client = deadline_client
    cid = wstore.seed_clarification(task_id, past_due=False)
    resp = _answer(client, task_id, cid)
    assert resp.status_code == 200
    assert wstore.clarifications[cid]["status"] == "answered"


# --------------------------------------------------------------------------------------
# Real-Postgres integration tests (isolated ephemeral DB via BE1_TEST_DATABASE_URL)
# --------------------------------------------------------------------------------------

import os  # noqa: E402

try:
    import asyncpg  # noqa: E402

    _HAS_ASYNCPG = True
except Exception:  # pragma: no cover
    _HAS_ASYNCPG = False

from step66c4_pg_safety import destructive_pg_refusal_reason  # noqa: E402

_DSN = os.environ.get("BE1_TEST_DATABASE_URL")
_REFUSAL = destructive_pg_refusal_reason()


def _pg_reachable() -> bool:
    # Fail-closed: these fixtures DROP tables, so an un-vetted DSN must never reach them.
    if _REFUSAL is not None:
        return False
    if not (_HAS_ASYNCPG and _DSN):
        return False
    try:

        async def _ping() -> bool:
            conn = await asyncpg.connect(dsn=_DSN, timeout=5)
            await conn.close()
            return True

        return asyncio.new_event_loop().run_until_complete(_ping())
    except Exception:
        return False


requires_pg = pytest.mark.skipif(
    not _pg_reachable(),
    reason=(
        _REFUSAL
        or "isolated test Postgres not reachable (set BE1_TEST_DATABASE_URL to an ephemeral DB)"
    ),
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _apply_base_and_migration(conn) -> None:
    await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    for name in (
        "029_operator_task_api_foundation.sql",
        "030_workroom_clarification_foundation.sql",
        "031_clarification_lifecycle_outbox_foundation.sql",
    ):
        await conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))


async def _seed_task_and_clarification(conn, *, due_offset_hours: float) -> tuple[str, str]:
    task_id = await conn.fetchval("""
        INSERT INTO operator_tasks (title, task_type, created_by)
        VALUES ('t','software_delivery','alice') RETURNING id
        """)
    qmid = await conn.fetchval(
        """
        INSERT INTO task_messages (task_id, sender_type, sender_id, message_type, body)
        VALUES ($1,'human','alice','clarification_question','q') RETURNING id
        """,
        task_id,
    )
    cid = await conn.fetchval(
        """
        INSERT INTO operator_clarification_requests
          (task_id, question_message_id, question, requested_by_type, requested_by_id,
           due_at, reminder_at)
        VALUES ($1,$2,'q','human','alice', now() + ($3 || ' hours')::interval,
                now() + ($3 || ' hours')::interval)
        RETURNING id
        """,
        task_id,
        qmid,
        str(due_offset_hours),
    )
    return str(task_id), str(cid)


@requires_pg
def test_pg_migration_creates_schema_and_rolls_back() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await conn.execute(
                "DROP TABLE IF EXISTS clarification_lifecycle_outbox, "
                "operator_clarification_requests, task_messages, operator_tasks CASCADE;"
            )
            await _apply_base_and_migration(conn)
            # Six lifecycle fields exist and are nullable.
            cols = {
                r["column_name"]: r["is_nullable"]
                for r in await conn.fetch(
                    "SELECT column_name, is_nullable FROM information_schema.columns "
                    "WHERE table_name='operator_clarification_requests'"
                )
            }
            for f in LIFECYCLE_FIELDS:
                assert f in cols, f
                assert cols[f] == "YES", f
            assert "resume_dispatched_at" not in cols
            # Outbox table + indexes + unique constraint exist.
            assert await conn.fetchval("SELECT to_regclass('clarification_lifecycle_outbox')")
            idx = {
                r["indexname"]
                for r in await conn.fetch(
                    "SELECT indexname FROM pg_indexes WHERE tablename IN "
                    "('operator_clarification_requests','clarification_lifecycle_outbox')"
                )
            }
            assert "idx_ocr_reminder_due" in idx
            assert "idx_ocr_expiry_due" in idx
            assert "idx_clo_pending_created" in idx
            assert "idx_clo_pending_available" in idx
            assert "idx_clo_dead_at" in idx
            # Reapply is idempotent.
            await conn.execute(UP_SQL.read_text(encoding="utf-8"))
            # Rollback removes only BE1 objects.
            await conn.execute(DOWN_SQL.read_text(encoding="utf-8"))
            cols_after = {
                r["column_name"]
                for r in await conn.fetch(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='operator_clarification_requests'"
                )
            }
            for f in LIFECYCLE_FIELDS:
                assert f not in cols_after, f
            assert not await conn.fetchval("SELECT to_regclass('clarification_lifecycle_outbox')")
            # Pre-existing columns survive rollback.
            assert "due_at" in cols_after and "status" in cols_after
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_existing_rows_remain_intact_after_migration() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await conn.execute(
                "DROP TABLE IF EXISTS clarification_lifecycle_outbox, "
                "operator_clarification_requests, task_messages, operator_tasks CASCADE;"
            )
            await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
            await conn.execute((MIGRATIONS / "029_operator_task_api_foundation.sql").read_text())
            await conn.execute(
                (MIGRATIONS / "030_workroom_clarification_foundation.sql").read_text()
            )
            _task_id, cid = await _seed_task_and_clarification(conn, due_offset_hours=72)
            # Apply BE1 migration AFTER data exists; row must remain readable/unmutated.
            await conn.execute(UP_SQL.read_text(encoding="utf-8"))
            row = await conn.fetchrow(
                "SELECT status, answered_at, reminder_sent_at, resume_eligible_at "
                "FROM operator_clarification_requests WHERE id=$1",
                uuid.UUID(cid),
            )
            assert row["status"] == "open"
            assert row["answered_at"] is None
            assert row["reminder_sent_at"] is None
            assert row["resume_eligible_at"] is None
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_deadline_cas_future_past_boundary() -> None:
    from shared.sdk.tasks.workroom_store import WorkroomStore

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await conn.execute(
                "DROP TABLE IF EXISTS clarification_lifecycle_outbox, "
                "operator_clarification_requests, task_messages, operator_tasks CASCADE;"
            )
            await _apply_base_and_migration(conn)
            store = WorkroomStore(database_url=_DSN)

            # Future deadline -> claim succeeds.
            _t, cid_future = await _seed_task_and_clarification(conn, due_offset_hours=1)
            assert await store.claim_clarification_answer(cid_future) is not None

            # Past deadline, still 'open' -> claim fails (deadline predicate).
            _t, cid_past = await _seed_task_and_clarification(conn, due_offset_hours=-1)
            assert await store.claim_clarification_answer(cid_past) is None
            still = await conn.fetchval(
                "SELECT status FROM operator_clarification_requests WHERE id=$1",
                uuid.UUID(cid_past),
            )
            assert still == "open"  # not materialized to expired by BE1

            # Exact boundary (due_at == now) -> exclusive upper bound -> fails.
            _t, cid_boundary = await _seed_task_and_clarification(conn, due_offset_hours=0)
            # due_at was set to now() at insert; a later claim has now() > due_at -> fails.
            assert await store.claim_clarification_answer(cid_boundary) is None

            # Already answered -> claim fails.
            assert await store.claim_clarification_answer(cid_future) is None
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_concurrent_answer_exactly_one_wins() -> None:
    from shared.sdk.tasks.workroom_store import WorkroomStore

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await conn.execute(
                "DROP TABLE IF EXISTS clarification_lifecycle_outbox, "
                "operator_clarification_requests, task_messages, operator_tasks CASCADE;"
            )
            await _apply_base_and_migration(conn)
            _t, cid = await _seed_task_and_clarification(conn, due_offset_hours=1)
            store = WorkroomStore(database_url=_DSN)
            results = await asyncio.gather(
                store.claim_clarification_answer(cid),
                store.claim_clarification_answer(cid),
            )
            winners = [r for r in results if r is not None]
            assert len(winners) == 1
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_outbox_transaction_atomicity_and_idempotency() -> None:
    from shared.sdk.tasks import lifecycle_outbox

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await conn.execute(
                "DROP TABLE IF EXISTS clarification_lifecycle_outbox, "
                "operator_clarification_requests, task_messages, operator_tasks CASCADE;"
            )
            await _apply_base_and_migration(conn)
            task_id, cid = await _seed_task_and_clarification(conn, due_offset_hours=1)

            # Rollback removes the outbox row (transaction-aware insert, caller-owned txn).
            tx = conn.transaction()
            await tx.start()
            await lifecycle_outbox.insert_lifecycle_outbox_event(
                conn,
                clarification_id=cid,
                task_id=task_id,
                event_type=REMINDER_EVENT,
                idempotency_key=f"{cid}:reminder",
                payload={"reason": "reminder_sent"},
            )
            await tx.rollback()
            assert await conn.fetchval("SELECT count(*) FROM clarification_lifecycle_outbox") == 0

            # Committed insert persists; duplicate idempotency key is rejected.
            tx2 = conn.transaction()
            await tx2.start()
            await lifecycle_outbox.insert_lifecycle_outbox_event(
                conn,
                clarification_id=cid,
                task_id=task_id,
                event_type=REMINDER_EVENT,
                idempotency_key=f"{cid}:reminder",
                payload={"reason": "reminder_sent"},
            )
            await tx2.commit()
            assert await conn.fetchval("SELECT count(*) FROM clarification_lifecycle_outbox") == 1
            with pytest.raises(asyncpg.UniqueViolationError):
                await lifecycle_outbox.insert_lifecycle_outbox_event(
                    conn,
                    clarification_id=cid,
                    task_id=task_id,
                    event_type=REMINDER_EVENT,
                    idempotency_key=f"{cid}:reminder",
                    payload={"reason": "dup"},
                )
        finally:
            await conn.close()

    _run(scenario())
