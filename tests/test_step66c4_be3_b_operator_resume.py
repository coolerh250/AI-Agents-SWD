"""Step 66C.4-BE3-B -- operator-controlled resume request/authorize/gated-execution tests.

Real-PostgreSQL 16 integration (migration 033 + the BE3-A authorization foundation) covering:
migration up/down/reapply, DB-authoritative eligibility, request idempotency/concurrency, actor
model + spoof prevention, authorize/reject/cancel races, gated execution preparation + outbox
rollback, orchestrator confirmation foundation, and privacy. Gated by the fail-closed destructive-PG
guard. Nothing calls the orchestrator or executes resume.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import sys
import uuid
from pathlib import Path

import pytest

from step66c4_pg_safety import destructive_pg_refusal_reason

REPO = Path(__file__).resolve().parents[1]
MIGRATIONS = REPO / "migrations"
_ORCH_SRC = REPO / "apps" / "orchestrator" / "src"

TEAM_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PROJECT_A = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
TEAM_B = "cccccccc-cccc-cccc-cccc-cccccccccccc"
PROJECT_B = "dddddddd-dddd-dddd-dddd-dddddddddddd"
CAPABILITY = "test-policy-authority-capability"


def _model():
    from shared.sdk.tasks import resume_request_model

    return resume_request_model


def _svc():
    from shared.sdk.tasks import resume_service

    return resume_service


def _repo():
    from shared.sdk.tasks import resume_request_repository

    return resume_request_repository


def _policy():
    from shared.sdk.tasks import authorization_policy

    return authorization_policy


def _authz():
    from shared.sdk.tasks import authorization_service

    return authorization_service


# --------------------------------------------------------------------------------------
# DB-less unit tests
# --------------------------------------------------------------------------------------


def test_feature_gates_disabled_by_default(monkeypatch) -> None:
    m = _model()
    monkeypatch.delenv("BE3_RESUME_API_ENABLED", raising=False)
    monkeypatch.delenv("BE3_RESUME_COMMAND_ENABLED", raising=False)
    assert m.resume_api_enabled() is False
    assert m.resume_command_enabled() is False
    monkeypatch.setenv("BE3_RESUME_API_ENABLED", "1")  # only a true-ish value enables
    assert m.resume_api_enabled() is False
    monkeypatch.setenv("BE3_RESUME_API_ENABLED", "yes")
    assert m.resume_api_enabled() is False
    monkeypatch.setenv("BE3_RESUME_API_ENABLED", "  TRUE  ")  # trimmed + case-insensitive
    assert m.resume_api_enabled() is True


def test_command_payload_is_identifiers_only() -> None:
    m = _model()
    ok = m.build_resume_command_payload(
        resume_request_id="rr", authorization_id="a", resource_state_version="answered:m1"
    )
    assert set(ok) == {"resume_request_id", "authorization_id", "resource_state_version"}
    with pytest.raises(ValueError):
        m.build_resume_command_payload(
            resume_request_id="rr",
            authorization_id="a",
            resource_state_version="dsn=postgres://u:p@h/db",
        )


def test_reason_code_allowlist() -> None:
    m = _model()
    assert m.assert_reason_code("policy_allow") == "policy_allow"
    with pytest.raises(ValueError):
        m.assert_reason_code("free text")


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
    ):
        await _apply(conn, name)


async def _seed(
    conn,
    *,
    project_id: str | None = PROJECT_A,
    task_status: str = "clarification_needed",
    answered: bool = True,
    eligible: bool = True,
) -> tuple[str, str]:
    task_id = await conn.fetchval(
        "INSERT INTO operator_tasks (title, task_type, created_by, status, project_id) "
        "VALUES ('t', 'software_delivery', 'alice', $1, $2) RETURNING id",
        task_status,
        uuid.UUID(project_id) if project_id else None,
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
        "VALUES ($1, $2, 'open', 'q', 'human', 'alice', "
        "        statement_timestamp() + interval '1 day', statement_timestamp()) RETURNING id",
        task_id,
        qmsg,
    )
    if answered:
        amsg = await conn.fetchval(
            "INSERT INTO task_messages (task_id, sender_type, sender_id, message_type, body) "
            "VALUES ($1, 'human', 'alice', 'clarification_answer', 'a') RETURNING id",
            task_id,
        )
        await conn.execute(
            "UPDATE operator_clarification_requests SET status='answered', "
            "answered_at=statement_timestamp(), answer_message_id=$2 WHERE id=$1",
            clar_id,
            amsg,
        )
    if eligible:
        await conn.execute(
            "UPDATE operator_clarification_requests SET resume_eligible_at=statement_timestamp() "
            "WHERE id=$1",
            clar_id,
        )
    return str(task_id), str(clar_id)


def _op(principal: str = "alice", role: str = "agent_operator"):
    return _policy().Actor(principal, role)


def _authority(principal: str = "policy-safety", role: str = "platform_admin"):
    return _policy().Actor(principal, role, is_policy_authority=True)


def _service_identity(principal: str = "svc"):
    return _policy().Actor(principal, "agent_operator", is_service_identity=True)


def _scope(team: str | None = TEAM_A, project: str | None = PROJECT_A):
    return _policy().Scope(team, project)


@pytest.fixture(autouse=True)
def _reset_gates(monkeypatch):
    # Every test starts with both gates OFF; a test that needs them sets them explicitly.
    monkeypatch.delenv("BE3_RESUME_API_ENABLED", raising=False)
    monkeypatch.delenv("BE3_RESUME_COMMAND_ENABLED", raising=False)
    yield


def _enable_api(monkeypatch):
    monkeypatch.setenv("BE3_RESUME_API_ENABLED", "true")


def _enable_command(monkeypatch):
    monkeypatch.setenv("BE3_RESUME_COMMAND_ENABLED", "true")


async def _request(conn, s, clar_id, *, actor=None, scope=None, key=None, **kw):
    async with conn.transaction():
        return await s.request_resume(
            conn,
            actor=actor or _op(),
            actor_scope=scope or _scope(),
            clarification_id=clar_id,
            idempotency_key=key or f"req:{uuid.uuid4()}",
            expires_at=await _future(conn),
            **kw,
        )


async def _future(conn):
    return await conn.fetchval("SELECT statement_timestamp() + interval '1 hour'")


# ---- Migration ----------------------------------------------------------------------


@requires_pg
def test_pg_migration_up_down_reapply_and_constraints() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            assert await conn.fetchval("SELECT to_regclass('resume_requests') IS NOT NULL")
            cons = {
                r["conname"]
                for r in await conn.fetch(
                    "SELECT conname FROM pg_constraint WHERE conrelid='resume_requests'::regclass"
                )
            }
            for c in ("chk_rr_state", "chk_rr_execution_coherent", "uq_rr_idempotency_key"):
                assert c in cons, c
            idx = {
                r["indexname"]
                for r in await conn.fetch(
                    "SELECT indexname FROM pg_indexes WHERE tablename='resume_requests'"
                )
            }
            assert "uq_rr_active_per_clarification" in idx
            # scope columns are NOT NULL
            notnull = {
                r["column_name"]
                for r in await conn.fetch(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='resume_requests' AND is_nullable='NO'"
                )
            }
            assert {"team_id", "project_id"} <= notnull
            # existing feature unchanged
            tid = await conn.fetchval(
                "INSERT INTO operator_tasks (title, task_type, created_by, status) "
                "VALUES ('t','software_delivery','a','draft') RETURNING id"
            )
            assert tid is not None
            # down + reapply is deterministic
            await _apply(conn, "033_be3_resume_requests_down.sql")
            assert await conn.fetchval("SELECT to_regclass('resume_requests') IS NULL")
            await _apply(conn, "033_be3_resume_requests.sql")
            await _apply(conn, "033_be3_resume_requests.sql")  # idempotent
            assert await conn.fetchval("SELECT to_regclass('resume_requests') IS NOT NULL")
        finally:
            await conn.close()

    _run(scenario())


# ---- Eligibility --------------------------------------------------------------------


@requires_pg
def test_pg_eligibility_gate(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)

            # answered + eligible -> success
            _, clar = await _seed(conn)
            ok = await _request(conn, s, clar)
            assert ok.ok and ok.state == "authorization_pending"

            # unanswered -> rejected
            _, clar2 = await _seed(conn, answered=False, eligible=False)
            r = await _request(conn, s, clar2)
            assert not r.ok and r.reason_code == "clarification_not_answered"

            # answered but not eligible -> rejected
            _, clar3 = await _seed(conn, eligible=False)
            r = await _request(conn, s, clar3)
            assert not r.ok and r.reason_code == "resume_not_eligible"

            # expired clarification -> blocked
            _, clar4 = await _seed(conn)
            await conn.execute(
                "UPDATE operator_clarification_requests SET status='expired' WHERE id=$1",
                uuid.UUID(clar4),
            )
            r = await _request(conn, s, clar4)
            assert not r.ok and r.reason_code == "clarification_blocked"

            # terminal parent task -> rejected
            task5, clar5 = await _seed(conn)
            await conn.execute(
                "UPDATE operator_tasks SET status='canceled' WHERE id=$1", uuid.UUID(task5)
            )
            r = await _request(conn, s, clar5)
            assert not r.ok and r.reason_code == "resource_terminal"
        finally:
            await conn.close()

    _run(scenario())


# ---- Request / idempotency / concurrency --------------------------------------------


@requires_pg
def test_pg_request_idempotency_and_active_uniqueness(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            _, clar = await _seed(conn)

            first = await _request(conn, s, clar, key="k1")
            assert first.ok
            rid = first.resume_request["resume_request_id"]
            # duplicate idempotency key -> canonical same request
            dup = await _request(conn, s, clar, key="k1")
            assert dup.ok and str(dup.resume_request["resume_request_id"]) == str(rid)
            # a DIFFERENT key for the same still-active clarification -> active_request_exists
            other = await _request(conn, s, clar, key="k2")
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
            _, clar = await _seed(setup)
        finally:
            await setup.close()
        _enable_api(monkeypatch)
        s = _svc()

        async def one():
            c = await asyncpg.connect(dsn=_DSN)
            try:
                res = await _request(c, s, clar, key=f"k:{uuid.uuid4()}")
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
                "SELECT count(*) FROM resume_requests WHERE clarification_id=$1 "
                "AND state='authorization_pending'",
                uuid.UUID(clar),
            )
            assert n == 1
        finally:
            await verify.close()

    _run(scenario())


@requires_pg
def test_pg_request_rollback_leaves_no_partial_state(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            _, clar = await _seed(conn)
            tx = conn.transaction()
            await tx.start()
            res = await s.request_resume(
                conn,
                actor=_op(),
                actor_scope=_scope(),
                clarification_id=clar,
                idempotency_key="rollback",
                expires_at=await _future(conn),
            )
            assert res.ok
            await tx.rollback()
            assert await conn.fetchval("SELECT count(*) FROM resume_requests") == 0
            assert await conn.fetchval("SELECT count(*) FROM resume_replay_authorizations") == 0
            assert await conn.fetchval("SELECT count(*) FROM clarification_lifecycle_outbox") == 0
            # the clarification marker was rolled back too
            row = await conn.fetchrow(
                "SELECT resume_requested_at FROM operator_clarification_requests WHERE id=$1",
                uuid.UUID(clar),
            )
            assert row["resume_requested_at"] is None
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_prior_terminal_request_allows_new_request(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            _, clar = await _seed(conn)
            first = await _request(conn, s, clar, key="a")
            rid = str(first.resume_request["resume_request_id"])
            async with conn.transaction():
                canceled = await s.cancel_resume(conn, rid, actor=_op(), actor_scope=_scope())
            assert canceled.ok and canceled.state == "canceled"
            # after a terminal (canceled) request the clarification can be requested again
            again = await _request(conn, s, clar, key="b")
            assert again.ok and again.state == "authorization_pending"
        finally:
            await conn.close()

    _run(scenario())


# ---- Actor model / spoof prevention (service layer) ---------------------------------


@requires_pg
def test_pg_actor_model_and_authority_separation(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)

            # non-operator role cannot request
            _, clar = await _seed(conn)
            bad = await _request(conn, s, clar, actor=_op("mallory", "requester"))
            assert not bad.ok and bad.result_kind == "forbidden"
            assert await conn.fetchval("SELECT count(*) FROM resume_requests") == 0

            # operator requests
            ok = await _request(conn, s, clar, actor=_op("alice"))
            rid = str(ok.resume_request["resume_request_id"])

            # the SAME operator cannot human-authorize their own resume
            async with conn.transaction():
                self_auth = await s.authorize_resume(
                    conn, rid, actor=_op("alice"), actor_scope=_scope(), policy_version="v1"
                )
            assert self_auth.reason_code == "policy_authority_required"
            # another plain operator also cannot authorize
            async with conn.transaction():
                other = await s.authorize_resume(
                    conn,
                    rid,
                    actor=_op("carol", "platform_admin"),
                    actor_scope=_scope(),
                    policy_version="v1",
                )
            assert other.reason_code == "policy_authority_required"
            # a service identity cannot authorize
            async with conn.transaction():
                svc_auth = await s.authorize_resume(
                    conn, rid, actor=_service_identity(), actor_scope=_scope(), policy_version="v1"
                )
            assert svc_auth.result_kind == "forbidden"

            # the policy/safety authority authorizes; decided_by is the authority, not the requester
            async with conn.transaction():
                good = await s.authorize_resume(
                    conn,
                    rid,
                    actor=_authority("policy-safety"),
                    actor_scope=_scope(),
                    policy_version="v1",
                )
            assert good.ok and good.state == "authorized"
            auth_row = await conn.fetchrow(
                "SELECT decided_by, requested_by FROM resume_replay_authorizations "
                "WHERE authorization_id=$1",
                uuid.UUID(str(good.resume_request["authorization_id"])),
            )
            assert auth_row["decided_by"] == "policy-safety"
            assert auth_row["decided_by"] != auth_row["requested_by"]
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_scope_isolation_and_null_fail_closed(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            _, clar = await _seed(conn, project_id=PROJECT_A)
            ok = await _request(conn, s, clar, scope=_scope(TEAM_A, PROJECT_A), key="k")
            rid = str(ok.resume_request["resume_request_id"])

            # cross-team read is masked
            r = await s.get_resume_request(conn, rid, actor_scope=_scope(TEAM_B, PROJECT_A))
            assert r.result_kind == "not_found_masked"
            # NULL scope fail-closed
            r = await s.get_resume_request(conn, rid, actor_scope=_scope(None, None))
            assert r.result_kind == "not_found_masked"
            # exact scope reads
            r = await s.get_resume_request(conn, rid, actor_scope=_scope(TEAM_A, PROJECT_A))
            assert r.ok
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_cross_project_task_mismatch_masked(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            # task is in PROJECT_A, but the actor declares PROJECT_B -> masked
            _, clar = await _seed(conn, project_id=PROJECT_A)
            r = await _request(conn, s, clar, scope=_scope(TEAM_A, PROJECT_B))
            assert r.result_kind == "not_found_masked"
        finally:
            await conn.close()

    _run(scenario())


# ---- Authorize / reject / cancel races ----------------------------------------------


@requires_pg
def test_pg_reject_and_cancel_and_races(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)

            # reject a pending request
            _, clar = await _seed(conn)
            a = await _request(conn, s, clar, key="rej")
            rid = str(a.resume_request["resume_request_id"])
            async with conn.transaction():
                rej = await s.reject_resume(conn, rid, actor=_authority(), actor_scope=_scope())
            assert rej.ok and rej.state == "rejected"

            # authorize a canceled request is rejected (invalid transition)
            _, clar2 = await _seed(conn)
            b = await _request(conn, s, clar2, key="cxl")
            rid2 = str(b.resume_request["resume_request_id"])
            async with conn.transaction():
                await s.cancel_resume(conn, rid2, actor=_op(), actor_scope=_scope())
            async with conn.transaction():
                after = await s.authorize_resume(
                    conn, rid2, actor=_authority(), actor_scope=_scope(), policy_version="v1"
                )
            assert not after.ok and after.result_kind == "invalid_transition"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_cancel_authorize_race_single_outcome(monkeypatch) -> None:
    async def scenario() -> None:
        setup = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(setup)
            _, clar = await _seed(setup)
        finally:
            await setup.close()
        _enable_api(monkeypatch)
        s = _svc()
        seed = await asyncpg.connect(dsn=_DSN)
        try:
            req = await _request(seed, s, clar, key="race")
            rid = str(req.resume_request["resume_request_id"])
        finally:
            await seed.close()

        async def do_cancel():
            c = await asyncpg.connect(dsn=_DSN)
            try:
                async with c.transaction():
                    return (await s.cancel_resume(c, rid, actor=_op(), actor_scope=_scope())).ok
            finally:
                await c.close()

        async def do_authorize():
            c = await asyncpg.connect(dsn=_DSN)
            try:
                async with c.transaction():
                    return (
                        await s.authorize_resume(
                            c, rid, actor=_authority(), actor_scope=_scope(), policy_version="v1"
                        )
                    ).ok
            finally:
                await c.close()

        results = await asyncio.gather(do_cancel(), do_authorize(), return_exceptions=True)
        wins = sum(1 for r in results if r is True)
        assert wins == 1  # exactly one legal terminal/authorized outcome
        verify = await asyncpg.connect(dsn=_DSN)
        try:
            st = await verify.fetchval(
                "SELECT state FROM resume_requests WHERE resume_request_id=$1", uuid.UUID(rid)
            )
            assert st in ("canceled", "authorized")
        finally:
            await verify.close()

    _run(scenario())


# ---- Gated execution preparation ----------------------------------------------------


async def _authorized_request(conn, s, monkeypatch, *, production=False, prod_ref=None):
    _enable_api(monkeypatch)
    _, clar = await _seed(conn)
    req = await _request(
        conn,
        s,
        clar,
        key=f"x:{uuid.uuid4()}",
        production_effect=production,
        production_approval_reference=prod_ref,
    )
    rid = str(req.resume_request["resume_request_id"])
    async with conn.transaction():
        await s.authorize_resume(
            conn, rid, actor=_authority(), actor_scope=_scope(), policy_version="v1"
        )
    return clar, rid


@requires_pg
def test_pg_command_gate_disabled_no_consume_no_outbox(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _clar, rid = await _authorized_request(conn, s, monkeypatch)
            # command gate is OFF
            res = await s.prepare_execution(
                conn, rid, actor=_service_identity(), actor_scope=_scope()
            )
            assert res.result_kind == "command_gate_disabled"
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM clarification_lifecycle_outbox "
                    "WHERE event_type='resume.execution_requested'"
                )
                == 0
            )
            auth = await conn.fetchrow(
                "SELECT consumed_at FROM resume_replay_authorizations LIMIT 1"
            )
            assert auth["consumed_at"] is None
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_prepare_execution_consumes_and_creates_command(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _clar, rid = await _authorized_request(conn, s, monkeypatch)
            _enable_command(monkeypatch)
            # human cannot prepare (service-identity-only)
            async with conn.transaction():
                human = await s.prepare_execution(conn, rid, actor=_op(), actor_scope=_scope())
            assert not human.ok and human.result_kind == "forbidden"

            async with conn.transaction():
                ok = await s.prepare_execution(
                    conn, rid, actor=_service_identity(), actor_scope=_scope()
                )
            assert ok.ok and ok.state == "execution_pending" and ok.command_id
            # exactly one command row; authorization consumed
            row = await conn.fetchrow(
                "SELECT id FROM clarification_lifecycle_outbox "
                "WHERE event_type='resume.execution_requested'"
            )
            assert str(row["id"]) == ok.command_id
            auth = await conn.fetchrow(
                "SELECT consumed_at FROM resume_replay_authorizations LIMIT 1"
            )
            assert auth["consumed_at"] is not None

            # duplicate prepare reuses nothing new (already consumed -> not ok, no second command)
            async with conn.transaction():
                dup = await s.prepare_execution(
                    conn, rid, actor=_service_identity(), actor_scope=_scope()
                )
            assert not dup.ok
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM clarification_lifecycle_outbox "
                    "WHERE event_type='resume.execution_requested'"
                )
                == 1
            )
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_outbox_failure_rolls_back_consume(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _clar, rid = await _authorized_request(conn, s, monkeypatch)
            _enable_command(monkeypatch)

            # force the outbox insert to fail AFTER the consume
            import shared.sdk.tasks.resume_service as rs

            async def boom(*a, **k):
                raise RuntimeError("outbox down")

            monkeypatch.setattr(rs.lifecycle_outbox, "insert_lifecycle_outbox_event", boom)
            with pytest.raises(RuntimeError):
                async with conn.transaction():
                    await s.prepare_execution(
                        conn, rid, actor=_service_identity(), actor_scope=_scope()
                    )
            # consume rolled back; request still authorized
            auth = await conn.fetchrow(
                "SELECT consumed_at FROM resume_replay_authorizations LIMIT 1"
            )
            assert auth["consumed_at"] is None
            st = await conn.fetchval(
                "SELECT state FROM resume_requests WHERE resume_request_id=$1", uuid.UUID(rid)
            )
            assert st == "authorized"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_stale_state_and_expired_and_revoked_cannot_prepare(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()

            # stale: clarification state changes after authorize -> version mismatch
            _clar, rid = await _authorized_request(conn, s, monkeypatch)
            _enable_command(monkeypatch)
            await conn.execute(
                "UPDATE operator_clarification_requests SET status='expired' WHERE id=$1",
                uuid.UUID(_clar),
            )
            async with conn.transaction():
                stale = await s.prepare_execution(
                    conn, rid, actor=_service_identity(), actor_scope=_scope()
                )
            assert stale.result_kind == "stale_state"
            auth = await conn.fetchrow(
                "SELECT consumed_at FROM resume_replay_authorizations LIMIT 1"
            )
            assert auth["consumed_at"] is None

            # expired authorization -> cannot prepare
            await _reset_and_migrate(conn)
            _clar2, rid2 = await _authorized_request(conn, s, monkeypatch)
            _enable_command(monkeypatch)
            await conn.execute(
                "UPDATE resume_replay_authorizations "
                "SET requested_at=statement_timestamp() - interval '2 hours', "
                "    expires_at=statement_timestamp() - interval '1 hour'"
            )
            async with conn.transaction():
                exp = await s.prepare_execution(
                    conn, rid2, actor=_service_identity(), actor_scope=_scope()
                )
            assert exp.result_kind in ("expired", "stale_state", "conflict")
            assert exp.ok is False
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_production_effect_independently_gated(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            # production-effect request WITHOUT an approval reference -> consume blocked
            _clar, rid = await _authorized_request(conn, s, monkeypatch, production=True)
            _enable_command(monkeypatch)
            async with conn.transaction():
                blocked = await s.prepare_execution(
                    conn, rid, actor=_service_identity(), actor_scope=_scope()
                )
            assert blocked.result_kind == "production_approval_required"

            # WITH an approval reference -> consume proceeds
            await _reset_and_migrate(conn)
            _clar2, rid2 = await _authorized_request(
                conn, s, monkeypatch, production=True, prod_ref="approval-123"
            )
            _enable_command(monkeypatch)
            async with conn.transaction():
                ok = await s.prepare_execution(
                    conn, rid2, actor=_service_identity(), actor_scope=_scope()
                )
            assert ok.ok and ok.state == "execution_pending"
        finally:
            await conn.close()

    _run(scenario())


# ---- Confirmation foundation --------------------------------------------------------


@requires_pg
def test_pg_confirm_resumed_and_failed_semantics(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _clar, rid = await _authorized_request(conn, s, monkeypatch)
            _enable_command(monkeypatch)
            async with conn.transaction():
                prep = await s.prepare_execution(
                    conn, rid, actor=_service_identity(), actor_scope=_scope()
                )
            cmd = prep.command_id

            # wrong command_id rejected
            async with conn.transaction():
                wrong = await s.confirm_resumed(conn, rid, command_id=str(uuid.uuid4()))
            assert not wrong.ok and wrong.result_kind == "conflict"

            # execution_pending -> resumed
            async with conn.transaction():
                res = await s.confirm_resumed(conn, rid, command_id=cmd)
            assert res.ok and res.state == "resumed"
            # duplicate confirmation is idempotent
            async with conn.transaction():
                again = await s.confirm_resumed(conn, rid, command_id=cmd)
            assert again.ok and again.state == "resumed"
            # resumed cannot become failed
            async with conn.transaction():
                to_fail = await s.confirm_failed(
                    conn, rid, command_id=cmd, reason_code="policy_deny"
                )
            assert not to_fail.ok and to_fail.result_kind == "conflict"

            # a fresh request path: execution_pending -> failed
            await _reset_and_migrate(conn)
            _clar2, rid2 = await _authorized_request(conn, s, monkeypatch)
            _enable_command(monkeypatch)
            async with conn.transaction():
                prep2 = await s.prepare_execution(
                    conn, rid2, actor=_service_identity(), actor_scope=_scope()
                )
            async with conn.transaction():
                failed = await s.confirm_failed(
                    conn, rid2, command_id=prep2.command_id, reason_code="policy_deny"
                )
            assert failed.ok and failed.state == "failed"
        finally:
            await conn.close()

    _run(scenario())


# ---- Privacy ------------------------------------------------------------------------


@requires_pg
def test_pg_events_carry_no_raw_content(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _clar, rid = await _authorized_request(conn, s, monkeypatch)
            _enable_command(monkeypatch)
            async with conn.transaction():
                await s.prepare_execution(
                    conn, rid, actor=_service_identity(), actor_scope=_scope()
                )
            rows = await conn.fetch(
                "SELECT event_type, payload FROM clarification_lifecycle_outbox"
            )
            assert rows
            # Payloads carry identifiers only -- an allowlist of safe keys, never a raw
            # clarification question/answer body and never a secret.
            allowed_keys = {
                "event_id",
                "occurred_at",
                "reason",
                "resume_request_id",
                "resource_state_version",
                "resume_requested_by",
                "authorization_id",
                "command_id",
            }
            for r in rows:
                payload = (
                    json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"]
                )
                assert set(payload) <= allowed_keys, (r["event_type"], set(payload))
                blob = json.dumps(payload).lower()
                for marker in ("secret", "token", "dsn=", "postgres://", "redis://", "password"):
                    assert marker not in blob, (r["event_type"], marker)
                # the raw seeded question/answer bodies ('q' / 'a') never appear as values
                for value in payload.values():
                    assert value not in ("q", "a")
        finally:
            await conn.close()

    _run(scenario())


# ---- API layer (feature gate + capability enforcement + masking) --------------------


def _load_api():
    sys.path.insert(0, str(_ORCH_SRC))
    try:
        for mod in ("task_api", "operations_resume_api"):
            sys.modules.pop(mod, None)
        task_api = importlib.import_module("task_api")
        api = importlib.import_module("operations_resume_api")
        return task_api, api
    finally:
        if str(_ORCH_SRC) in sys.path:
            sys.path.remove(str(_ORCH_SRC))


def _client(api):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


@requires_pg
def test_api_feature_gate_and_capability(monkeypatch) -> None:
    async def prep() -> str:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            _, clar = await _seed(conn)
            return clar
        finally:
            await conn.close()

    clar = _run(prep())
    monkeypatch.setenv("DATABASE_URL", _DSN)
    monkeypatch.setenv("TASK_API_TEST_AUTH_ENABLED", "true")
    _task_api, api = _load_api()
    # reset the store singleton so it picks up DATABASE_URL
    _task_api._store_singleton = None

    op_headers = {"X-Task-Actor": "alice", "X-Task-Role": "agent_operator"}
    body = {
        "clarification_id": clar,
        "team_id": TEAM_A,
        "project_id": PROJECT_A,
        "idempotency_key": "api-1",
    }

    # gate OFF -> 503, no row created
    monkeypatch.delenv("BE3_RESUME_API_ENABLED", raising=False)
    c = _client(api)
    r = c.post("/operations/resume-requests", json=body, headers=op_headers)
    assert r.status_code == 503 and r.json()["detail"] == "feature_disabled"

    # gate ON -> operator creates
    monkeypatch.setenv("BE3_RESUME_API_ENABLED", "true")
    r = c.post("/operations/resume-requests", json=body, headers=op_headers)
    assert r.status_code == 201, r.text
    rid = r.json()["resume_request_id"]

    # authorize WITHOUT the capability -> 403 policy_authority_required (operator cannot self-auth)
    dec = {"team_id": TEAM_A, "project_id": PROJECT_A, "policy_version": "v1"}
    r = c.post(f"/operations/resume-requests/{rid}/authorize", json=dec, headers=op_headers)
    assert r.status_code == 403 and r.json()["detail"] == "policy_authority_required"

    # Step 66C.4-BE3-B-C1: the capability alone is NOT sufficient -- the caller must ALSO
    # authenticate as the configured trusted principal, never an ordinary Operator's own actor id.
    monkeypatch.setenv("BE3_RESUME_POLICY_AUTHORITY_CAPABILITY", CAPABILITY)
    monkeypatch.setenv("BE3_RESUME_POLICY_AUTHORITY_PRINCIPAL_ID", "policy-safety-service")

    # the SAME operator adding the capability header themselves is still denied (wrong principal)
    self_spoof_headers = {**op_headers, "X-Resume-Policy-Authority": CAPABILITY}
    r = c.post(f"/operations/resume-requests/{rid}/authorize", json=dec, headers=self_spoof_headers)
    assert r.status_code == 403 and r.json()["detail"] == "policy_authority_required"

    # authorize as the trusted principal WITH the server-configured capability -> succeeds
    auth_headers = {
        "X-Task-Actor": "policy-safety-service",
        "X-Task-Role": "platform_admin",
        "X-Resume-Policy-Authority": CAPABILITY,
    }
    r = c.post(f"/operations/resume-requests/{rid}/authorize", json=dec, headers=auth_headers)
    assert r.status_code == 200 and r.json()["state"] == "authorized", r.text

    # cross-scope GET is masked (404)
    r = c.get(
        f"/operations/resume-requests/{rid}",
        params={"team_id": TEAM_B, "project_id": PROJECT_A},
        headers=op_headers,
    )
    assert r.status_code == 404

    # in-scope GET works
    r = c.get(
        f"/operations/resume-requests/{rid}",
        params={"team_id": TEAM_A, "project_id": PROJECT_A},
        headers=op_headers,
    )
    assert r.status_code == 200 and r.json()["state"] == "authorized"

    _task_api._store_singleton = None
