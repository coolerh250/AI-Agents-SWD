"""Step 66C.4-BE3-R2 -- resume production-effect authoritative derivation (finding R2-1 closure).

Real-PostgreSQL 16 integration covering: resume's production-effect classification is now derived
SERVER-SIDE from the owning task's OWN `operator_tasks.production_effect` column -- never from
request input -- folded into the resume resource_state_version so a LATER change to the task's
classification invalidates any outstanding request/authorization bound to the OLD classification
(revalidated at authorize AND consume time, under the same row locks used for eligibility). The
production_action_approvals registry (Step 66C.4-BE3-R1) integration is unchanged and reused.

Gated by the fail-closed destructive-PG guard. Nothing calls the orchestrator or executes resume.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path

import pytest

from step66c4_pg_safety import destructive_pg_refusal_reason

REPO = Path(__file__).resolve().parents[1]
MIGRATIONS = REPO / "migrations"

TEAM_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PROJECT_A = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
PROJECT_B = "dddddddd-dddd-dddd-dddd-dddddddddddd"


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


def _paa_svc():
    from shared.sdk.tasks import production_approval_service

    return production_approval_service


# --------------------------------------------------------------------------------------
# DB-less unit tests
# --------------------------------------------------------------------------------------


def test_client_cannot_supply_production_effect_at_all() -> None:
    """The resume service function has NO production_effect parameter -- there is no code path
    through which a caller could even attempt to pass one (the strongest possible proof: it isn't
    merely ignored, it doesn't exist)."""
    import inspect

    from shared.sdk.tasks import resume_service

    sig = inspect.signature(resume_service.request_resume)
    assert "production_effect" not in sig.parameters


def test_api_schema_has_no_production_effect_field() -> None:
    """The HTTP request schema does not expose production_effect as a field; even if a client sends
    it in the JSON body, Pydantic silently drops an unrecognized key (default `extra` behavior) and
    it never reaches the service layer."""
    import sys

    src = REPO / "apps" / "orchestrator" / "src"
    sys.path.insert(0, str(src))
    try:
        sys.modules.pop("operations_resume_api", None)
        import operations_resume_api as api
    finally:
        if str(src) in sys.path:
            sys.path.remove(str(src))
    assert "production_effect" not in api.ResumeRequestCreate.model_fields
    # a client-sent production_effect is silently dropped, not rejected and not honored
    payload = api.ResumeRequestCreate(
        clarification_id=str(uuid.uuid4()),
        team_id=TEAM_A,
        project_id=PROJECT_A,
        idempotency_key="k1",
        production_effect=False,  # type: ignore[call-arg]
    )
    assert not hasattr(payload, "production_effect")


def test_authoritative_production_effect_fail_closed_default() -> None:
    m = _model()
    assert m.authoritative_production_effect({"production_effect": True}) is True
    assert m.authoritative_production_effect({"production_effect": False}) is False
    # an unresolvable/missing value fails closed (treated as production-effect)
    assert m.authoritative_production_effect({}) is True


def test_state_version_changes_with_production_effect() -> None:
    m = _model()
    clar = {"status": "answered", "answer_message_id": "m1"}
    v_false = m.resource_state_version(clar, {"production_effect": False})
    v_true = m.resource_state_version(clar, {"production_effect": True})
    assert v_false != v_true
    assert v_false == m.resource_state_version(clar, {"production_effect": False})


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
    await conn.execute("DROP TABLE IF EXISTS production_action_approvals CASCADE;")
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
        "035_be3_production_action_approvals.sql",
    ):
        await _apply(conn, name)


