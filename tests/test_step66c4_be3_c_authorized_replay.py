"""Step 66C.4-BE3-C -- authorized dead-event replay request/authorize/gated-execution tests.

Real-PostgreSQL 16 integration (migration 034 + the BE3-A authorization foundation, reused unchanged
with action_type='replay') covering: migration up/down/reapply, dead-only eligibility, request
idempotency/concurrency, two-person actor model, authorize/reject/cancel races, gated execution +
rollback, destination-readiness gating, rate limiting, production-effect derivation, retry/identity
preservation, and privacy. Gated by the fail-closed destructive-PG guard. Nothing calls a real
replay_dead in any shared runtime and nothing publishes an event.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from step66c4_pg_safety import destructive_pg_refusal_reason

REPO = Path(__file__).resolve().parents[1]
MIGRATIONS = REPO / "migrations"

TEAM_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PROJECT_A = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
TEAM_B = "cccccccc-cccc-cccc-cccc-cccccccccccc"
PROJECT_B = "dddddddd-dddd-dddd-dddd-dddddddddddd"


def _model():
    from shared.sdk.tasks import replay_request_model

    return replay_request_model


def _svc():
    from shared.sdk.tasks import replay_service

    return replay_service


def _repo():
    from shared.sdk.tasks import replay_request_repository

    return replay_request_repository


def _outbox():
    from shared.sdk.tasks import lifecycle_outbox

    return lifecycle_outbox


def _policy():
    from shared.sdk.tasks import authorization_policy

    return authorization_policy


# --------------------------------------------------------------------------------------
# DB-less unit tests
# --------------------------------------------------------------------------------------


def test_feature_gates_disabled_by_default(monkeypatch) -> None:
    m = _model()
    monkeypatch.delenv("BE3_REPLAY_API_ENABLED", raising=False)
    monkeypatch.delenv("BE3_REPLAY_EXECUTION_ENABLED", raising=False)
    assert m.replay_api_enabled() is False
    assert m.replay_execution_enabled() is False
    monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
    assert m.replay_api_enabled() is True


def test_dead_episode_state_version_changes_per_episode() -> None:
    m = _model()
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 2, tzinfo=timezone.utc)
    v1 = m.dead_episode_state_version(dead_at=t1, attempts=5)
    v1_again = m.dead_episode_state_version(dead_at=t1, attempts=5)
    v2 = m.dead_episode_state_version(dead_at=t2, attempts=5)
    v3 = m.dead_episode_state_version(dead_at=t1, attempts=6)
    assert v1 == v1_again
    assert v1 != v2
    assert v1 != v3
    with pytest.raises(ValueError):
        m.dead_episode_state_version(dead_at=None, attempts=0)


def test_rate_limit_config_bounds_and_fail_closed(monkeypatch) -> None:
    m = _model()
    monkeypatch.delenv("BE3_REPLAY_MAX_SUCCESSFUL_PER_EVENT", raising=False)
    assert m.max_successful_replays_per_event() == 3
    monkeypatch.setenv("BE3_REPLAY_MAX_SUCCESSFUL_PER_EVENT", "0")
    with pytest.raises(ValueError):
        m.max_successful_replays_per_event()
    monkeypatch.setenv("BE3_REPLAY_MAX_SUCCESSFUL_PER_EVENT", "not-a-number")
    with pytest.raises(ValueError):
        m.max_successful_replays_per_event()
    monkeypatch.delenv("BE3_REPLAY_RATE_LIMIT_WINDOW_HOURS", raising=False)
    assert m.rate_limit_window_hours() == 24


def test_readiness_default_never_ready() -> None:
    m = _model()
    lo = _outbox()
    assert m.default_destination_readiness(lo.DESTINATION_AUDIT) == m.READINESS_NOT_CONFIGURED
    assert (
        m.default_destination_readiness(lo.DESTINATION_ORCHESTRATOR_COMMAND)
        == m.READINESS_NOT_CONFIGURED
    )
    assert m.default_destination_readiness("nope") == m.READINESS_UNKNOWN_DESTINATION


def test_replay_audit_payload_safety() -> None:
    m = _model()
    ok = m.build_replay_audit_payload(
        event="replay.requested", replay_request_id="r1", reason_code="policy_allow"
    )
    assert ok["replay_request_id"] == "r1"
    with pytest.raises(ValueError):
        m.build_replay_audit_payload(event="x", secret="dsn=postgres://u:p@h/db")
    with pytest.raises(ValueError):
        m.build_replay_audit_payload(event="x", not_an_allowed_key="v")


def test_two_person_policy_reused_unchanged_for_replay() -> None:
    p = _policy()
    sc = p.Scope(TEAM_A, PROJECT_A)
    appr = p.Actor("bob", "reviewer_approver")
    outcome = p.evaluate(
        action="authorize_replay",
        actor=appr,
        actor_scope=sc,
        resource_scope=sc,
        requested_by="alice",
    )
    assert outcome.allowed
    self_outcome = p.evaluate(
        action="authorize_replay",
        actor=p.Actor("alice", "reviewer_approver"),
        actor_scope=sc,
        resource_scope=sc,
        requested_by="alice",
    )
    assert not self_outcome.allowed and self_outcome.reason_code == "two_person_required"


# --------------------------------------------------------------------------------------
# Real-PostgreSQL integration
# --------------------------------------------------------------------------------------

try:
    import asyncpg

    _HAS_ASYNCPG = True
except Exception:  # pragma: no cover
    _HAS_ASYNCPG = False

_DSN = os.environ.get("BE1_TEST_DATABASE_URL")
_REFUSAL = destructive_pg_refusal_reason()


def _pg_ok() -> bool:
    if _REFUSAL is not None or not (_HAS_ASYNCPG and _DSN):
        return False
    try:

        async def _ping() -> bool:
            c = await asyncpg.connect(dsn=_DSN, timeout=5)
            await c.close()
            return True

        return asyncio.new_event_loop().run_until_complete(_ping())
    except Exception:
        return False


requires_pg = pytest.mark.skipif(
    not _pg_ok(), reason=(_REFUSAL or "isolated ephemeral PostgreSQL 16 not reachable")
)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


async def _apply(conn, name: str) -> None:
    await conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))


async def _reset_and_migrate(conn) -> None:
    await conn.execute("DROP TABLE IF EXISTS replay_requests CASCADE;")
    await conn.execute("DROP TABLE IF EXISTS resume_requests CASCADE;")
    await conn.execute("DROP TABLE IF EXISTS resume_replay_authorizations CASCADE;")
    await conn.execute(
        "DROP TABLE IF EXISTS clarification_lifecycle_outbox, operator_clarification_requests, "
        "task_messages, operator_tasks CASCADE;"
    )
    await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    for name in (
        "029_operator_task_api_foundation.sql",
        "030_workroom_clarification_foundation.sql",
        "031_clarification_lifecycle_outbox_foundation.sql",
        "032_be3_resume_replay_authorization.sql",
        "033_be3_resume_requests.sql",
        "034_be3_replay_requests.sql",
    ):
        await _apply(conn, name)


async def _seed_dead_event(
    conn,
    *,
    project_id: str | None = PROJECT_A,
    production_effect: bool = False,
    event_type: str = "clarification.expired",
    attempts: int = 5,
    status: str = "dead",
) -> tuple[str, str]:
    task_id = await conn.fetchval(
        "INSERT INTO operator_tasks (title, task_type, created_by, status, project_id, "
        "production_effect) VALUES ('t', 'software_delivery', 'alice', 'clarification_needed', "
        "$1, $2) RETURNING id",
        uuid.UUID(project_id) if project_id else None,
        production_effect,
    )
    qmsg = await conn.fetchval(
        "INSERT INTO task_messages (task_id, sender_type, sender_id, message_type, body) "
        "VALUES ($1, 'human', 'alice', 'clarification_question', 'q') RETURNING id",
        task_id,
    )
    clar_id = await conn.fetchval(
        "INSERT INTO operator_clarification_requests "
        "(task_id, question_message_id, status, question, requested_by_type, requested_by_id, "
        " due_at, reminder_at) "
        "VALUES ($1, $2, 'expired', 'q', 'human', 'alice', "
        "        statement_timestamp() - interval '1 day', statement_timestamp() - interval '2 day') "
        "RETURNING id",
        task_id,
        qmsg,
    )
    event_id = await conn.fetchval(
        "INSERT INTO clarification_lifecycle_outbox "
        "(clarification_id, task_id, event_type, idempotency_key, payload, status, attempts, "
        " dead_at, published_at) "
        "VALUES ($1, $2, $3, $4, '{}'::jsonb, $5, $6, "
        "        CASE WHEN $5='dead' THEN statement_timestamp() ELSE NULL END, "
        "        CASE WHEN $5='published' THEN statement_timestamp() ELSE NULL END) "
        "RETURNING id",
        clar_id,
        task_id,
        event_type,
        f"evt:{uuid.uuid4()}",
        status,
        attempts,
    )
    return str(task_id), str(event_id)


def _op(principal: str = "alice", role: str = "agent_operator"):
    return _policy().Actor(principal, role)


def _approver(principal: str = "bob", role: str = "reviewer_approver"):
    return _policy().Actor(principal, role)


def _service_identity(principal: str = "svc"):
    return _policy().Actor(principal, "agent_operator", is_service_identity=True)


def _scope(team: str | None = TEAM_A, project: str | None = PROJECT_A):
    return _policy().Scope(team, project)


@pytest.fixture(autouse=True)
def _reset_gates(monkeypatch):
    monkeypatch.delenv("BE3_REPLAY_API_ENABLED", raising=False)
    monkeypatch.delenv("BE3_REPLAY_EXECUTION_ENABLED", raising=False)
    monkeypatch.delenv("BE3_REPLAY_MAX_SUCCESSFUL_PER_EVENT", raising=False)
    monkeypatch.delenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", raising=False)
    monkeypatch.delenv("BE3_REPLAY_RATE_LIMIT_WINDOW_HOURS", raising=False)
    yield


def _enable_api(monkeypatch):
    monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")


def _enable_execution(monkeypatch):
    monkeypatch.setenv("BE3_REPLAY_EXECUTION_ENABLED", "true")


def _ready(_destination: str) -> str:
    return _model().READINESS_READY


async def _future(conn, hours: int = 1):
    return await conn.fetchval(
        "SELECT statement_timestamp() + ($1 || ' hours')::interval", str(hours)
    )


async def _request(conn, s, event_id, *, actor=None, scope=None, key=None, **kw):
    async with conn.transaction():
        return await s.request_replay(
            conn,
            actor=actor or _op(),
            actor_scope=scope or _scope(),
            outbox_event_id=event_id,
            idempotency_key=key or f"req:{uuid.uuid4()}",
            expires_at=await _future(conn),
            **kw,
        )


async def _authorized_replay_request(conn, s, monkeypatch, **seed_kw):
    _enable_api(monkeypatch)
    _task_id, event_id = await _seed_dead_event(conn, **seed_kw)
    req = await _request(conn, s, event_id, key=f"k:{uuid.uuid4()}")
    assert req.ok, req.reason_code
    rid = str(req.replay_request["replay_request_id"])
    async with conn.transaction():
        auth = await s.authorize_replay(
            conn, rid, actor=_approver(), actor_scope=_scope(), policy_version="v1"
        )
    assert auth.ok, auth.reason_code
    return event_id, rid


# ---- Migration ------------------------------------------------------------------------


@requires_pg
def test_pg_migration_up_down_reapply_and_constraints() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            assert await conn.fetchval("SELECT to_regclass('replay_requests') IS NOT NULL")
            cons = {
                r["conname"]
                for r in await conn.fetch(
                    "SELECT conname FROM pg_constraint WHERE conrelid='replay_requests'::regclass"
                )
            }
            for c in ("chk_rpr_state", "chk_rpr_executed_coherent", "uq_rpr_idempotency_key"):
                assert c in cons, c
            idx = {
                r["indexname"]
                for r in await conn.fetch(
                    "SELECT indexname FROM pg_indexes WHERE tablename='replay_requests'"
                )
            }
            assert "uq_rpr_active_per_event" in idx
            notnull = {
                r["column_name"]
                for r in await conn.fetch(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='replay_requests' AND is_nullable='NO'"
                )
            }
            assert {"team_id", "project_id"} <= notnull
            # existing BE1/BE2 rows compatible: an ordinary pending outbox row still inserts fine
            tid = await conn.fetchval(
                "INSERT INTO operator_tasks (title, task_type, created_by, status) "
                "VALUES ('t','software_delivery','a','draft') RETURNING id"
            )
            assert tid is not None
            await _apply(conn, "034_be3_replay_requests_down.sql")
            assert await conn.fetchval("SELECT to_regclass('replay_requests') IS NULL")
            await _apply(conn, "034_be3_replay_requests.sql")
            await _apply(conn, "034_be3_replay_requests.sql")  # idempotent
            assert await conn.fetchval("SELECT to_regclass('replay_requests') IS NOT NULL")
        finally:
            await conn.close()

    _run(scenario())


# ---- Eligibility ------------------------------------------------------------------------


@requires_pg
def test_pg_eligibility_dead_required(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)

            _t, dead_event = await _seed_dead_event(conn, status="dead")
            ok = await _request(conn, s, dead_event)
            assert ok.ok

            _t2, pending_event = await _seed_dead_event(conn, status="pending")
            r = await _request(conn, s, pending_event)
            assert not r.ok and r.reason_code == "not_dead"

            _t3, published_event = await _seed_dead_event(conn, status="published")
            r = await _request(conn, s, published_event)
            assert not r.ok and r.reason_code == "already_published"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_eligibility_scope_masked_and_null_fail_closed(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            _t, event_id = await _seed_dead_event(conn, project_id=PROJECT_A)

            # cross-project actor -> masked
            r = await _request(conn, s, event_id, scope=_scope(TEAM_A, PROJECT_B))
            assert r.result_kind == "not_found_masked"
            # NULL scope -> fail-closed
            r = await _request(conn, s, event_id, scope=_scope(None, None))
            assert r.result_kind == "not_found_masked"
            # nonexistent event -> masked
            r = await _request(conn, s, str(uuid.uuid4()))
            assert r.result_kind == "not_found_masked"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_request_idempotency_and_active_uniqueness(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            _t, event_id = await _seed_dead_event(conn)

            first = await _request(conn, s, event_id, key="k1")
            assert first.ok
            rid = first.replay_request["replay_request_id"]
            dup = await _request(conn, s, event_id, key="k1")
            assert dup.ok and str(dup.replay_request["replay_request_id"]) == str(rid)
            other = await _request(conn, s, event_id, key="k2")
            assert not other.ok and other.reason_code == "active_request_exists"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_concurrent_request_exactly_one_active(monkeypatch) -> None:
    async def scenario() -> None:
        setup = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(setup)
            _t, event_id = await _seed_dead_event(setup)
        finally:
            await setup.close()
        _enable_api(monkeypatch)
        s = _svc()

        async def one():
            c = await asyncpg.connect(dsn=_DSN)
            try:
                res = await _request(c, s, event_id, key=f"k:{uuid.uuid4()}")
                return res.ok
            except asyncpg.UniqueViolationError:
                return False
            finally:
                await c.close()

        results = await asyncio.gather(one(), one(), one(), return_exceptions=True)
        wins = sum(1 for r in results if r is True)
        assert wins == 1

        verify = await asyncpg.connect(dsn=_DSN)
        try:
            n = await verify.fetchval(
                "SELECT count(*) FROM replay_requests WHERE outbox_event_id=$1 "
                "AND state='authorization_pending'",
                uuid.UUID(event_id),
            )
            assert n == 1
        finally:
            await verify.close()

    _run(scenario())


# ---- Actors / two-person -----------------------------------------------------------------


@requires_pg
def test_pg_actor_model_operator_approver_service_identity(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            _t, event_id = await _seed_dead_event(conn)

            # unauthorized role cannot request
            bad = await _request(conn, s, event_id, actor=_op("carol", "requester"))
            assert not bad.ok and bad.result_kind == "forbidden"
            assert await conn.fetchval("SELECT count(*) FROM replay_requests") == 0

            # service identity cannot request
            svc_req = await _request(conn, s, event_id, actor=_service_identity())
            assert not svc_req.ok and svc_req.result_kind == "forbidden"

            # operator requests
            req = await _request(conn, s, event_id, actor=_op("alice"))
            assert req.ok
            rid = str(req.replay_request["replay_request_id"])

            # service identity cannot authorize
            async with conn.transaction():
                svc_auth = await s.authorize_replay(
                    conn, rid, actor=_service_identity(), actor_scope=_scope(), policy_version="v1"
                )
            assert svc_auth.result_kind == "forbidden"

            # a different approver authorizes
            async with conn.transaction():
                ok = await s.authorize_replay(
                    conn, rid, actor=_approver("bob"), actor_scope=_scope(), policy_version="v1"
                )
            assert ok.ok and ok.state == "authorized"

            # a human cannot execute
            human_exec = await s.execute_authorized_replay(
                conn, rid, actor=_op("alice"), actor_scope=_scope(), readiness_provider=_ready
            )
            assert human_exec.result_kind == "execution_gate_disabled"  # gate closed first anyway
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_requester_cannot_self_approve(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            _t, event_id = await _seed_dead_event(conn)
            # alice requests as an operator role that ALSO happens to be a valid approver role
            req = await _request(conn, s, event_id, actor=_op("alice", "platform_admin"))
            assert req.ok
            rid = str(req.replay_request["replay_request_id"])
            async with conn.transaction():
                self_auth = await s.authorize_replay(
                    conn,
                    rid,
                    actor=_op("alice", "platform_admin"),
                    actor_scope=_scope(),
                    policy_version="v1",
                )
            assert (
                self_auth.result_kind == "forbidden"
                and self_auth.reason_code == "requester_cannot_approve"
            )
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_authorize_cancel_race_one_outcome(monkeypatch) -> None:
    async def scenario() -> None:
        setup = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(setup)
            _t, event_id = await _seed_dead_event(setup)
        finally:
            await setup.close()
        _enable_api(monkeypatch)
        s = _svc()
        seed = await asyncpg.connect(dsn=_DSN)
        try:
            req = await _request(seed, s, event_id, key="race")
            rid = str(req.replay_request["replay_request_id"])
        finally:
            await seed.close()

        async def do_cancel():
            c = await asyncpg.connect(dsn=_DSN)
            try:
                async with c.transaction():
                    return (await s.cancel_replay(c, rid, actor=_op(), actor_scope=_scope())).ok
            finally:
                await c.close()

        async def do_authorize():
            c = await asyncpg.connect(dsn=_DSN)
            try:
                async with c.transaction():
                    return (
                        await s.authorize_replay(
                            c, rid, actor=_approver(), actor_scope=_scope(), policy_version="v1"
                        )
                    ).ok
            finally:
                await c.close()

        results = await asyncio.gather(do_cancel(), do_authorize(), return_exceptions=True)
        wins = sum(1 for r in results if r is True)
        assert wins == 1
        verify = await asyncpg.connect(dsn=_DSN)
        try:
            st = await verify.fetchval(
                "SELECT state FROM replay_requests WHERE replay_request_id=$1", uuid.UUID(rid)
            )
            assert st in ("canceled", "authorized")
        finally:
            await verify.close()

    _run(scenario())


# ---- Gated execution ----------------------------------------------------------------


@requires_pg
def test_pg_execution_gate_disabled_no_consume_no_mutation(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            event_id, rid = await _authorized_replay_request(conn, s, monkeypatch)
            res = await s.execute_authorized_replay(
                conn,
                rid,
                actor=_service_identity(),
                actor_scope=_scope(),
                readiness_provider=_ready,
            )
            assert res.result_kind == "execution_gate_disabled"
            auth = await conn.fetchrow(
                "SELECT consumed_at FROM resume_replay_authorizations LIMIT 1"
            )
            assert auth["consumed_at"] is None
            row = await conn.fetchrow(
                "SELECT status FROM clarification_lifecycle_outbox WHERE id=$1", uuid.UUID(event_id)
            )
            assert row["status"] == "dead"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_destination_unavailable_blocks_no_consume_no_mutation(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            event_id, rid = await _authorized_replay_request(conn, s, monkeypatch)
            _enable_execution(monkeypatch)
            m = _model()
            async with conn.transaction():
                res = await s.execute_authorized_replay(
                    conn,
                    rid,
                    actor=_service_identity(),
                    actor_scope=_scope(),
                    readiness_provider=m.default_destination_readiness,
                )
            assert res.result_kind == "destination_unavailable"
            auth = await conn.fetchrow(
                "SELECT consumed_at FROM resume_replay_authorizations LIMIT 1"
            )
            assert auth["consumed_at"] is None
            row = await conn.fetchrow(
                "SELECT status FROM clarification_lifecycle_outbox WHERE id=$1", uuid.UUID(event_id)
            )
            assert row["status"] == "dead"
            # replay_request stays 'authorized' (retryable later), not a terminal state
            st = await conn.fetchval(
                "SELECT state FROM replay_requests WHERE replay_request_id=$1", uuid.UUID(rid)
            )
            assert st == "authorized"
            blocked = await conn.fetchval(
                "SELECT count(*) FROM clarification_lifecycle_outbox "
                "WHERE event_type='replay.execution_blocked'"
            )
            assert blocked == 1
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_valid_execution_preserves_identity_and_increments_episode(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            event_id, rid = await _authorized_replay_request(conn, s, monkeypatch, attempts=3)
            before = await conn.fetchrow(
                "SELECT idempotency_key, event_type, payload, created_at FROM "
                "clarification_lifecycle_outbox WHERE id=$1",
                uuid.UUID(event_id),
            )
            _enable_execution(monkeypatch)
            async with conn.transaction():
                res = await s.execute_authorized_replay(
                    conn,
                    rid,
                    actor=_service_identity(),
                    actor_scope=_scope(),
                    readiness_provider=_ready,
                )
            assert res.ok and res.state == "executed"
            after = await conn.fetchrow(
                "SELECT * FROM clarification_lifecycle_outbox WHERE id=$1", uuid.UUID(event_id)
            )
            assert after["status"] == "pending"
            assert after["idempotency_key"] == before["idempotency_key"]
            assert after["event_type"] == before["event_type"]
            assert after["created_at"] == before["created_at"]
            assert after["attempts"] == 3  # NOT reset (plan_replay_state preserves it)
            assert after["dead_at"] is None
            # authorization consumed exactly once
            auth = await conn.fetchrow(
                "SELECT consumed_at FROM resume_replay_authorizations LIMIT 1"
            )
            assert auth["consumed_at"] is not None
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_concurrent_execute_exactly_one_replay(monkeypatch) -> None:
    async def scenario() -> None:
        setup = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(setup)
            event_id, rid = await _authorized_replay_request(setup, _svc(), monkeypatch)
        finally:
            await setup.close()
        _enable_execution(monkeypatch)
        s = _svc()

        async def one():
            c = await asyncpg.connect(dsn=_DSN)
            try:
                async with c.transaction():
                    res = await s.execute_authorized_replay(
                        c,
                        rid,
                        actor=_service_identity(),
                        actor_scope=_scope(),
                        readiness_provider=_ready,
                    )
                    return res.ok
            finally:
                await c.close()

        results = await asyncio.gather(one(), one(), one(), return_exceptions=True)
        wins = sum(1 for r in results if r is True)
        assert wins == 1

        verify = await asyncpg.connect(dsn=_DSN)
        try:
            st = await verify.fetchval(
                "SELECT status FROM clarification_lifecycle_outbox WHERE id=$1", uuid.UUID(event_id)
            )
            assert st == "pending"
        finally:
            await verify.close()

    _run(scenario())


@requires_pg
def test_pg_stale_authorization_cannot_execute(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            event_id, rid = await _authorized_replay_request(conn, s, monkeypatch)
            # the underlying event's dead episode changes after authorization (simulating a race)
            await conn.execute(
                "UPDATE clarification_lifecycle_outbox SET attempts=99 WHERE id=$1",
                uuid.UUID(event_id),
            )
            _enable_execution(monkeypatch)
            async with conn.transaction():
                res = await s.execute_authorized_replay(
                    conn,
                    rid,
                    actor=_service_identity(),
                    actor_scope=_scope(),
                    readiness_provider=_ready,
                )
            assert res.result_kind == "stale_state"
            auth = await conn.fetchrow(
                "SELECT consumed_at FROM resume_replay_authorizations LIMIT 1"
            )
            assert auth["consumed_at"] is None
        finally:
            await conn.close()

    _run(scenario())


# ---- Rollback -------------------------------------------------------------------------


@requires_pg
def test_pg_execution_failure_rolls_back_consume(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            event_id, rid = await _authorized_replay_request(conn, s, monkeypatch)
            _enable_execution(monkeypatch)

            import shared.sdk.tasks.replay_service as rsvc

            async def boom(*a, **k):
                return None  # simulate the guard failing after consume

            monkeypatch.setattr(rsvc.repo, "replay_dead_row", boom)
            with pytest.raises(RuntimeError):
                async with conn.transaction():
                    await s.execute_authorized_replay(
                        conn,
                        rid,
                        actor=_service_identity(),
                        actor_scope=_scope(),
                        readiness_provider=_ready,
                    )
            auth = await conn.fetchrow(
                "SELECT consumed_at FROM resume_replay_authorizations LIMIT 1"
            )
            assert auth["consumed_at"] is None
            row = await conn.fetchrow(
                "SELECT status FROM clarification_lifecycle_outbox WHERE id=$1", uuid.UUID(event_id)
            )
            assert row["status"] == "dead"
            st = await conn.fetchval(
                "SELECT state FROM replay_requests WHERE replay_request_id=$1", uuid.UUID(rid)
            )
            assert st == "authorized"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_audit_insertion_failure_rolls_back_execution(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            event_id, rid = await _authorized_replay_request(conn, s, monkeypatch)
            _enable_execution(monkeypatch)

            import shared.sdk.tasks.replay_service as rsvc

            async def boom(*a, **k):
                raise RuntimeError("outbox down")

            monkeypatch.setattr(rsvc.lifecycle_outbox, "insert_lifecycle_outbox_event", boom)
            with pytest.raises(RuntimeError):
                async with conn.transaction():
                    await s.execute_authorized_replay(
                        conn,
                        rid,
                        actor=_service_identity(),
                        actor_scope=_scope(),
                        readiness_provider=_ready,
                    )
            auth = await conn.fetchrow(
                "SELECT consumed_at FROM resume_replay_authorizations LIMIT 1"
            )
            assert auth["consumed_at"] is None
            row = await conn.fetchrow(
                "SELECT status FROM clarification_lifecycle_outbox WHERE id=$1", uuid.UUID(event_id)
            )
            assert row["status"] == "dead"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_process_failure_before_commit_leaves_no_partial_state(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            _t, event_id = await _seed_dead_event(conn)
            tx = conn.transaction()
            await tx.start()
            res = await s.request_replay(
                conn,
                actor=_op(),
                actor_scope=_scope(),
                outbox_event_id=event_id,
                idempotency_key="rollback",
                expires_at=await _future(conn),
            )
            assert res.ok
            await tx.rollback()
            assert await conn.fetchval("SELECT count(*) FROM replay_requests") == 0
            assert await conn.fetchval("SELECT count(*) FROM resume_replay_authorizations") == 0
            row = await conn.fetchrow(
                "SELECT status FROM clarification_lifecycle_outbox WHERE id=$1", uuid.UUID(event_id)
            )
            assert row["status"] == "dead"
        finally:
            await conn.close()

    _run(scenario())


# ---- Rate limiting ----------------------------------------------------------------------


@requires_pg
def test_pg_rate_limit_actor_window(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "2")
            for i in range(2):
                _t, event_id = await _seed_dead_event(conn)
                res = await _request(conn, s, event_id, actor=_op("alice"), key=f"a{i}")
                assert res.ok
            _t, event_id3 = await _seed_dead_event(conn)
            blocked = await _request(conn, s, event_id3, actor=_op("alice"), key="a3")
            assert not blocked.ok and blocked.reason_code == "rate_limited"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_rate_limit_event_cap(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            monkeypatch.setenv("BE3_REPLAY_MAX_SUCCESSFUL_PER_EVENT", "1")
            _enable_api(monkeypatch)
            _enable_execution(monkeypatch)
            _t, event_id = await _seed_dead_event(conn)
            req = await _request(conn, s, event_id, key="first")
            rid = str(req.replay_request["replay_request_id"])
            async with conn.transaction():
                await s.authorize_replay(
                    conn, rid, actor=_approver(), actor_scope=_scope(), policy_version="v1"
                )
            async with conn.transaction():
                exec_res = await s.execute_authorized_replay(
                    conn,
                    rid,
                    actor=_service_identity(),
                    actor_scope=_scope(),
                    readiness_provider=_ready,
                )
            assert exec_res.ok

            # the event died again (simulate downstream failure) -> a second replay request is
            # blocked by the per-event successful-replay cap (max 1 configured above)
            await conn.execute(
                "UPDATE clarification_lifecycle_outbox SET status='dead', "
                "dead_at=statement_timestamp() WHERE id=$1",
                uuid.UUID(event_id),
            )
            second = await _request(conn, s, event_id, key="second")
            assert not second.ok and second.reason_code == "rate_limited"
        finally:
            await conn.close()

    _run(scenario())


# ---- Production effect / privacy -----------------------------------------------------


@requires_pg
def test_pg_production_effect_derived_not_client_trusted(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            _enable_execution(monkeypatch)
            # the OWNING TASK has production_effect=True -- server-side authoritative
            _t, event_id = await _seed_dead_event(conn, production_effect=True)
            req = await _request(conn, s, event_id, key="prod")
            rid = str(req.replay_request["replay_request_id"])
            async with conn.transaction():
                await s.authorize_replay(
                    conn, rid, actor=_approver(), actor_scope=_scope(), policy_version="v1"
                )
            blocked = await s.execute_authorized_replay(
                conn,
                rid,
                actor=_service_identity(),
                actor_scope=_scope(),
                readiness_provider=_ready,
            )
            assert blocked.result_kind == "production_approval_required"

            auth_row = await conn.fetchrow(
                "SELECT production_effect FROM resume_replay_authorizations LIMIT 1"
            )
            assert auth_row["production_effect"] is True  # derived server-side, not client body
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_events_carry_no_raw_content(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            event_id, rid = await _authorized_replay_request(conn, s, monkeypatch)
            _enable_execution(monkeypatch)
            async with conn.transaction():
                await s.execute_authorized_replay(
                    conn,
                    rid,
                    actor=_service_identity(),
                    actor_scope=_scope(),
                    readiness_provider=_ready,
                )
            rows = await conn.fetch(
                "SELECT event_type, payload FROM clarification_lifecycle_outbox "
                "WHERE event_type LIKE 'replay.%'"
            )
            assert rows
            for r in rows:
                blob = str(r["payload"]).lower()
                for marker in ("secret", "token", "dsn=", "postgres://", "redis://", "password"):
                    assert marker not in blob, (r["event_type"], marker)
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_expire_due_replay_requests(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            _t, event_id = await _seed_dead_event(conn)
            expires_soon = await _future(conn, hours=1)
            async with conn.transaction():
                req = await s.request_replay(
                    conn,
                    actor=_op(),
                    actor_scope=_scope(),
                    outbox_event_id=event_id,
                    idempotency_key="exp",
                    expires_at=expires_soon,
                )
            assert req.ok
            await conn.execute(
                "UPDATE resume_replay_authorizations "
                "SET requested_at=statement_timestamp() - interval '2 hours', "
                "    expires_at=statement_timestamp() - interval '1 hour'"
            )
            r = _repo()
            now = await r.db_now(conn)
            n = await r.expire_due_replay_requests(conn, before=now)
            assert n >= 1
            st = await conn.fetchval(
                "SELECT state FROM replay_requests WHERE outbox_event_id=$1", uuid.UUID(event_id)
            )
            assert st == "expired"
        finally:
            await conn.close()

    _run(scenario())
