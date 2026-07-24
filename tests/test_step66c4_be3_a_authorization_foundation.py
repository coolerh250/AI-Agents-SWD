"""Step 66C.4-BE3-A -- durable resume/replay authorization foundation tests.

DB-less unit tests (model/policy) + real-PostgreSQL 16 integration (migration, repository CAS,
RBAC, isolation, expiry, state-version, single-use consume, production gate, transaction safety,
privacy). Gated by the fail-closed guard (BE1_TEST_DATABASE_URL). Nothing executes resume/replay.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from step66c4_pg_safety import destructive_pg_refusal_reason

REPO = Path(__file__).resolve().parents[1]
MIGRATIONS = REPO / "migrations"


def _model():
    from shared.sdk.tasks import authorization_model

    return authorization_model


def _policy():
    from shared.sdk.tasks import authorization_policy

    return authorization_policy


def _repo():
    from shared.sdk.tasks import authorization_repository

    return authorization_repository


def _svc():
    from shared.sdk.tasks import authorization_service

    return authorization_service


# --------------------------------------------------------------------------------------
# DB-less unit tests
# --------------------------------------------------------------------------------------


def test_reason_code_allowlist_enforced() -> None:
    m = _model()
    assert m.assert_reason_code("policy_allow") == "policy_allow"
    assert m.assert_reason_code(None) is None
    with pytest.raises(ValueError):
        m.assert_reason_code("free text reason")


def test_audit_payload_rejects_unsafe_values() -> None:
    m = _model()
    ok = m.build_audit_payload(
        event="authorization.requested",
        authorization_id="a",
        action_type="replay",
        resource_type="outbox_event",
        resource_id="r",
        actor_id="alice",
        reason_code="policy_allow",
        state="pending",
    )
    assert "reason_code" in ok and ok["state"] == "pending"
    # A value that looks like a DSN/secret is rejected.
    with pytest.raises(ValueError):
        m.build_audit_payload(
            event="x",
            authorization_id="dsn=postgres://u:p@h/db",
            action_type="replay",
            resource_type="outbox_event",
            resource_id="r",
            actor_id="alice",
            reason_code="policy_allow",
            state="pending",
        )


def test_project_state_precedence() -> None:
    m = _model()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    future = now + timedelta(hours=1)
    past = now - timedelta(hours=1)
    base = {"decision": "authorized", "expires_at": future}
    assert m.project_state({**base, "consumed_at": now}, now=now) == "consumed"
    assert m.project_state({**base, "revoked_at": now}, now=now) == "revoked"
    assert m.project_state({**base, "expired_at": now}, now=now) == "expired"
    assert m.project_state({"decision": "authorized", "expires_at": past}, now=now) == "expired"
    assert m.project_state({"decision": "rejected"}, now=now) == "rejected"
    assert m.project_state({"decision": "canceled"}, now=now) == "canceled"
    assert m.project_state(base, now=now) == "authorized"
    assert m.project_state({"decision": "pending", "expires_at": future}, now=now) == "pending"


def test_policy_service_identity_and_two_person() -> None:
    p = _policy()
    sc = p.Scope("t1", "p1")
    op = p.Actor("alice", "agent_operator")
    appr = p.Actor("bob", "reviewer_approver")
    svc = p.Actor("svc", "service_identity", is_service_identity=True)
    # service identity: consume only.
    assert (
        p.evaluate(
            action="request_replay", actor=svc, actor_scope=sc, resource_scope=sc
        ).reason_code
        == "service_identity_cannot_decide"
    )
    assert p.evaluate(action="consume_replay", actor=svc, actor_scope=sc, resource_scope=sc).allowed
    # human cannot consume.
    assert not p.evaluate(
        action="consume_replay", actor=op, actor_scope=sc, resource_scope=sc
    ).allowed
    # two-person replay.
    assert p.evaluate(
        action="authorize_replay",
        actor=appr,
        actor_scope=sc,
        resource_scope=sc,
        requested_by="alice",
    ).allowed
    assert (
        p.evaluate(
            action="authorize_replay",
            actor=p.Actor("alice", "reviewer_approver"),
            actor_scope=sc,
            resource_scope=sc,
            requested_by="alice",
        ).reason_code
        == "two_person_required"
    )
    # cross-team masked.
    assert (
        p.evaluate(
            action="request_replay",
            actor=op,
            actor_scope=p.Scope("t1"),
            resource_scope=p.Scope("t2"),
        ).result_kind
        == "not_found_masked"
    )


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
    ):
        await _apply(conn, name)


def _future(hours: int = 1) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


async def _new_request(
    conn,
    *,
    action="replay",
    resource_id=None,
    requested_by="alice",
    role="agent_operator",
    state_version="v1",
    expires=None,
    key=None,
    team="t1",
    project="p1",
    production=False,
    prod_ref=None,
):
    r = _repo()
    return await r.create_request(
        conn,
        action_type=action,
        resource_type="outbox_event" if action == "replay" else "clarification",
        resource_id=resource_id or str(uuid.uuid4()),
        requested_by=requested_by,
        requested_role=role,
        resource_state_version=state_version,
        expires_at=expires or _future(),
        idempotency_key=key or f"{action}:{uuid.uuid4()}",
        team_id=team,
        project_id=project,
        production_effect=production,
        production_approval_reference=prod_ref,
    )


# ---- Migration ----------------------------------------------------------------------


@requires_pg
def test_pg_migration_up_down_reapply_and_constraints() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            # table + key constraints/indexes exist
            assert await conn.fetchval(
                "SELECT to_regclass('resume_replay_authorizations') IS NOT NULL"
            )
            cons = set(
                r["conname"]
                for r in await conn.fetch(
                    "SELECT conname FROM pg_constraint WHERE conrelid="
                    "'resume_replay_authorizations'::regclass"
                )
            )
            for c in (
                "chk_rra_action_type",
                "chk_rra_decision",
                "chk_rra_expiry_after_request",
                "chk_rra_consume_requires_authorized",
                "chk_rra_revoke_requires_authorized",
                "chk_rra_not_consumed_and_revoked",
                "chk_rra_replay_two_person",
                "uq_rra_idempotency_key",
            ):
                assert c in cons, c
            idx = set(
                r["indexname"]
                for r in await conn.fetch(
                    "SELECT indexname FROM pg_indexes WHERE tablename="
                    "'resume_replay_authorizations'"
                )
            )
            for i in (
                "uq_rra_active_request",
                "idx_rra_expiry_scan",
                "idx_rra_authorized_unconsumed",
            ):
                assert i in idx, i
            # existing feature unchanged: operator_tasks still present with a row insertable
            tid = await conn.fetchval(
                "INSERT INTO operator_tasks (title, task_type, created_by, status) "
                "VALUES ('t','software_delivery','a','draft') RETURNING id"
            )
            assert tid is not None
            # down + reapply is deterministic
            await _apply(conn, "032_be3_resume_replay_authorization_down.sql")
            assert await conn.fetchval("SELECT to_regclass('resume_replay_authorizations') IS NULL")
            await _apply(conn, "032_be3_resume_replay_authorization.sql")
            await _apply(conn, "032_be3_resume_replay_authorization.sql")  # idempotent re-apply
            assert await conn.fetchval(
                "SELECT to_regclass('resume_replay_authorizations') IS NOT NULL"
            )
        finally:
            await conn.close()

    _run(scenario())


# ---- Request + idempotency ----------------------------------------------------------


@requires_pg
def test_pg_request_and_active_uniqueness_and_idempotency() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            rid = str(uuid.uuid4())
            row = await _new_request(conn, resource_id=rid, key="k1")
            assert row["decision"] == "pending"
            # second ACTIVE request for the same (action, resource) -> unique violation
            with pytest.raises(asyncpg.UniqueViolationError):
                await _new_request(conn, resource_id=rid, key="k2")
            # duplicate idempotency_key -> unique violation
            with pytest.raises(asyncpg.UniqueViolationError):
                await _new_request(conn, resource_id=str(uuid.uuid4()), key="k1")
            # a DIFFERENT action on the same resource is allowed
            await _new_request(conn, action="resume", resource_id=rid, key="k3")
            # after the first is terminal (canceled), a new request is allowed
            r = _repo()
            await r.cancel(
                conn,
                str(row["authorization_id"]),
                decided_by="alice",
                decided_role="agent_operator",
                reason_code="operator_canceled",
            )
            await _new_request(conn, resource_id=rid, key="k4")
        finally:
            await conn.close()

    _run(scenario())


# ---- Decisions ----------------------------------------------------------------------


@requires_pg
def test_pg_decisions_approve_reject_cancel_revoke() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            r = _repo()
            # approve then revoke-before-consume
            a = await _new_request(conn, key="a")
            aid = str(a["authorization_id"])
            up = await r.approve(
                conn,
                aid,
                decided_by="bob",
                decided_role="reviewer_approver",
                reason_code="policy_allow",
                policy_result="allow",
                policy_version="p1",
            )
            assert up is not None and up["decision"] == "authorized"
            # duplicate approve is a no-op (CAS lost)
            assert (
                await r.approve(
                    conn,
                    aid,
                    decided_by="bob",
                    decided_role="reviewer_approver",
                    reason_code="policy_allow",
                    policy_result="allow",
                    policy_version="p1",
                )
                is None
            )
            rev = await r.revoke(conn, aid, revoked_by="bob", reason_code="operator_revoked")
            assert rev is not None and rev["revoked_at"] is not None
            # reject a fresh pending
            b = await _new_request(conn, key="b", resource_id=str(uuid.uuid4()))
            bid = str(b["authorization_id"])
            assert (
                await r.reject(
                    conn,
                    bid,
                    decided_by="bob",
                    decided_role="reviewer_approver",
                    reason_code="policy_deny",
                )
                is not None
            )
            # approve after reject is rejected (CAS lost)
            assert (
                await r.approve(
                    conn,
                    bid,
                    decided_by="bob",
                    decided_role="reviewer_approver",
                    reason_code="policy_allow",
                    policy_result="allow",
                    policy_version="p1",
                )
                is None
            )
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_db_rejects_replay_self_approval() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            r = _repo()
            a = await _new_request(conn, action="replay", requested_by="alice", key="s")
            aid = str(a["authorization_id"])
            # The DB two-person constraint rejects an approval by the requester.
            with pytest.raises(asyncpg.CheckViolationError):
                await r.approve(
                    conn,
                    aid,
                    decided_by="alice",
                    decided_role="reviewer_approver",
                    reason_code="policy_allow",
                    policy_result="allow",
                    policy_version="p1",
                )
        finally:
            await conn.close()

    _run(scenario())


# ---- Identity / RBAC via the service ------------------------------------------------


@requires_pg
def test_pg_service_rbac_isolation_and_service_identity() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s, p = _svc(), _policy()
            sc = p.Scope("t1", "p1")
            op = p.Actor("alice", "agent_operator")
            appr = p.Actor("bob", "reviewer_approver")
            svc = p.Actor("svc", "service_identity", is_service_identity=True)
            requester = p.Actor("mallory", "requester")

            rid = str(uuid.uuid4())
            # unauthorized role rejected (no DB row created)
            bad = await s.request_authorization(
                conn,
                actor=requester,
                actor_scope=sc,
                resource_scope=sc,
                action_type="replay",
                resource_type="outbox_event",
                resource_id=rid,
                resource_state_version="v1",
                expires_at=_future(),
                idempotency_key="x1",
            )
            assert not bad.ok and bad.result_kind == "forbidden"
            assert await conn.fetchval("SELECT count(*) FROM resume_replay_authorizations") == 0

            # operator requests
            req = await s.request_authorization(
                conn,
                actor=op,
                actor_scope=sc,
                resource_scope=sc,
                action_type="replay",
                resource_type="outbox_event",
                resource_id=rid,
                resource_state_version="v1",
                expires_at=_future(),
                idempotency_key="x2",
            )
            assert req.ok
            aid = str(req.authorization["authorization_id"])

            # service identity cannot approve
            assert (
                await s.authorize(conn, aid, actor=svc, actor_scope=sc, policy_version="p1")
            ).result_kind == "forbidden"
            # cross-team actor sees not_found_masked
            masked = await s.authorize(
                conn,
                aid,
                actor=p.Actor("z", "reviewer_approver"),
                actor_scope=p.Scope("t2", "p9"),
                policy_version="p1",
            )
            assert masked.result_kind == "not_found_masked"
            # approver (different principal) authorizes
            ok = await s.authorize(conn, aid, actor=appr, actor_scope=sc, policy_version="p1")
            assert ok.ok and ok.state == "authorized"
            # human cannot consume
            assert (
                await s.consume(conn, aid, actor=op, actor_scope=sc, resource_state_version="v1")
            ).result_kind == "forbidden"
            # service identity consumes
            consumed = await s.consume(
                conn, aid, actor=svc, actor_scope=sc, resource_state_version="v1"
            )
            assert consumed.ok and consumed.state == "consumed"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_replay_requester_cannot_self_approve_via_service() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s, p = _svc(), _policy()
            sc = p.Scope("t1", "p1")
            # alice is an operator who is ALSO able to act as approver role here, but is the requester
            req = await s.request_authorization(
                conn,
                actor=p.Actor("alice", "platform_admin"),
                actor_scope=sc,
                resource_scope=sc,
                action_type="replay",
                resource_type="outbox_event",
                resource_id=str(uuid.uuid4()),
                resource_state_version="v1",
                expires_at=_future(),
                idempotency_key="self",
            )
            aid = str(req.authorization["authorization_id"])
            self_appr = await s.authorize(
                conn,
                aid,
                actor=p.Actor("alice", "platform_admin"),
                actor_scope=sc,
                policy_version="p1",
            )
            assert (
                self_appr.result_kind == "forbidden"
                and self_appr.reason_code == "two_person_required"
            )
        finally:
            await conn.close()

    _run(scenario())


# ---- Expiry / state version ---------------------------------------------------------


@requires_pg
def test_pg_expiry_and_state_version_block_consume() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            r, s, p = _repo(), _svc(), _policy()
            sc = p.Scope("t1", "p1")
            svc = p.Actor("svc", "service_identity", is_service_identity=True)

            # expired authorization cannot consume. expires_at must be > requested_at, so create
            # with a short future deadline, then push it into the past and run the expiry scan.
            a = await _new_request(conn, key="exp", expires=_future(1))
            aid = str(a["authorization_id"])
            await r.approve(
                conn,
                aid,
                decided_by="bob",
                decided_role="reviewer_approver",
                reason_code="policy_allow",
                policy_result="allow",
                policy_version="p1",
            )
            # force the deadline into the past (backdating requested_at too so the
            # expires_at > requested_at constraint still holds), then run the expiry scan
            await conn.execute(
                "UPDATE resume_replay_authorizations "
                "SET requested_at=statement_timestamp() - interval '2 hours', "
                "    expires_at=statement_timestamp() - interval '1 hour' "
                "WHERE authorization_id=$1",
                uuid.UUID(aid),
            )
            assert await r.expire_due_authorizations(conn) >= 1
            res = await s.consume(conn, aid, actor=svc, actor_scope=sc, resource_state_version="v1")
            assert res.result_kind == "expired"

            # state-version mismatch cannot consume
            b = await _new_request(conn, key="sv", resource_id=str(uuid.uuid4()))
            bid = str(b["authorization_id"])
            await r.approve(
                conn,
                bid,
                decided_by="bob",
                decided_role="reviewer_approver",
                reason_code="policy_allow",
                policy_result="allow",
                policy_version="p1",
            )
            stale = await s.consume(
                conn, bid, actor=svc, actor_scope=sc, resource_state_version="v2-changed"
            )
            assert stale.result_kind == "stale_state"
            # the authorization remains durably non-consumed
            assert (await r.get_authorization(conn, bid))["consumed_at"] is None
        finally:
            await conn.close()

    _run(scenario())


# ---- Consumption single-use / concurrency -------------------------------------------


@requires_pg
def test_pg_single_use_and_concurrent_consume_exactly_one() -> None:
    async def scenario() -> None:
        setup = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(setup)
            r = _repo()
            a = await _new_request(setup, key="c", state_version="v1")
            aid = str(a["authorization_id"])
            await r.approve(
                setup,
                aid,
                decided_by="bob",
                decided_role="reviewer_approver",
                reason_code="policy_allow",
                policy_result="allow",
                policy_version="p1",
            )
        finally:
            await setup.close()

        async def one_consume():
            c = await asyncpg.connect(dsn=_DSN)
            try:
                async with c.transaction():
                    row = await _repo().consume(
                        c, aid, consumed_by="svc", resource_state_version="v1"
                    )
                    return row is not None
            finally:
                await c.close()

        results = await asyncio.gather(one_consume(), one_consume(), one_consume())
        assert sum(1 for x in results if x) == 1  # exactly one DB CAS wins

        verify = await asyncpg.connect(dsn=_DSN)
        try:
            row = await _repo().get_authorization(verify, aid)
            assert row["consumed_at"] is not None
            # a later consume is idempotently rejected (already consumed)
            again = await _repo().consume(
                verify, aid, consumed_by="svc", resource_state_version="v1"
            )
            assert again is None
        finally:
            await verify.close()

    _run(scenario())


# ---- Production gate ----------------------------------------------------------------


@requires_pg
def test_pg_production_gate_blocks_consume_without_reference() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            r, s, p = _repo(), _svc(), _policy()
            sc = p.Scope("t1", "p1")
            svc = p.Actor("svc", "service_identity", is_service_identity=True)
            # production-effect authorization with NO production approval reference
            a = await _new_request(conn, key="prod", production=True, prod_ref=None)
            aid = str(a["authorization_id"])
            await r.approve(
                conn,
                aid,
                decided_by="bob",
                decided_role="reviewer_approver",
                reason_code="policy_allow",
                policy_result="allow",
                policy_version="p1",
            )
            blocked = await s.consume(
                conn, aid, actor=svc, actor_scope=sc, resource_state_version="v1"
            )
            assert blocked.result_kind == "production_approval_required"
            assert (await r.get_authorization(conn, aid))["consumed_at"] is None
            # with a reference present, consume proceeds (BE3-A does not validate the ref itself)
            b = await _new_request(
                conn,
                key="prod2",
                resource_id=str(uuid.uuid4()),
                production=True,
                prod_ref="approval-123",
            )
            bid = str(b["authorization_id"])
            await r.approve(
                conn,
                bid,
                decided_by="bob",
                decided_role="reviewer_approver",
                reason_code="policy_allow",
                policy_result="allow",
                policy_version="p1",
            )
            ok = await s.consume(conn, bid, actor=svc, actor_scope=sc, resource_state_version="v1")
            assert ok.ok and ok.state == "consumed"
        finally:
            await conn.close()

    _run(scenario())


# ---- Transaction safety -------------------------------------------------------------


@requires_pg
def test_pg_process_failure_before_commit_leaves_no_partial_state() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s, p = _svc(), _policy()
            sc = p.Scope("t1", "p1")
            op = p.Actor("alice", "agent_operator")
            rid = str(uuid.uuid4())
            tx = conn.transaction()
            await tx.start()
            req = await s.request_authorization(
                conn,
                actor=op,
                actor_scope=sc,
                resource_scope=sc,
                action_type="replay",
                resource_type="outbox_event",
                resource_id=rid,
                resource_state_version="v1",
                expires_at=_future(),
                idempotency_key="rollback",
            )
            assert req.ok
            await tx.rollback()  # crash before commit
            # nothing persisted
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM resume_replay_authorizations WHERE resource_id=$1",
                    uuid.UUID(rid),
                )
                == 0
            )
        finally:
            await conn.close()

    _run(scenario())