async def _seed(
    conn,
    *,
    project_id: str | None = PROJECT_A,
    production_effect: bool = False,
    answered: bool = True,
    eligible: bool = True,
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


def _approver(principal: str = "carol", role: str = "reviewer_approver"):
    return _policy().Actor(principal, role)


def _service_identity(principal: str = "svc"):
    return _policy().Actor(principal, "agent_operator", is_service_identity=True)


def _scope(team: str | None = TEAM_A, project: str | None = PROJECT_A):
    return _policy().Scope(team, project)


@pytest.fixture(autouse=True)
def _reset_gates(monkeypatch):
    monkeypatch.delenv("BE3_RESUME_API_ENABLED", raising=False)
    monkeypatch.delenv("BE3_RESUME_COMMAND_ENABLED", raising=False)
    yield


def _enable_api(monkeypatch):
    monkeypatch.setenv("BE3_RESUME_API_ENABLED", "true")


def _enable_command(monkeypatch):
    monkeypatch.setenv("BE3_RESUME_COMMAND_ENABLED", "true")


async def _future(conn, hours: int = 1):
    return await conn.fetchval(
        "SELECT statement_timestamp() + ($1 || ' hours')::interval", str(hours)
    )


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


async def _grant(conn, *, resource_id, resource_state_version, action_type="resume"):
    approvals = _paa_svc()
    async with conn.transaction():
        return await approvals.grant_production_approval(
            conn,
            actor=_approver(),
            actor_scope=_scope(),
            action_type=action_type,
            resource_type="clarification",
            resource_id=resource_id,
            resource_state_version=resource_state_version,
            expires_at=await _future(conn),
            idempotency_key=f"grant:{uuid.uuid4()}",
        )


# ---- Client cannot control classification -------------------------------------------


@requires_pg
def test_pg_client_downgrade_has_no_effect(monkeypatch) -> None:
    """task.production_effect=true; the client cannot make it false (there is no request field to
    even try). The stored request/authorization must be true and require a production approval."""

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            _t, clar = await _seed(conn, production_effect=True)
            req = await _request(conn, s, clar)
            assert req.ok, req.reason_code
            auth_row = await conn.fetchrow(
                "SELECT production_effect FROM resume_replay_authorizations LIMIT 1"
            )
            assert auth_row["production_effect"] is True

            async with conn.transaction():
                await s.authorize_resume(
                    conn,
                    str(req.resume_request["resume_request_id"]),
                    actor=_authority(),
                    actor_scope=_scope(),
                    policy_version="v1",
                )
            _enable_command(monkeypatch)
            async with conn.transaction():
                blocked = await s.prepare_execution(
                    conn,
                    str(req.resume_request["resume_request_id"]),
                    actor=_service_identity(),
                    actor_scope=_scope(),
                )
            assert blocked.result_kind == "production_approval_required"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_client_upgrade_attempt_has_no_effect(monkeypatch) -> None:
    """task.production_effect=false; there is no way for a client to force it true. The stored
    request/authorization must be false and NOT require a production approval."""

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            _t, clar = await _seed(conn, production_effect=False)
            req = await _request(conn, s, clar)
            assert req.ok, req.reason_code
            auth_row = await conn.fetchrow(
                "SELECT production_effect FROM resume_replay_authorizations LIMIT 1"
            )
            assert auth_row["production_effect"] is False

            async with conn.transaction():
                await s.authorize_resume(
                    conn,
                    str(req.resume_request["resume_request_id"]),
                    actor=_authority(),
                    actor_scope=_scope(),
                    policy_version="v1",
                )
            _enable_command(monkeypatch)
            async with conn.transaction():
                ok = await s.prepare_execution(
                    conn,
                    str(req.resume_request["resume_request_id"]),
                    actor=_service_identity(),
                    actor_scope=_scope(),
                )
            assert ok.ok and ok.state == "execution_pending"
        finally:
            await conn.close()

    _run(scenario())


# ---- State-change races ---------------------------------------------------------------


@requires_pg
def test_pg_task_becomes_production_between_request_and_authorize(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            t, clar = await _seed(conn, production_effect=False)
            req = await _request(conn, s, clar)
            assert req.ok, req.reason_code

            await conn.execute(
                "UPDATE operator_tasks SET production_effect=true WHERE id=$1", uuid.UUID(t)
            )
            async with conn.transaction():
                stale = await s.authorize_resume(
                    conn,
                    str(req.resume_request["resume_request_id"]),
                    actor=_authority(),
                    actor_scope=_scope(),
                    policy_version="v1",
                )
            assert not stale.ok and stale.result_kind == "stale_state"
            auth = await conn.fetchrow(
                "SELECT decision, consumed_at FROM resume_replay_authorizations LIMIT 1"
            )
            assert auth["decision"] == "pending" and auth["consumed_at"] is None
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_task_becomes_production_between_authorize_and_consume(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            t, clar = await _seed(conn, production_effect=False)
            req = await _request(conn, s, clar)
            assert req.ok, req.reason_code
            async with conn.transaction():
                auth_ok = await s.authorize_resume(
                    conn,
                    str(req.resume_request["resume_request_id"]),
                    actor=_authority(),
                    actor_scope=_scope(),
                    policy_version="v1",
                )
            assert auth_ok.ok

            await conn.execute(
                "UPDATE operator_tasks SET production_effect=true WHERE id=$1", uuid.UUID(t)
            )
            _enable_command(monkeypatch)
            async with conn.transaction():
                rejected = await s.prepare_execution(
                    conn,
                    str(req.resume_request["resume_request_id"]),
                    actor=_service_identity(),
                    actor_scope=_scope(),
                )
            assert not rejected.ok and rejected.result_kind == "stale_state"
            auth = await conn.fetchrow(
                "SELECT consumed_at FROM resume_replay_authorizations LIMIT 1"
            )
            assert auth["consumed_at"] is None
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_task_changes_between_request_and_consume_state_version_mismatch(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            t, clar = await _seed(conn, production_effect=True)
            req = await _request(conn, s, clar)
            assert req.ok, req.reason_code
            async with conn.transaction():
                await s.authorize_resume(
                    conn,
                    str(req.resume_request["resume_request_id"]),
                    actor=_authority(),
                    actor_scope=_scope(),
                    policy_version="v1",
                )
            # production -> non-production before consume
            await conn.execute(
                "UPDATE operator_tasks SET production_effect=false WHERE id=$1", uuid.UUID(t)
            )
            _enable_command(monkeypatch)
            async with conn.transaction():
                rejected = await s.prepare_execution(
                    conn,
                    str(req.resume_request["resume_request_id"]),
                    actor=_service_identity(),
                    actor_scope=_scope(),
                )
            assert not rejected.ok and rejected.result_kind == "stale_state"
        finally:
            await conn.close()

    _run(scenario())


# ---- Production approval integration --------------------------------------------------


@requires_pg
def test_pg_production_task_no_approval_blocks_consume(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            _t, clar = await _seed(conn, production_effect=True)
            req = await _request(conn, s, clar)
            async with conn.transaction():
                await s.authorize_resume(
                    conn,
                    str(req.resume_request["resume_request_id"]),
                    actor=_authority(),
                    actor_scope=_scope(),
                    policy_version="v1",
                )
            _enable_command(monkeypatch)
            async with conn.transaction():
                blocked = await s.prepare_execution(
                    conn,
                    str(req.resume_request["resume_request_id"]),
                    actor=_service_identity(),
                    actor_scope=_scope(),
                )
            assert blocked.result_kind == "production_approval_required"
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM clarification_lifecycle_outbox "
                    "WHERE event_type='resume.execution_requested'"
                )
                == 0
            )
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_production_task_valid_approval_consume_succeeds(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            _t, clar = await _seed(conn, production_effect=True)
            clar_row = dict(
                await conn.fetchrow(
                    "SELECT * FROM operator_clarification_requests WHERE id=$1", uuid.UUID(clar)
                )
            )
            task_row = dict(
                await conn.fetchrow("SELECT * FROM operator_tasks WHERE id=$1", uuid.UUID(_t))
            )
            state_version = _model().resource_state_version(clar_row, task_row)
            grant = await _grant(conn, resource_id=clar, resource_state_version=state_version)
            assert grant.ok and grant.approval is not None
            approval_id = str(grant.approval["approval_id"])

            req = await _request(conn, s, clar, production_approval_reference=approval_id)
            assert req.ok, req.reason_code
            async with conn.transaction():
                await s.authorize_resume(
                    conn,
                    str(req.resume_request["resume_request_id"]),
                    actor=_authority(),
                    actor_scope=_scope(),
                    policy_version="v1",
                )
            _enable_command(monkeypatch)
            async with conn.transaction():
                ok = await s.prepare_execution(
                    conn,
                    str(req.resume_request["resume_request_id"]),
                    actor=_service_identity(),
                    actor_scope=_scope(),
                )
            assert ok.ok and ok.state == "execution_pending"
            approval_row = await conn.fetchrow(
                "SELECT state FROM production_action_approvals WHERE approval_id=$1",
                uuid.UUID(approval_id),
            )
            assert approval_row["state"] == "consumed"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_wrong_resource_and_stale_version_approval_rejected(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)

            # approval granted for a DIFFERENT clarification -> wrong_resource
            _t1, clar1 = await _seed(conn, production_effect=True)
            _t2, clar2 = await _seed(conn, production_effect=True)
            clar2_row = dict(
                await conn.fetchrow(
                    "SELECT * FROM operator_clarification_requests WHERE id=$1", uuid.UUID(clar2)
                )
            )
            task2_row = dict(
                await conn.fetchrow("SELECT * FROM operator_tasks WHERE id=$1", uuid.UUID(_t2))
            )
            wrong_grant = await _grant(
                conn,
                resource_id=clar2,
                resource_state_version=_model().resource_state_version(clar2_row, task2_row),
            )
            assert wrong_grant.ok and wrong_grant.approval is not None
            req1 = await _request(
                conn,
                s,
                clar1,
                production_approval_reference=str(wrong_grant.approval["approval_id"]),
            )
            assert req1.ok
            async with conn.transaction():
                await s.authorize_resume(
                    conn,
                    str(req1.resume_request["resume_request_id"]),
                    actor=_authority(),
                    actor_scope=_scope(),
                    policy_version="v1",
                )
            _enable_command(monkeypatch)
            async with conn.transaction():
                rejected = await s.prepare_execution(
                    conn,
                    str(req1.resume_request["resume_request_id"]),
                    actor=_service_identity(),
                    actor_scope=_scope(),
                )
            assert rejected.reason_code == "production_approval_wrong_resource"

            # approval granted with a STALE state version for the SAME clarification
            await _reset_and_migrate(conn)
            _t3, clar3 = await _seed(conn, production_effect=True)
            stale_grant = await _grant(
                conn, resource_id=clar3, resource_state_version="stale:version:True"
            )
            assert stale_grant.ok and stale_grant.approval is not None
            req3 = await _request(
                conn,
                s,
                clar3,
                production_approval_reference=str(stale_grant.approval["approval_id"]),
            )
            assert req3.ok
            async with conn.transaction():
                await s.authorize_resume(
                    conn,
                    str(req3.resume_request["resume_request_id"]),
                    actor=_authority(),
                    actor_scope=_scope(),
                    policy_version="v1",
                )
            async with conn.transaction():
                rejected3 = await s.prepare_execution(
                    conn,
                    str(req3.resume_request["resume_request_id"]),
                    actor=_service_identity(),
                    actor_scope=_scope(),
                )
            assert rejected3.reason_code == "production_approval_stale_state"
        finally:
            await conn.close()

    _run(scenario())


# ---- Scope isolation --------------------------------------------------------------------


@requires_pg
def test_pg_cross_project_task_masked_and_null_scope_fail_closed(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            _t, clar = await _seed(conn, project_id=PROJECT_A)

            cross = await _request(conn, s, clar, scope=_scope(TEAM_A, PROJECT_B))
            assert not cross.ok and cross.result_kind == "not_found_masked"

            null_scope = await _request(conn, s, clar, scope=_scope(None, None))
            assert not null_scope.ok and null_scope.result_kind == "not_found_masked"

            ok = await _request(conn, s, clar, scope=_scope(TEAM_A, PROJECT_A))
            assert ok.ok
        finally:
            await conn.close()

    _run(scenario())


# ---- Transaction rollback ---------------------------------------------------------------


@requires_pg
def test_pg_outbox_failure_rolls_back_both_authorization_and_approval(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _svc()
            _enable_api(monkeypatch)
            _t, clar = await _seed(conn, production_effect=True)
            clar_row = dict(
                await conn.fetchrow(
                    "SELECT * FROM operator_clarification_requests WHERE id=$1", uuid.UUID(clar)
                )
            )
            task_row = dict(
                await conn.fetchrow("SELECT * FROM operator_tasks WHERE id=$1", uuid.UUID(_t))
            )
            state_version = _model().resource_state_version(clar_row, task_row)
            grant = await _grant(conn, resource_id=clar, resource_state_version=state_version)
            assert grant.ok and grant.approval is not None
            approval_id = str(grant.approval["approval_id"])

            req = await _request(conn, s, clar, production_approval_reference=approval_id)
            assert req.ok
            async with conn.transaction():
                await s.authorize_resume(
                    conn,
                    str(req.resume_request["resume_request_id"]),
                    actor=_authority(),
                    actor_scope=_scope(),
                    policy_version="v1",
                )
            _enable_command(monkeypatch)

            import shared.sdk.tasks.resume_service as rs

            async def boom(*a, **k):
                raise RuntimeError("outbox down")

            monkeypatch.setattr(rs.lifecycle_outbox, "insert_lifecycle_outbox_event", boom)
            with pytest.raises(RuntimeError):
                async with conn.transaction():
                    await s.prepare_execution(
                        conn,
                        str(req.resume_request["resume_request_id"]),
                        actor=_service_identity(),
                        actor_scope=_scope(),
                    )
            auth = await conn.fetchrow(
                "SELECT consumed_at FROM resume_replay_authorizations LIMIT 1"
            )
            assert auth["consumed_at"] is None
            approval_row = await conn.fetchrow(
                "SELECT state FROM production_action_approvals WHERE approval_id=$1",
                uuid.UUID(approval_id),
            )
            assert approval_row["state"] == "granted"
        finally:
            await conn.close()

    _run(scenario())
