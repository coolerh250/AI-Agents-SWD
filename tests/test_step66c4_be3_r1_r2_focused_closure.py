"""Step 66C.4-BE3-R-FC -- INDEPENDENT focused-closure tests for findings M-1, L-1, R2-1.

Written by the original BE3-R independent reviewer to re-derive (not re-run the implementation's own
suites) the closure of the three remediation findings against real PostgreSQL 16:

- M-1: `production_approval_reference` now resolves against the authoritative
  `production_action_approvals` registry (migration 035) and is consumed single-use, atomically,
  in the SAME transaction as the BE3 authorization consume; every invalid/stale/expired/revoked/
  wrong-scope/wrong-resource/wrong-action reference fails closed with no consume; a post-approval-
  consume authorization CAS failure rolls the whole transaction back; the resolve holds a row lock
  (no TOCTOU).
- L-1: the per-actor replay-request rate cap is concurrency-safe (a PostgreSQL transaction-scoped
  advisory lock keyed on team+project+actor serializes check-then-insert), scoped per
  (team, project, actor), and cannot be exceeded under a concurrent burst.
- R2-1: resume `production_effect` is derived server-side from the owning task and folded into the
  canonical resource_state_version; a client cannot supply/upgrade/downgrade it; it is revalidated
  under lock at authorize and consume.

Gated by the fail-closed destructive-PG guard. Nothing calls a real orchestrator/replay_dead in any
shared runtime; nothing is deployed or activated.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime
from pathlib import Path

import pytest

from step66c4_pg_safety import destructive_pg_refusal_reason

try:
    import asyncpg

    _HAS_ASYNCPG = True
except Exception:  # pragma: no cover
    _HAS_ASYNCPG = False

REPO = Path(__file__).resolve().parents[1]
MIGRATIONS = REPO / "migrations"

TEAM_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
PROJECT_A = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
TEAM_B = "cccccccc-cccc-cccc-cccc-cccccccccccc"
PROJECT_B = "dddddddd-dddd-dddd-dddd-dddddddddddd"

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


# ---- imports of the code under review -----------------------------------------------------------


def _authz_repo():
    from shared.sdk.tasks import authorization_repository

    return authorization_repository


def _authz():
    from shared.sdk.tasks import authorization_service

    return authorization_service


def _policy():
    from shared.sdk.tasks import authorization_policy

    return authorization_policy


def _paa_model():
    from shared.sdk.tasks import production_approval_model

    return production_approval_model


def _paa_repo():
    from shared.sdk.tasks import production_approval_repository

    return production_approval_repository


def _paa_svc():
    from shared.sdk.tasks import production_approval_service

    return production_approval_service


def _replay_svc():
    from shared.sdk.tasks import replay_service

    return replay_service


def _replay_repo():
    from shared.sdk.tasks import replay_request_repository

    return replay_request_repository


def _replay_model():
    from shared.sdk.tasks import replay_request_model

    return replay_request_model


def _resume_svc():
    from shared.sdk.tasks import resume_service

    return resume_service


def _resume_model():
    from shared.sdk.tasks import resume_request_model

    return resume_request_model


# ---- schema / seed helpers ----------------------------------------------------------------------


async def _apply(conn, name: str) -> None:
    await conn.execute((MIGRATIONS / name).read_text(encoding="utf-8"))


async def _reset_and_migrate(conn) -> None:
    await conn.execute("DROP TABLE IF EXISTS replay_requests CASCADE;")
    await conn.execute("DROP TABLE IF EXISTS resume_requests CASCADE;")
    await conn.execute("DROP TABLE IF EXISTS production_action_approvals CASCADE;")
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
        "035_be3_production_action_approvals.sql",
    ):
        await _apply(conn, name)


async def _connect():
    return await asyncpg.connect(dsn=_DSN)


async def _future(conn, hours: int = 1) -> datetime:
    return await conn.fetchval(
        "SELECT statement_timestamp() + ($1 || ' hours')::interval", str(hours)
    )


def _op(principal="alice", role="agent_operator"):
    return _policy().Actor(principal, role)


def _approver(principal="carol", role="reviewer_approver"):
    return _policy().Actor(principal, role)


def _svc_identity(principal="svc"):
    return _policy().Actor(principal, "agent_operator", is_service_identity=True)


def _scope(team=TEAM_A, project=PROJECT_A):
    return _policy().Scope(team, project)


async def _grant_approval(
    conn,
    *,
    action="resume",
    resource_type="clarification",
    resource_id,
    version="v1",
    team=TEAM_A,
    project=PROJECT_A,
    hours=1,
    approver=None,
):
    svc = _paa_svc()
    res = await svc.grant_production_approval(
        conn,
        actor=approver or _approver(),
        actor_scope=_policy().Scope(team, project),
        action_type=action,
        resource_type=resource_type,
        resource_id=resource_id,
        resource_state_version=version,
        expires_at=await _future(conn, hours),
        idempotency_key=f"grant:{uuid.uuid4()}",
    )
    assert res.ok, res.reason_code
    return res.approval


async def _make_authorized_prod_auth(
    conn,
    *,
    action="resume",
    resource_type="clarification",
    resource_id=None,
    version="v1",
    team=TEAM_A,
    project=PROJECT_A,
    prod_ref=None,
    production=True,
    hours=1,
):
    r = _authz_repo()
    resource_id = resource_id or str(uuid.uuid4())
    row = await r.create_request(
        conn,
        action_type=action,
        resource_type=resource_type,
        resource_id=resource_id,
        requested_by="alice",
        requested_role="agent_operator",
        resource_state_version=version,
        expires_at=await _future(conn, hours),
        idempotency_key=f"{action}:{uuid.uuid4()}",
        team_id=team,
        project_id=project,
        production_effect=production,
        production_approval_reference=prod_ref,
    )
    approved = await r.approve(
        conn,
        str(row["authorization_id"]),
        decided_by="bob",
        decided_role="reviewer_approver",
        reason_code="policy_allow",
        policy_result="allow",
        policy_version="v1",
        scope_team_id=team,
        scope_project_id=project,
    )
    assert approved is not None
    return approved


async def _seed_resume(conn, *, production_effect=False, project_id=PROJECT_A):
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
    amsg = await conn.fetchval(
        "INSERT INTO task_messages (task_id, sender_type, sender_id, message_type, body) "
        "VALUES ($1, 'human', 'alice', 'clarification_answer', 'a') RETURNING id",
        task_id,
    )
    await conn.execute(
        "UPDATE operator_clarification_requests SET status='answered', "
        "answered_at=statement_timestamp(), answer_message_id=$2, "
        "resume_eligible_at=statement_timestamp() WHERE id=$1",
        clar_id,
        amsg,
    )
    return str(task_id), str(clar_id)


async def _seed_dead_event(conn, *, project_id=PROJECT_A, production_effect=False, attempts=5):
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
        "(clarification_id, task_id, event_type, idempotency_key, payload, status, attempts, dead_at) "
        "VALUES ($1, $2, 'clarification.expired', $3, '{}'::jsonb, 'dead', $4, statement_timestamp()) "
        "RETURNING id",
        clar_id,
        task_id,
        f"evt:{uuid.uuid4()}",
        attempts,
    )
    return str(task_id), str(event_id)


# =================================================================================================
# M-1 -- authoritative production-approval registry resolution + atomic single-use consume
# =================================================================================================


@requires_pg
async def test_m1_valid_approval_allows_production_consume_and_marks_consumed() -> None:
    conn = await _connect()
    try:
        await _reset_and_migrate(conn)
        resource_id = str(uuid.uuid4())
        approval = await _grant_approval(conn, resource_id=resource_id, version="v1")
        auth = await _make_authorized_prod_auth(
            conn, resource_id=resource_id, version="v1", prod_ref=str(approval["approval_id"])
        )
        async with conn.transaction():
            res = await _authz().consume(
                conn,
                str(auth["authorization_id"]),
                actor=_svc_identity(),
                actor_scope=_scope(),
                resource_state_version="v1",
            )
        assert res.ok, res.reason_code
        # approval is now consumed and traces back to the authorization
        arow = await conn.fetchrow(
            "SELECT state, consumed_at, consumed_by_authorization_id "
            "FROM production_action_approvals WHERE approval_id=$1",
            approval["approval_id"],
        )
        assert arow["state"] == "consumed"
        assert arow["consumed_at"] is not None
        assert str(arow["consumed_by_authorization_id"]) == str(auth["authorization_id"])
    finally:
        await conn.close()


@requires_pg
async def test_m1_every_invalid_reference_blocks_and_leaves_unconsumed() -> None:
    conn = await _connect()
    try:
        await _reset_and_migrate(conn)

        async def _consume_result(
            prod_ref,
            *,
            version="v1",
            action="resume",
            rtype="clarification",
            resource_id=None,
            scope=None,
        ):
            resource_id = resource_id or str(uuid.uuid4())
            auth = await _make_authorized_prod_auth(
                conn,
                action=action,
                resource_type=rtype,
                resource_id=resource_id,
                version=version,
                prod_ref=prod_ref,
            )
            try:
                async with conn.transaction():
                    r = await _authz().consume(
                        conn,
                        str(auth["authorization_id"]),
                        actor=_svc_identity(),
                        actor_scope=scope or _scope(),
                        resource_state_version=version,
                    )
            except Exception:  # a raise would also mean "not a clean success"
                r = None
            # authorization must remain unconsumed on every rejection
            consumed_at = await conn.fetchval(
                "SELECT consumed_at FROM resume_replay_authorizations WHERE authorization_id=$1",
                auth["authorization_id"],
            )
            return (r, consumed_at, resource_id)

        # 1. missing reference (None) -- blocked fail-closed by the policy layer BEFORE the resolver
        #    (production_effect present but no reference), authorization never consumed.
        r, c, _ = await _consume_result(None)
        assert (not r.ok) and c is None
        assert r.reason_code == "production_approval_required"
        assert r.result_kind == "production_approval_required"

        # 2. non-UUID reference
        r, c, _ = await _consume_result("not-a-uuid")
        assert (not r.ok) and c is None and r.reason_code == "production_approval_invalid_reference"

        # 3. unknown UUID
        r, c, _ = await _consume_result(str(uuid.uuid4()))
        assert (not r.ok) and c is None and r.reason_code == "production_approval_not_found"

        # 4. revoked approval
        rid = str(uuid.uuid4())
        appr = await _grant_approval(conn, resource_id=rid, version="v1")
        await _paa_svc().revoke_production_approval(
            conn, str(appr["approval_id"]), actor=_approver(), actor_scope=_scope()
        )
        r, c, _ = await _consume_result(str(appr["approval_id"]), resource_id=rid)
        assert (not r.ok) and c is None and r.reason_code == "production_approval_already_revoked"

        # 5. expired approval
        rid = str(uuid.uuid4())
        appr = await _paa_repo().insert_approval(
            conn,
            action_type="resume",
            resource_type="clarification",
            resource_id=rid,
            team_id=TEAM_A,
            project_id=PROJECT_A,
            resource_state_version="v1",
            granted_by="carol",
            granted_role="reviewer_approver",
            expires_at=await conn.fetchval("SELECT statement_timestamp() + interval '1 second'"),
            idempotency_key=f"grant:{uuid.uuid4()}",
        )
        await conn.execute("SELECT pg_sleep(1.2)")
        r, c, _ = await _consume_result(str(appr["approval_id"]), resource_id=rid)
        assert (not r.ok) and c is None and r.reason_code == "production_approval_expired"

        # 6. already-consumed approval (consume once via a first authorization, then reuse)
        rid = str(uuid.uuid4())
        appr = await _grant_approval(conn, resource_id=rid, version="v1")
        first = await _make_authorized_prod_auth(
            conn, resource_id=rid, version="v1", prod_ref=str(appr["approval_id"])
        )
        async with conn.transaction():
            ok = await _authz().consume(
                conn,
                str(first["authorization_id"]),
                actor=_svc_identity(),
                actor_scope=_scope(),
                resource_state_version="v1",
            )
        assert ok.ok
        r, c, _ = await _consume_result(str(appr["approval_id"]), resource_id=rid)
        assert (not r.ok) and c is None and r.reason_code == "production_approval_already_consumed"

        # 7. wrong action (approval granted for replay, authorization is resume)
        rid = str(uuid.uuid4())
        appr = await _grant_approval(
            conn, action="replay", resource_type="outbox_event", resource_id=rid, version="v1"
        )
        r, c, _ = await _consume_result(
            str(appr["approval_id"]),
            action="resume",
            rtype="clarification",
            resource_id=str(uuid.uuid4()),
        )
        assert (
            (not r.ok)
            and c is None
            and r.reason_code == "production_approval_wrong_resource"
            or r.reason_code == "production_approval_wrong_action"
        )

        # 8. wrong resource (approval for a different resource_id)
        appr = await _grant_approval(conn, resource_id=str(uuid.uuid4()), version="v1")
        r, c, _ = await _consume_result(str(appr["approval_id"]), resource_id=str(uuid.uuid4()))
        assert (not r.ok) and c is None and r.reason_code == "production_approval_wrong_resource"

        # 9. wrong scope (approval granted in TEAM_B/PROJECT_B)
        rid = str(uuid.uuid4())
        appr = await _grant_approval(
            conn,
            resource_id=rid,
            version="v1",
            team=TEAM_B,
            project=PROJECT_B,
            approver=_approver(),
        )
        # authorization + caller scope is TEAM_A/PROJECT_A -> wrong_scope
        r, c, _ = await _consume_result(str(appr["approval_id"]), resource_id=rid)
        assert (not r.ok) and c is None and r.reason_code == "production_approval_wrong_scope"

        # 10. stale resource-state-version (approval granted at v1, authorization/consume at v2)
        rid = str(uuid.uuid4())
        appr = await _grant_approval(conn, resource_id=rid, version="v1")
        r, c, _ = await _consume_result(str(appr["approval_id"]), resource_id=rid, version="v2")
        assert (not r.ok) and c is None and r.reason_code == "production_approval_stale_state"
    finally:
        await conn.close()


@requires_pg
async def test_m1_post_approval_consume_authz_failure_rolls_back_both() -> None:
    """If the approval is consumed but the authorization's own CAS then fails, the service RAISES so
    the whole transaction rolls back -- the approval is NOT left burned."""
    conn = await _connect()
    try:
        await _reset_and_migrate(conn)
        rid = str(uuid.uuid4())
        appr = await _grant_approval(conn, resource_id=rid, version="v1")
        auth = await _make_authorized_prod_auth(
            conn, resource_id=rid, version="v1", prod_ref=str(appr["approval_id"])
        )
        # Simulate the authorization already consumed by a concurrent path (committed).
        await conn.execute(
            "UPDATE resume_replay_authorizations "
            "SET consumed_at=statement_timestamp(), consumed_by='other' WHERE authorization_id=$1",
            auth["authorization_id"],
        )
        with pytest.raises(RuntimeError):
            async with conn.transaction():
                await _authz().consume(
                    conn,
                    str(auth["authorization_id"]),
                    actor=_svc_identity(),
                    actor_scope=_scope(),
                    resource_state_version="v1",
                )
        # after rollback the approval is still granted (not burned)
        st = await conn.fetchval(
            "SELECT state FROM production_action_approvals WHERE approval_id=$1",
            appr["approval_id"],
        )
        assert st == "granted"
    finally:
        await conn.close()


@requires_pg
async def test_m1_no_toctou_concurrent_revoke_vs_consume() -> None:
    """The resolver locks the approval FOR UPDATE, so a concurrent revoke and consume can never both
    succeed on the same approval."""
    setup = await _connect()
    try:
        await _reset_and_migrate(setup)
        rid = str(uuid.uuid4())
        appr = await _grant_approval(setup, resource_id=rid, version="v1")
        auth = await _make_authorized_prod_auth(
            setup, resource_id=rid, version="v1", prod_ref=str(appr["approval_id"])
        )
        approval_id = str(appr["approval_id"])
        auth_id = str(auth["authorization_id"])
    finally:
        await setup.close()

    async def _do_consume():
        c = await _connect()
        try:
            async with c.transaction():
                return (
                    "consume",
                    (
                        await _authz().consume(
                            c,
                            auth_id,
                            actor=_svc_identity(),
                            actor_scope=_scope(),
                            resource_state_version="v1",
                        )
                    ).ok,
                )
        except Exception:
            return ("consume", False)
        finally:
            await c.close()

    async def _do_revoke():
        c = await _connect()
        try:
            async with c.transaction():
                res = await _paa_svc().revoke_production_approval(
                    c, approval_id, actor=_approver(), actor_scope=_scope()
                )
                return ("revoke", res.ok)
        except Exception:
            return ("revoke", False)
        finally:
            await c.close()

    results = dict(await asyncio.gather(_do_consume(), _do_revoke()))
    # exactly one of {consume-succeeds, revoke-succeeds} may be true (never both burn the approval)
    assert not (results["consume"] and results["revoke"])
    assert results["consume"] or results["revoke"]

    verify = await _connect()
    try:
        st = await verify.fetchval(
            "SELECT state FROM production_action_approvals WHERE approval_id=$1",
            uuid.UUID(approval_id),
        )
        assert st in ("consumed", "revoked")
    finally:
        await verify.close()


@requires_pg
async def test_m1_replay_execute_outbox_failure_rolls_back_approval_and_dead_row(
    monkeypatch,
) -> None:
    """End-to-end replay execute with a valid production approval: if the audit-outbox insert fails,
    the approval consume, authorization consume and dead-row requeue all revert together."""
    monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
    monkeypatch.setenv("BE3_REPLAY_EXECUTION_ENABLED", "true")
    svc = _replay_svc()
    model = _replay_model()

    conn = await _connect()
    try:
        await _reset_and_migrate(conn)
        _, event_id = await _seed_dead_event(conn, production_effect=True, attempts=5)
        async with conn.transaction():
            req = await svc.request_replay(
                conn,
                actor=_op(),
                actor_scope=_scope(),
                outbox_event_id=event_id,
                idempotency_key=f"k:{uuid.uuid4()}",
                expires_at=await _future(conn),
            )
        assert req.ok, req.reason_code
        rid = str(req.replay_request["replay_request_id"])
        # server derived production_effect=True from the owning task
        auth_id = await conn.fetchval(
            "SELECT authorization_id FROM replay_requests WHERE replay_request_id=$1",
            uuid.UUID(rid),
        )
        prod = await conn.fetchval(
            "SELECT production_effect FROM resume_replay_authorizations WHERE authorization_id=$1",
            auth_id,
        )
        assert prod is True
        version = await conn.fetchval(
            "SELECT resource_state_version FROM resume_replay_authorizations WHERE authorization_id=$1",
            auth_id,
        )
        # grant a matching production approval and point the authorization at it
        appr = await _grant_approval(
            conn,
            action="replay",
            resource_type="outbox_event",
            resource_id=event_id,
            version=version,
        )
        await conn.execute(
            "UPDATE resume_replay_authorizations SET production_approval_reference=$2 "
            "WHERE authorization_id=$1",
            auth_id,
            str(appr["approval_id"]),
        )
        async with conn.transaction():
            await svc.authorize_replay(
                conn, rid, actor=_approver("dave"), actor_scope=_scope(), policy_version="v1"
            )

        # Force the audit-outbox insert (after consume) to raise, inside the execute transaction.
        from shared.sdk.tasks import lifecycle_outbox as lo

        real_insert = lo.insert_lifecycle_outbox_event

        async def _boom(*a, **k):
            raise RuntimeError("injected outbox failure")

        monkeypatch.setattr(lo, "insert_lifecycle_outbox_event", _boom)

        with pytest.raises(RuntimeError):
            async with conn.transaction():
                await svc.execute_authorized_replay(
                    conn,
                    rid,
                    actor=_svc_identity(),
                    actor_scope=_scope(),
                    readiness_provider=lambda _d: model.READINESS_READY,
                )
        monkeypatch.setattr(lo, "insert_lifecycle_outbox_event", real_insert)

        # everything reverted: approval granted, authorization unconsumed, dead row still dead
        assert (
            await conn.fetchval(
                "SELECT state FROM production_action_approvals WHERE approval_id=$1",
                appr["approval_id"],
            )
            == "granted"
        )
        assert (
            await conn.fetchval(
                "SELECT consumed_at FROM resume_replay_authorizations WHERE authorization_id=$1",
                auth_id,
            )
            is None
        )
        ev = await conn.fetchrow(
            "SELECT status, dead_at FROM clarification_lifecycle_outbox WHERE id=$1",
            uuid.UUID(event_id),
        )
        assert ev["status"] == "dead" and ev["dead_at"] is not None
    finally:
        await conn.close()


@requires_pg
async def test_m1_grant_boundary_is_approver_only() -> None:
    conn = await _connect()
    try:
        await _reset_and_migrate(conn)
        svc = _paa_svc()

        async def _try_grant(actor):
            return await svc.grant_production_approval(
                conn,
                actor=actor,
                actor_scope=_scope(),
                action_type="resume",
                resource_type="clarification",
                resource_id=str(uuid.uuid4()),
                resource_state_version="v1",
                expires_at=await _future(conn),
                idempotency_key=f"grant:{uuid.uuid4()}",
            )

        # ordinary Operator cannot grant
        assert (await _try_grant(_op("alice", "agent_operator"))).reason_code == "rbac_denied"
        assert (await _try_grant(_op("pm", "pm_engineering_lead"))).reason_code == "rbac_denied"
        # Service Identity cannot grant
        assert (await _try_grant(_svc_identity())).reason_code == "rbac_denied"
        # canonical Approver roles can
        assert (await _try_grant(_approver("carol", "reviewer_approver"))).ok
        assert (await _try_grant(_op("admin", "platform_admin"))).ok
    finally:
        await conn.close()


def test_m1_can_grant_is_canonical_approver_pair() -> None:
    m = _paa_model()
    assert m.can_grant("reviewer_approver") is True
    assert m.can_grant("platform_admin") is True
    for role in (
        "agent_operator",
        "pm_engineering_lead",
        "requester",
        "security_compliance_reviewer",
        "not_a_role",
    ):
        assert m.can_grant(role) is False


# =================================================================================================
# L-1 -- concurrency-safe per-actor replay-request rate cap (advisory lock)
# =================================================================================================


def test_l1_uses_pg_advisory_lock_not_python_hash() -> None:
    import inspect

    src = inspect.getsource(_replay_repo().acquire_actor_rate_limit_lock)
    assert "pg_advisory_xact_lock" in src, "must use a transaction-scoped advisory lock"
    assert "hashtextextended" in src, "must key on a PostgreSQL server-side hash"
    assert "hash(" not in src, "must NOT use Python's built-in hash() (not cross-process stable)"


async def _concurrent_requests(events, *, actor, scope):
    svc = _replay_svc()

    async def _req(eid):
        c = await _connect()
        try:
            async with c.transaction():
                return await svc.request_replay(
                    c,
                    actor=actor,
                    actor_scope=scope,
                    outbox_event_id=eid,
                    idempotency_key=f"k:{uuid.uuid4()}",
                    expires_at=await _future(c),
                )
        except Exception as exc:  # pragma: no cover - surfaced as a non-ok
            return exc
        finally:
            await c.close()

    return await asyncio.gather(*[_req(e) for e in events])


@requires_pg
async def test_l1_20_concurrent_requests_cap_10_exactly_10(monkeypatch) -> None:
    monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
    monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "10")
    setup = await _connect()
    try:
        await _reset_and_migrate(setup)
        events = [(await _seed_dead_event(setup))[1] for _ in range(20)]
    finally:
        await setup.close()

    results = await _concurrent_requests(events, actor=_op("storm"), scope=_scope())
    created = [r for r in results if not isinstance(r, Exception) and getattr(r, "ok", False)]
    limited = [
        r
        for r in results
        if not isinstance(r, Exception) and getattr(r, "reason_code", "") == "rate_limited"
    ]
    assert len(created) == 10, f"expected exactly 10 created, got {len(created)}"
    assert len(limited) == 10, f"expected exactly 10 rate_limited, got {len(limited)}"

    verify = await _connect()
    try:
        n = await verify.fetchval(
            "SELECT count(*) FROM replay_requests WHERE requested_by='storm' "
            "AND team_id=$1::uuid AND project_id=$2::uuid",
            TEAM_A,
            PROJECT_A,
        )
        assert n == 10
    finally:
        await verify.close()


@requires_pg
async def test_l1_50_concurrent_requests_cap_3_never_exceeds(monkeypatch) -> None:
    monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
    monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "3")
    setup = await _connect()
    try:
        await _reset_and_migrate(setup)
        events = [(await _seed_dead_event(setup))[1] for _ in range(50)]
    finally:
        await setup.close()

    results = await _concurrent_requests(events, actor=_op("flood"), scope=_scope())
    created = [r for r in results if not isinstance(r, Exception) and getattr(r, "ok", False)]
    assert len(created) <= 3, f"hard cap breached: {len(created)} created"
    assert len(created) == 3
    verify = await _connect()
    try:
        assert (
            await verify.fetchval("SELECT count(*) FROM replay_requests WHERE requested_by='flood'")
            == 3
        )
    finally:
        await verify.close()


@requires_pg
async def test_l1_caps_are_isolated_per_team_project_actor(monkeypatch) -> None:
    monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
    monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "1")
    setup = await _connect()
    try:
        await _reset_and_migrate(setup)
        e_a = (await _seed_dead_event(setup, project_id=PROJECT_A))[1]
        e_b = (await _seed_dead_event(setup, project_id=PROJECT_B))[1]
    finally:
        await setup.close()

    svc = _replay_svc()
    # same actor, project A: 1 allowed
    conn = await _connect()
    try:
        async with conn.transaction():
            r1 = await svc.request_replay(
                conn,
                actor=_op("multi"),
                actor_scope=_scope(TEAM_A, PROJECT_A),
                outbox_event_id=e_a,
                idempotency_key=f"k:{uuid.uuid4()}",
                expires_at=await _future(conn),
            )
        assert r1.ok
        # same actor, DIFFERENT project B: independent cap -> also allowed
        async with conn.transaction():
            r2 = await svc.request_replay(
                conn,
                actor=_op("multi"),
                actor_scope=_scope(TEAM_B, PROJECT_B),
                outbox_event_id=e_b,
                idempotency_key=f"k:{uuid.uuid4()}",
                expires_at=await _future(conn),
            )
        assert r2.ok, r2.reason_code
    finally:
        await conn.close()


@requires_pg
async def test_l1_idempotency_concurrency_yields_one_row(monkeypatch) -> None:
    monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
    monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "10")
    setup = await _connect()
    try:
        await _reset_and_migrate(setup)
        _, event_id = await _seed_dead_event(setup)
    finally:
        await setup.close()

    svc = _replay_svc()
    key = f"k:{uuid.uuid4()}"

    async def _req():
        c = await _connect()
        try:
            async with c.transaction():
                return await svc.request_replay(
                    c,
                    actor=_op("idem"),
                    actor_scope=_scope(),
                    outbox_event_id=event_id,
                    idempotency_key=key,
                    expires_at=await _future(c),
                )
        except Exception as exc:
            return exc
        finally:
            await c.close()

    await asyncio.gather(*[_req() for _ in range(6)])
    verify = await _connect()
    try:
        assert (
            await verify.fetchval(
                "SELECT count(*) FROM replay_requests WHERE idempotency_key=$1", key
            )
            == 1
        )
    finally:
        await verify.close()


@requires_pg
async def test_l1_advisory_lock_released_after_rollback(monkeypatch) -> None:
    """A rolled-back request transaction must not leave the advisory lock held (xact-scoped)."""
    monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
    monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "10")
    setup = await _connect()
    try:
        await _reset_and_migrate(setup)
        _, event_id = await _seed_dead_event(setup)
    finally:
        await setup.close()

    # Acquire the lock in a transaction then roll back.
    c1 = await _connect()
    try:
        tx = c1.transaction()
        await tx.start()
        await _replay_repo().acquire_actor_rate_limit_lock(
            c1, team_id=TEAM_A, project_id=PROJECT_A, actor_id="rb"
        )
        await tx.rollback()  # xact lock must release here
        # a fresh connection can immediately acquire the SAME key without blocking
        c2 = await _connect()
        try:
            got = await c2.fetchval(
                "SELECT pg_try_advisory_xact_lock(hashtextextended($1, 0))",
                "be3-replay-actor-rate:%s:%s:%s" % (TEAM_A, PROJECT_A, "rb"),
            )
            # try-lock succeeds only if no other session holds it
            assert got is True
        finally:
            await c2.close()
    finally:
        await c1.close()


@requires_pg
async def test_l1_platform_admin_cannot_bypass_and_invalid_config_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
    monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "1")
    setup = await _connect()
    try:
        await _reset_and_migrate(setup)
        e1 = (await _seed_dead_event(setup))[1]
        e2 = (await _seed_dead_event(setup))[1]
    finally:
        await setup.close()

    svc = _replay_svc()
    conn = await _connect()
    try:
        async with conn.transaction():
            r1 = await svc.request_replay(
                conn,
                actor=_op("admin", "platform_admin"),
                actor_scope=_scope(),
                outbox_event_id=e1,
                idempotency_key=f"k:{uuid.uuid4()}",
                expires_at=await _future(conn),
            )
        assert r1.ok
        async with conn.transaction():
            r2 = await svc.request_replay(
                conn,
                actor=_op("admin", "platform_admin"),
                actor_scope=_scope(),
                outbox_event_id=e2,
                idempotency_key=f"k:{uuid.uuid4()}",
                expires_at=await _future(conn),
            )
        assert (not r2.ok) and r2.reason_code == "rate_limited"
    finally:
        await conn.close()

    # invalid config fails closed (raises, never silently clamps)
    monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "0")
    with pytest.raises(ValueError):
        _replay_model().max_requests_per_actor_per_window()
    monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "abc")
    with pytest.raises(ValueError):
        _replay_model().max_requests_per_actor_per_window()


@requires_pg
async def test_l1_rolling_window_excludes_old_requests(monkeypatch) -> None:
    monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
    monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "1")
    monkeypatch.setenv("BE3_REPLAY_RATE_LIMIT_WINDOW_HOURS", "24")
    setup = await _connect()
    try:
        await _reset_and_migrate(setup)
        _, e_new = await _seed_dead_event(setup)
        # an older request (outside the 24h window) must not count against the cap
        _, e_old = await _seed_dead_event(setup)
        auth = await _make_authorized_prod_auth(
            setup,
            action="replay",
            resource_type="outbox_event",
            resource_id=e_old,
            version="x",
            production=False,
        )
        await setup.execute(
            "INSERT INTO replay_requests (authorization_id, outbox_event_id, event_type, "
            "destination, team_id, project_id, resource_state_version, requested_by, "
            "idempotency_key, requested_at, state) "
            "VALUES ($1,$2,'clarification.expired','audit',$3::uuid,$4::uuid,'x','win',$5, "
            "statement_timestamp() - interval '25 hours','executed')",
            auth["authorization_id"],
            uuid.UUID(e_old),
            TEAM_A,
            PROJECT_A,
            f"old:{uuid.uuid4()}",
        )
    finally:
        await setup.close()

    svc = _replay_svc()
    conn = await _connect()
    try:
        async with conn.transaction():
            r = await svc.request_replay(
                conn,
                actor=_op("win"),
                actor_scope=_scope(),
                outbox_event_id=e_new,
                idempotency_key=f"k:{uuid.uuid4()}",
                expires_at=await _future(conn),
            )
        assert r.ok, "a request older than the window must not consume the cap"
    finally:
        await conn.close()


@requires_pg
async def test_l1_per_event_successful_replay_cap_still_holds(monkeypatch) -> None:
    monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
    monkeypatch.setenv("BE3_REPLAY_MAX_SUCCESSFUL_PER_EVENT", "1")
    monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "100")
    conn = await _connect()
    try:
        await _reset_and_migrate(conn)
        _, event_id = await _seed_dead_event(conn)
        # record one prior successful replay for this event
        auth = await _make_authorized_prod_auth(
            conn,
            action="replay",
            resource_type="outbox_event",
            resource_id=event_id,
            version="x",
            production=False,
        )
        await conn.execute(
            "INSERT INTO replay_requests (authorization_id, outbox_event_id, event_type, "
            "destination, team_id, project_id, resource_state_version, requested_by, "
            "idempotency_key, executed_at, state) "
            "VALUES ($1,$2,'clarification.expired','audit',$3::uuid,$4::uuid,'x','a',$5, "
            "statement_timestamp(),'executed')",
            auth["authorization_id"],
            uuid.UUID(event_id),
            TEAM_A,
            PROJECT_A,
            f"s:{uuid.uuid4()}",
        )
        svc = _replay_svc()
        async with conn.transaction():
            r = await svc.request_replay(
                conn,
                actor=_op("z"),
                actor_scope=_scope(),
                outbox_event_id=event_id,
                idempotency_key=f"k:{uuid.uuid4()}",
                expires_at=await _future(conn),
            )
        assert (not r.ok) and r.reason_code == "rate_limited"
    finally:
        await conn.close()


# =================================================================================================
# R2-1 -- resume production-effect derived server-side, state-version-bound, revalidated
# =================================================================================================


def test_r2_api_schema_has_no_production_effect_field() -> None:
    import operations_resume_api as api

    fields = set(api.ResumeRequestCreate.model_fields)
    assert "production_effect" not in fields, "client must not be able to send production_effect"
    # a client that sends it anyway is ignored (Pydantic drops the unknown field by default)
    obj = api.ResumeRequestCreate(
        clarification_id="c",
        team_id=TEAM_A,
        project_id=PROJECT_A,
        idempotency_key="k",
        **{"production_effect": True},
    )
    assert not hasattr(obj, "production_effect")


def test_r2_state_version_includes_production_effect() -> None:
    m = _resume_model()
    clar = {"status": "answered", "answer_message_id": "m1"}
    v_prod = m.resource_state_version(clar, {"production_effect": True})
    v_nonprod = m.resource_state_version(clar, {"production_effect": False})
    assert v_prod != v_nonprod, "production_effect must be part of the canonical state version"
    # fail-closed: a missing production_effect is treated as production
    assert m.authoritative_production_effect({}) is True
    assert m.authoritative_production_effect({"production_effect": False}) is False


@requires_pg
async def test_r2_client_cannot_downgrade_production_task(monkeypatch) -> None:
    monkeypatch.setenv("BE3_RESUME_API_ENABLED", "true")
    svc = _resume_svc()
    conn = await _connect()
    try:
        await _reset_and_migrate(conn)
        _, clar_id = await _seed_resume(conn, production_effect=True)
        async with conn.transaction():
            # no production_effect argument exists to pass -- the server derives it
            res = await svc.request_resume(
                conn,
                actor=_op(),
                actor_scope=_scope(),
                clarification_id=clar_id,
                idempotency_key=f"k:{uuid.uuid4()}",
                expires_at=await _future(conn),
            )
        assert res.ok, res.reason_code
        auth_id = await conn.fetchval(
            "SELECT authorization_id FROM resume_requests WHERE resume_request_id=$1",
            res.resume_request["resume_request_id"],
        )
        prod = await conn.fetchval(
            "SELECT production_effect FROM resume_replay_authorizations WHERE authorization_id=$1",
            auth_id,
        )
        assert prod is True, "a production task must yield a production-effect authorization"
    finally:
        await conn.close()


@requires_pg
async def test_r2_client_cannot_upgrade_nonproduction_task(monkeypatch) -> None:
    monkeypatch.setenv("BE3_RESUME_API_ENABLED", "true")
    svc = _resume_svc()
    conn = await _connect()
    try:
        await _reset_and_migrate(conn)
        _, clar_id = await _seed_resume(conn, production_effect=False)
        async with conn.transaction():
            res = await svc.request_resume(
                conn,
                actor=_op(),
                actor_scope=_scope(),
                clarification_id=clar_id,
                idempotency_key=f"k:{uuid.uuid4()}",
                expires_at=await _future(conn),
            )
        assert res.ok
        auth_id = await conn.fetchval(
            "SELECT authorization_id FROM resume_requests WHERE resume_request_id=$1",
            res.resume_request["resume_request_id"],
        )
        prod = await conn.fetchval(
            "SELECT production_effect FROM resume_replay_authorizations WHERE authorization_id=$1",
            auth_id,
        )
        assert prod is False, "server classification stays non-production regardless of client"
    finally:
        await conn.close()


@requires_pg
async def test_r2_task_classification_change_invalidates_outstanding_request(monkeypatch) -> None:
    """non-production at request -> task flips to production before authorize -> stale_state, with no
    authorization consume and no side effect."""
    monkeypatch.setenv("BE3_RESUME_API_ENABLED", "true")
    svc = _resume_svc()
    conn = await _connect()
    try:
        await _reset_and_migrate(conn)
        task_id, clar_id = await _seed_resume(conn, production_effect=False)
        async with conn.transaction():
            res = await svc.request_resume(
                conn,
                actor=_op(),
                actor_scope=_scope(),
                clarification_id=clar_id,
                idempotency_key=f"k:{uuid.uuid4()}",
                expires_at=await _future(conn),
            )
        assert res.ok
        rid = str(res.resume_request["resume_request_id"])
        # task classification flips to production AFTER the request was recorded
        await conn.execute(
            "UPDATE operator_tasks SET production_effect=true WHERE id=$1", uuid.UUID(task_id)
        )
        from shared.sdk.tasks.authorization_policy import Actor

        authority = Actor("policy-safety", "platform_admin", is_policy_authority=True)
        async with conn.transaction():
            authd = await svc.authorize_resume(
                conn, rid, actor=authority, actor_scope=_scope(), policy_version="v1"
            )
        assert (not authd.ok) and authd.reason_code == "stale_state"
        # request stayed authorization_pending; the authorization was never authorized/consumed
        st = await conn.fetchval(
            "SELECT state FROM resume_requests WHERE resume_request_id=$1", uuid.UUID(rid)
        )
        assert st == "authorization_pending"
    finally:
        await conn.close()


@requires_pg
async def test_r2_scope_isolation_and_task_mismatch(monkeypatch) -> None:
    monkeypatch.setenv("BE3_RESUME_API_ENABLED", "true")
    svc = _resume_svc()
    conn = await _connect()
    try:
        await _reset_and_migrate(conn)
        _, clar_id = await _seed_resume(conn, production_effect=True, project_id=PROJECT_A)
        # cross-project caller scope -> masked not_found (task project cross-check)
        async with conn.transaction():
            res = await svc.request_resume(
                conn,
                actor=_op(),
                actor_scope=_scope(TEAM_A, PROJECT_B),
                clarification_id=clar_id,
                idempotency_key=f"k:{uuid.uuid4()}",
                expires_at=await _future(conn),
            )
        assert (not res.ok) and res.result_kind == "not_found_masked"
        # NULL scope -> fail closed
        async with conn.transaction():
            res2 = await svc.request_resume(
                conn,
                actor=_op(),
                actor_scope=_policy().Scope(None, None),
                clarification_id=clar_id,
                idempotency_key=f"k:{uuid.uuid4()}",
                expires_at=await _future(conn),
            )
        assert not res2.ok
    finally:
        await conn.close()
