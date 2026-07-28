"""Step 66C.4-BE3-R1 -- required findings remediation tests (M-1, L-1).

Real-PostgreSQL 16 integration covering the two mandatory-activation-precondition findings recorded
by the BE3-R combined independent review:

- M-1: `resume_replay_authorizations.production_approval_reference` must resolve against an
  authoritative registry (migration 035, `production_action_approvals`) -- exists, granted (not
  consumed/revoked/expired), and bound to the SAME action_type/resource_type/resource_id/team_id/
  project_id/resource_state_version as the authorization it backs -- not just checked non-empty.
  Both the resume AND replay consume paths are exercised (both go through the SAME shared
  `authorization_service.consume` resolver).
- L-1: the per-actor replay-request rate limit must be concurrency-safe (a PostgreSQL
  transaction-scoped advisory lock serializes the check-then-insert sequence) and isolated per
  (team_id, project_id, actor_id).

Gated by the fail-closed destructive-PG guard. Nothing calls a real orchestrator/replay_dead in any
shared runtime; nothing is deployed or activated.
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
TEAM_B = "cccccccc-cccc-cccc-cccc-cccccccccccc"
PROJECT_B = "dddddddd-dddd-dddd-dddd-dddddddddddd"


def _paa_model():
    from shared.sdk.tasks import production_approval_model

    return production_approval_model


def _paa_repo():
    from shared.sdk.tasks import production_approval_repository

    return production_approval_repository


def _paa_svc():
    from shared.sdk.tasks import production_approval_service

    return production_approval_service


def _authz():
    from shared.sdk.tasks import authorization_service

    return authorization_service


def _policy():
    from shared.sdk.tasks import authorization_policy

    return authorization_policy


def _resume_svc():
    from shared.sdk.tasks import resume_service

    return resume_service


def _resume_model():
    from shared.sdk.tasks import resume_request_model

    return resume_request_model


def _replay_svc():
    from shared.sdk.tasks import replay_service

    return replay_service


def _replay_repo():
    from shared.sdk.tasks import replay_request_repository

    return replay_request_repository


def _replay_model():
    from shared.sdk.tasks import replay_request_model

    return replay_request_model


# --------------------------------------------------------------------------------------
# DB-less unit tests
# --------------------------------------------------------------------------------------


def test_reason_code_allowlist_enforced() -> None:
    m = _paa_model()
    assert m.assert_reason_code("granted") == "granted"
    assert m.assert_reason_code(None) is None
    with pytest.raises(ValueError):
        m.assert_reason_code("free text")


def test_audit_payload_rejects_unsafe_values() -> None:
    m = _paa_model()
    ok = m.build_production_approval_audit_payload(
        event="production_approval.granted",
        approval_id="a1",
        action_type="resume",
        resource_type="clarification",
        resource_id="r1",
        actor_id="carol",
        reason_code="granted",
        state="granted",
    )
    assert ok["approval_id"] == "a1"
    with pytest.raises(ValueError):
        m.build_production_approval_audit_payload(
            event="x",
            approval_id="dsn=postgres://u:p@h/db",
            action_type="resume",
            resource_type="clarification",
            resource_id="r1",
            actor_id="carol",
            reason_code="granted",
            state="granted",
        )
    with pytest.raises(ValueError):
        m.build_production_approval_audit_payload(
            event="x",
            approval_id="a1",
            action_type="resume",
            resource_type="clarification",
            resource_id="r1",
            actor_id="carol",
            reason_code="not-on-the-allowlist",
            state="granted",
        )


def test_only_canonical_approver_roles_can_grant() -> None:
    m = _paa_model()
    assert m.can_grant("reviewer_approver") is True
    assert m.can_grant("platform_admin") is True
    for role in (
        "agent_operator",
        "pm_engineering_lead",
        "requester",
        "security_compliance_reviewer",
    ):
        assert m.can_grant(role) is False, role
    assert m.can_grant("not_a_real_role") is False


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
    for var in (
        "BE3_RESUME_API_ENABLED",
        "BE3_RESUME_COMMAND_ENABLED",
        "BE3_REPLAY_API_ENABLED",
        "BE3_REPLAY_EXECUTION_ENABLED",
        "BE3_REPLAY_MAX_SUCCESSFUL_PER_EVENT",
        "BE3_REPLAY_MAX_REQUESTS_PER_ACTOR",
        "BE3_REPLAY_RATE_LIMIT_WINDOW_HOURS",
    ):
        monkeypatch.delenv(var, raising=False)
    yield


async def _future(conn, hours: int = 1):
    return await conn.fetchval(
        "SELECT statement_timestamp() + ($1 || ' hours')::interval", str(hours)
    )


# ---- Fixtures: clarification (resume) and dead outbox event (replay) ----------------


async def _seed_clarification(conn, *, project_id: str | None = PROJECT_A) -> tuple[str, str]:
    task_id = await conn.fetchval(
        "INSERT INTO operator_tasks (title, task_type, created_by, status, project_id) "
        "VALUES ('t', 'software_delivery', 'alice', 'clarification_needed', $1) RETURNING id",
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


async def _seed_dead_event(
    conn,
    *,
    project_id: str | None = PROJECT_A,
    event_type: str = "clarification.expired",
    attempts: int = 5,
) -> tuple[str, str]:
    task_id = await conn.fetchval(
        "INSERT INTO operator_tasks (title, task_type, created_by, status, project_id, "
        "production_effect) VALUES ('t', 'software_delivery', 'alice', 'clarification_needed', "
        "$1, false) RETURNING id",
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
        "VALUES ($1, $2, 'expired', 'q', 'human', 'alice', "
        "        statement_timestamp() - interval '1 day', statement_timestamp() - interval '2 day') "
        "RETURNING id",
        task_id,
        qmsg,
    )
    event_id = await conn.fetchval(
        "INSERT INTO clarification_lifecycle_outbox "
        "(clarification_id, task_id, event_type, idempotency_key, payload, status, attempts, "
        " dead_at) "
        "VALUES ($1, $2, $3, $4, '{}'::jsonb, 'dead', $5, statement_timestamp()) "
        "RETURNING id",
        clar_id,
        task_id,
        event_type,
        f"evt:{uuid.uuid4()}",
        attempts,
    )
    return str(task_id), str(event_id)


async def _real_authorization_id(
    conn,
    *,
    resource_id: str,
    action_type: str = "resume",
    resource_type: str = "clarification",
    state_version: str = "v1",
) -> str:
    """Insert a minimal, real resume_replay_authorizations row and return its id -- needed anywhere
    a test drives resolve_and_consume_approval to a SUCCESSFUL consume, since
    production_action_approvals.consumed_by_authorization_id has a real FK to that table (an
    arbitrary uuid4() is rejected, by design -- the audit trail must always point at a real
    authorization, never a fabricated one)."""
    from shared.sdk.tasks import authorization_repository as arepo

    row = await arepo.create_request(
        conn,
        action_type=action_type,
        resource_type=resource_type,
        resource_id=resource_id,
        requested_by="alice",
        requested_role="agent_operator",
        resource_state_version=state_version,
        expires_at=await _future(conn),
        idempotency_key=f"real-auth:{uuid.uuid4()}",
        team_id=TEAM_A,
        project_id=PROJECT_A,
    )
    return str(row["authorization_id"])


async def _grant(
    conn,
    *,
    action_type: str,
    resource_type: str,
    resource_id: str,
    resource_state_version: str,
    scope=None,
    actor=None,
    expires_hours: int = 1,
    idempotency_key: str | None = None,
):
    approvals = _paa_svc()
    async with conn.transaction():
        return await approvals.grant_production_approval(
            conn,
            actor=actor or _approver(),
            actor_scope=scope or _scope(),
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_state_version=resource_state_version,
            expires_at=await _future(conn, expires_hours),
            idempotency_key=idempotency_key or f"grant:{uuid.uuid4()}",
        )


# ==== M-1: resolve_and_consume_approval -- direct repository-level coverage ===========


@requires_pg
def test_pg_m1_missing_and_unknown_and_invalid_reference_rejected() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            repo = _paa_repo()
            common = dict(
                action_type="resume",
                resource_type="clarification",
                resource_id=str(uuid.uuid4()),
                team_id=TEAM_A,
                project_id=PROJECT_A,
                resource_state_version="v1",
                consumed_by="svc",
                consumed_by_authorization_id=str(uuid.uuid4()),
            )
            missing_row, missing_reason = await repo.resolve_and_consume_approval(
                conn, None, **common
            )
            assert missing_row is None and missing_reason == "not_found"

            unknown_row, unknown_reason = await repo.resolve_and_consume_approval(
                conn, str(uuid.uuid4()), **common
            )
            assert unknown_row is None and unknown_reason == "not_found"

            invalid_row, invalid_reason = await repo.resolve_and_consume_approval(
                conn, "not-a-uuid-at-all", **common
            )
            assert invalid_row is None and invalid_reason == "invalid_reference"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_m1_revoked_and_expired_and_already_consumed_rejected() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            repo = _paa_repo()
            svc = _paa_svc()

            # revoked
            rid = str(uuid.uuid4())
            g1 = await _grant(
                conn,
                action_type="resume",
                resource_type="clarification",
                resource_id=rid,
                resource_state_version="v1",
            )
            assert g1.ok and g1.approval is not None
            aid1 = str(g1.approval["approval_id"])
            async with conn.transaction():
                rev = await svc.revoke_production_approval(
                    conn, aid1, actor=_approver(), actor_scope=_scope()
                )
            assert rev.ok
            row, reason = await repo.resolve_and_consume_approval(
                conn,
                aid1,
                action_type="resume",
                resource_type="clarification",
                resource_id=rid,
                team_id=TEAM_A,
                project_id=PROJECT_A,
                resource_state_version="v1",
                consumed_by="svc",
                consumed_by_authorization_id=str(uuid.uuid4()),
            )
            assert row is None and reason == "already_revoked"

            # expired (grant with an already-past expiry via direct repository insert)
            rid2 = str(uuid.uuid4())
            past = await conn.fetchval("SELECT statement_timestamp() - interval '1 hour'")
            granted_at = await conn.fetchval("SELECT statement_timestamp() - interval '2 hour'")
            aid2 = await conn.fetchval(
                "INSERT INTO production_action_approvals "
                "(action_type, resource_type, resource_id, team_id, project_id, "
                " resource_state_version, granted_by, granted_role, granted_at, expires_at, "
                " idempotency_key) "
                "VALUES ('resume','clarification',$1,$2,$3,'v1','carol','reviewer_approver',$4,$5,$6) "
                "RETURNING approval_id",
                uuid.UUID(rid2),
                uuid.UUID(TEAM_A),
                uuid.UUID(PROJECT_A),
                granted_at,
                past,
                f"grant:{uuid.uuid4()}",
            )
            row2, reason2 = await repo.resolve_and_consume_approval(
                conn,
                str(aid2),
                action_type="resume",
                resource_type="clarification",
                resource_id=rid2,
                team_id=TEAM_A,
                project_id=PROJECT_A,
                resource_state_version="v1",
                consumed_by="svc",
                consumed_by_authorization_id=str(uuid.uuid4()),
            )
            assert row2 is None and reason2 == "expired"

            # already consumed
            rid3 = str(uuid.uuid4())
            g3 = await _grant(
                conn,
                action_type="resume",
                resource_type="clarification",
                resource_id=rid3,
                resource_state_version="v1",
            )
            assert g3.ok and g3.approval is not None
            aid3 = str(g3.approval["approval_id"])
            first_auth = await _real_authorization_id(conn, resource_id=rid3)
            row3a, reason3a = await repo.resolve_and_consume_approval(
                conn,
                aid3,
                action_type="resume",
                resource_type="clarification",
                resource_id=rid3,
                team_id=TEAM_A,
                project_id=PROJECT_A,
                resource_state_version="v1",
                consumed_by="svc",
                consumed_by_authorization_id=first_auth,
            )
            assert row3a is not None and reason3a == "ok"
            row3b, reason3b = await repo.resolve_and_consume_approval(
                conn,
                aid3,
                action_type="resume",
                resource_type="clarification",
                resource_id=rid3,
                team_id=TEAM_A,
                project_id=PROJECT_A,
                resource_state_version="v1",
                consumed_by="svc",
                consumed_by_authorization_id=str(uuid.uuid4()),
            )
            assert row3b is None and reason3b == "already_consumed"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_m1_wrong_scope_resource_action_and_stale_version_rejected() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            repo = _paa_repo()
            rid = str(uuid.uuid4())
            g = await _grant(
                conn,
                action_type="resume",
                resource_type="clarification",
                resource_id=rid,
                resource_state_version="v1",
            )
            assert g.ok and g.approval is not None
            aid = str(g.approval["approval_id"])
            base = dict(
                action_type="resume",
                resource_type="clarification",
                resource_id=rid,
                team_id=TEAM_A,
                project_id=PROJECT_A,
                resource_state_version="v1",
                consumed_by="svc",
            )

            wrong_team_row, wrong_team_reason = await repo.resolve_and_consume_approval(
                conn,
                aid,
                **{**base, "team_id": TEAM_B},
                consumed_by_authorization_id=str(uuid.uuid4()),
            )
            assert wrong_team_row is None and wrong_team_reason == "wrong_scope"

            wrong_project_row, wrong_project_reason = await repo.resolve_and_consume_approval(
                conn,
                aid,
                **{**base, "project_id": PROJECT_B},
                consumed_by_authorization_id=str(uuid.uuid4()),
            )
            assert wrong_project_row is None and wrong_project_reason == "wrong_scope"

            wrong_resource_row, wrong_resource_reason = await repo.resolve_and_consume_approval(
                conn,
                aid,
                **{**base, "resource_id": str(uuid.uuid4())},
                consumed_by_authorization_id=str(uuid.uuid4()),
            )
            assert wrong_resource_row is None and wrong_resource_reason == "wrong_resource"

            wrong_action_row, wrong_action_reason = await repo.resolve_and_consume_approval(
                conn,
                aid,
                **{**base, "action_type": "replay"},
                consumed_by_authorization_id=str(uuid.uuid4()),
            )
            assert wrong_action_row is None and wrong_action_reason == "wrong_action"

            stale_row, stale_reason = await repo.resolve_and_consume_approval(
                conn,
                aid,
                **{**base, "resource_state_version": "v-stale"},
                consumed_by_authorization_id=str(uuid.uuid4()),
            )
            assert stale_row is None and stale_reason == "stale_state"

            # the approval is UNTOUCHED after every rejected attempt above -- still resolvable
            still_granted = await conn.fetchval(
                "SELECT state FROM production_action_approvals WHERE approval_id=$1", uuid.UUID(aid)
            )
            assert still_granted == "granted"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_m1_concurrent_revoke_and_consume_one_safe_outcome() -> None:
    async def scenario() -> None:
        setup = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(setup)
            rid = str(uuid.uuid4())
            g = await _grant(
                setup,
                action_type="resume",
                resource_type="clarification",
                resource_id=rid,
                resource_state_version="v1",
            )
            assert g.ok and g.approval is not None
            aid = str(g.approval["approval_id"])
            real_auth_id = await _real_authorization_id(setup, resource_id=rid)
        finally:
            await setup.close()

        svc = _paa_svc()
        repo = _paa_repo()

        async def do_revoke():
            c = await asyncpg.connect(dsn=_DSN)
            try:
                async with c.transaction():
                    r = await svc.revoke_production_approval(
                        c, aid, actor=_approver(), actor_scope=_scope()
                    )
                return ("revoke", r.ok)
            finally:
                await c.close()

        async def do_consume():
            c = await asyncpg.connect(dsn=_DSN)
            try:
                async with c.transaction():
                    row, reason = await repo.resolve_and_consume_approval(
                        c,
                        aid,
                        action_type="resume",
                        resource_type="clarification",
                        resource_id=rid,
                        team_id=TEAM_A,
                        project_id=PROJECT_A,
                        resource_state_version="v1",
                        consumed_by="svc",
                        consumed_by_authorization_id=real_auth_id,
                    )
                return ("consume", row is not None)
            finally:
                await c.close()

        results = await asyncio.gather(do_revoke(), do_consume())
        wins = sum(1 for _kind, ok in results if ok)
        assert wins == 1  # exactly one of {revoke, consume} succeeds -- never both, never neither

        verify = await asyncpg.connect(dsn=_DSN)
        try:
            state = await verify.fetchval(
                "SELECT state FROM production_action_approvals WHERE approval_id=$1", uuid.UUID(aid)
            )
            assert state in ("revoked", "consumed")
        finally:
            await verify.close()

    _run(scenario())


# ==== M-1: end-to-end through the shared authorization_service.consume resolver ======


@requires_pg
def test_pg_m1_resume_consume_end_to_end_valid_and_invalid() -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            authz = _authz()
            _t, clar = await _seed_clarification(conn)
            state_version = _resume_model().resource_state_version(
                dict(
                    await conn.fetchrow(
                        "SELECT * FROM operator_clarification_requests WHERE id=$1",
                        uuid.UUID(clar),
                    )
                ),
                dict(
                    await conn.fetchrow("SELECT * FROM operator_tasks WHERE id=$1", uuid.UUID(_t))
                ),
            )
            # invalid reference never lets the authorization consume (no approval need be granted at
            # all for this half -- an invalid/unresolvable reference is rejected regardless)
            from shared.sdk.tasks import authorization_repository as arepo

            async with conn.transaction():
                bad_auth = await arepo.create_request(
                    conn,
                    action_type="resume",
                    resource_type="clarification",
                    resource_id=clar,
                    requested_by="alice",
                    requested_role="agent_operator",
                    resource_state_version=state_version,
                    expires_at=await _future(conn),
                    idempotency_key=f"bad:{uuid.uuid4()}",
                    team_id=TEAM_A,
                    project_id=PROJECT_A,
                    production_effect=True,
                    production_approval_reference="totally-bogus",
                )
                await arepo.approve(
                    conn,
                    str(bad_auth["authorization_id"]),
                    decided_by="policy-safety",
                    decided_role="platform_admin",
                    reason_code="policy_allow",
                    policy_result="allow",
                    policy_version="v1",
                    scope_team_id=TEAM_A,
                    scope_project_id=PROJECT_A,
                )
            bad = await authz.consume(
                conn,
                str(bad_auth["authorization_id"]),
                actor=_service_identity(),
                actor_scope=_scope(),
                resource_state_version=state_version,
            )
            assert not bad.ok and bad.reason_code == "production_approval_invalid_reference"

            # a REAL granted approval lets the resume authorization consume. A FRESH clarification is
            # used here (bad_auth above stays 'authorized'/active on the first one -- rejected because
            # the approval was invalid, not because the authorization itself is unusable -- so it
            # still holds that clarification's one-active-authorization slot).
            _t2, clar2 = await _seed_clarification(conn)
            state_version2 = _resume_model().resource_state_version(
                dict(
                    await conn.fetchrow(
                        "SELECT * FROM operator_clarification_requests WHERE id=$1",
                        uuid.UUID(clar2),
                    )
                ),
                dict(
                    await conn.fetchrow("SELECT * FROM operator_tasks WHERE id=$1", uuid.UUID(_t2))
                ),
            )
            g2 = await _grant(
                conn,
                action_type="resume",
                resource_type="clarification",
                resource_id=clar2,
                resource_state_version=state_version2,
            )
            assert g2.ok and g2.approval is not None
            async with conn.transaction():
                good_auth = await arepo.create_request(
                    conn,
                    action_type="resume",
                    resource_type="clarification",
                    resource_id=clar2,
                    requested_by="alice",
                    requested_role="agent_operator",
                    resource_state_version=state_version2,
                    expires_at=await _future(conn),
                    idempotency_key=f"good:{uuid.uuid4()}",
                    team_id=TEAM_A,
                    project_id=PROJECT_A,
                    production_effect=True,
                    production_approval_reference=str(g2.approval["approval_id"]),
                )
                await arepo.approve(
                    conn,
                    str(good_auth["authorization_id"]),
                    decided_by="policy-safety",
                    decided_role="platform_admin",
                    reason_code="policy_allow",
                    policy_result="allow",
                    policy_version="v1",
                    scope_team_id=TEAM_A,
                    scope_project_id=PROJECT_A,
                )
            good = await authz.consume(
                conn,
                str(good_auth["authorization_id"]),
                actor=_service_identity(),
                actor_scope=_scope(),
                resource_state_version=state_version2,
            )
            assert good.ok and good.state == "consumed"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_m1_replay_consume_end_to_end_valid_and_invalid(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            s = _replay_svc()
            model = _replay_model()
            monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
            monkeypatch.setenv("BE3_REPLAY_EXECUTION_ENABLED", "true")

            def _ready(_destination: str) -> str:
                return model.READINESS_READY

            async def _state_version(event_id: str) -> str:
                row = await conn.fetchrow(
                    "SELECT dead_at, attempts FROM clarification_lifecycle_outbox WHERE id=$1",
                    uuid.UUID(event_id),
                )
                return model.dead_episode_state_version(
                    dead_at=row["dead_at"], attempts=row["attempts"]
                )

            # --- invalid reference never lets the replay execute, and never mutates the dead row ---
            _t, bad_event_id = await _seed_dead_event(conn)
            await conn.execute(
                "UPDATE operator_tasks SET production_effect=true WHERE id=$1", uuid.UUID(_t)
            )
            async with conn.transaction():
                bad_req = await s.request_replay(
                    conn,
                    actor=_op(),
                    actor_scope=_scope(),
                    outbox_event_id=bad_event_id,
                    idempotency_key=f"bad:{uuid.uuid4()}",
                    expires_at=await _future(conn),
                    production_approval_reference="totally-bogus",
                )
            assert bad_req.ok, bad_req.reason_code
            bad_rid = str(bad_req.replay_request["replay_request_id"])
            async with conn.transaction():
                await s.authorize_replay(
                    conn, bad_rid, actor=_approver(), actor_scope=_scope(), policy_version="v1"
                )
            bad_exec = await s.execute_authorized_replay(
                conn,
                bad_rid,
                actor=_service_identity(),
                actor_scope=_scope(),
                readiness_provider=_ready,
            )
            assert not bad_exec.ok
            assert bad_exec.reason_code == "production_approval_invalid_reference"
            still_dead = await conn.fetchval(
                "SELECT status FROM clarification_lifecycle_outbox WHERE id=$1",
                uuid.UUID(bad_event_id),
            )
            assert still_dead == "dead"  # no replay_dead mutation on a rejected approval

            # --- a REAL, resource-bound, granted approval lets the replay execute -------------------
            _t2, good_event_id = await _seed_dead_event(conn)
            await conn.execute(
                "UPDATE operator_tasks SET production_effect=true WHERE id=$1", uuid.UUID(_t2)
            )
            good_state_version = await _state_version(good_event_id)
            g = await _grant(
                conn,
                action_type="replay",
                resource_type="outbox_event",
                resource_id=good_event_id,
                resource_state_version=good_state_version,
            )
            assert g.ok and g.approval is not None
            async with conn.transaction():
                good_req = await s.request_replay(
                    conn,
                    actor=_op("dan"),
                    actor_scope=_scope(),
                    outbox_event_id=good_event_id,
                    idempotency_key=f"good:{uuid.uuid4()}",
                    expires_at=await _future(conn),
                    production_approval_reference=str(g.approval["approval_id"]),
                )
            assert good_req.ok, good_req.reason_code
            good_rid = str(good_req.replay_request["replay_request_id"])
            async with conn.transaction():
                await s.authorize_replay(
                    conn, good_rid, actor=_approver(), actor_scope=_scope(), policy_version="v1"
                )
            good_exec = await s.execute_authorized_replay(
                conn,
                good_rid,
                actor=_service_identity(),
                actor_scope=_scope(),
                readiness_provider=_ready,
            )
            assert good_exec.ok and good_exec.state == "executed"
            approval_row = await conn.fetchrow(
                "SELECT state FROM production_action_approvals WHERE approval_id=$1",
                uuid.UUID(str(g.approval["approval_id"])),
            )
            assert approval_row["state"] == "consumed"
        finally:
            await conn.close()

    _run(scenario())


# ==== L-1: concurrency-safe per-actor replay rate limit ==============================


@requires_pg
def test_pg_l1_twenty_concurrent_requests_same_actor_exactly_cap_created(monkeypatch) -> None:
    async def scenario() -> None:
        setup = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(setup)
            monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
            monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "10")
            event_ids = []
            for _ in range(20):
                _t, eid = await _seed_dead_event(setup)
                event_ids.append(eid)
        finally:
            await setup.close()

        s = _replay_svc()

        async def attempt(event_id: str):
            c = await asyncpg.connect(dsn=_DSN)
            try:
                async with c.transaction():
                    return await s.request_replay(
                        c,
                        actor=_op("alice"),
                        actor_scope=_scope(),
                        outbox_event_id=event_id,
                        idempotency_key=f"burst:{uuid.uuid4()}",
                        expires_at=await _future(c),
                    )
            finally:
                await c.close()

        results = await asyncio.gather(*(attempt(e) for e in event_ids))
        created = sum(1 for r in results if r.ok)
        rate_limited = sum(1 for r in results if not r.ok and r.reason_code == "rate_limited")
        assert created == 10
        assert rate_limited == 10

    _run(scenario())


@requires_pg
def test_pg_l1_fifty_concurrent_requests_never_exceed_hard_cap(monkeypatch) -> None:
    async def scenario() -> None:
        setup = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(setup)
            monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
            monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "3")
            event_ids = []
            for _ in range(50):
                _t, eid = await _seed_dead_event(setup)
                event_ids.append(eid)
        finally:
            await setup.close()

        s = _replay_svc()

        async def attempt(event_id: str):
            c = await asyncpg.connect(dsn=_DSN)
            try:
                async with c.transaction():
                    return await s.request_replay(
                        c,
                        actor=_op("alice"),
                        actor_scope=_scope(),
                        outbox_event_id=event_id,
                        idempotency_key=f"burst2:{uuid.uuid4()}",
                        expires_at=await _future(c),
                    )
            finally:
                await c.close()

        results = await asyncio.gather(*(attempt(e) for e in event_ids))
        created = sum(1 for r in results if r.ok)
        assert created == 3  # never overshoots the configured hard cap under a 50-way burst

    _run(scenario())


@requires_pg
def test_pg_l1_concurrent_same_idempotency_key_counted_once(monkeypatch) -> None:
    async def scenario() -> None:
        setup = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(setup)
            monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
            monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "5")
            _t, event_id = await _seed_dead_event(setup)
        finally:
            await setup.close()

        s = _replay_svc()
        key = f"same-key:{uuid.uuid4()}"

        async def attempt():
            c = await asyncpg.connect(dsn=_DSN)
            try:
                async with c.transaction():
                    return await s.request_replay(
                        c,
                        actor=_op("alice"),
                        actor_scope=_scope(),
                        outbox_event_id=event_id,
                        idempotency_key=key,
                        expires_at=await _future(c),
                    )
            finally:
                await c.close()

        results = await asyncio.gather(*(attempt() for _ in range(5)), return_exceptions=True)
        oks = [r for r in results if not isinstance(r, BaseException) and r.ok]
        assert len(oks) >= 1

        verify = await asyncpg.connect(dsn=_DSN)
        try:
            count = await verify.fetchval(
                "SELECT count(*) FROM replay_requests WHERE idempotency_key=$1", key
            )
            assert count == 1  # never a second durable row for the same idempotency key
            actor_count = await verify.fetchval(
                "SELECT count(*) FROM replay_requests WHERE requested_by='alice'"
            )
            assert actor_count == 1  # counted exactly once, not once per concurrent retry
        finally:
            await verify.close()

    _run(scenario())


@requires_pg
def test_pg_l1_different_actors_independent_limits(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
            monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "1")
            s = _replay_svc()
            _t1, e1 = await _seed_dead_event(conn)
            _t2, e2 = await _seed_dead_event(conn)
            async with conn.transaction():
                r1 = await s.request_replay(
                    conn,
                    actor=_op("alice"),
                    actor_scope=_scope(),
                    outbox_event_id=e1,
                    idempotency_key=f"a1:{uuid.uuid4()}",
                    expires_at=await _future(conn),
                )
            assert r1.ok
            async with conn.transaction():
                r2 = await s.request_replay(
                    conn,
                    actor=_op("dan"),
                    actor_scope=_scope(),
                    outbox_event_id=e2,
                    idempotency_key=f"a2:{uuid.uuid4()}",
                    expires_at=await _future(conn),
                )
            assert r2.ok  # a DIFFERENT actor's cap is independent of alice's
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_l1_same_actor_different_scope_isolated_limits(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
            monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "1")
            s = _replay_svc()
            _t1, e1 = await _seed_dead_event(conn, project_id=PROJECT_A)
            _t2, e2 = await _seed_dead_event(conn, project_id=PROJECT_B)
            async with conn.transaction():
                r1 = await s.request_replay(
                    conn,
                    actor=_op("alice"),
                    actor_scope=_scope(TEAM_A, PROJECT_A),
                    outbox_event_id=e1,
                    idempotency_key=f"s1:{uuid.uuid4()}",
                    expires_at=await _future(conn),
                )
            assert r1.ok
            async with conn.transaction():
                # SAME actor "alice", a DIFFERENT (team, project) scope -> independent cap
                r2 = await s.request_replay(
                    conn,
                    actor=_op("alice"),
                    actor_scope=_scope(TEAM_B, PROJECT_B),
                    outbox_event_id=e2,
                    idempotency_key=f"s2:{uuid.uuid4()}",
                    expires_at=await _future(conn),
                )
            assert r2.ok
            # but a THIRD request in the SAME (team_A, project_A) scope is capped
            _t3, e3 = await _seed_dead_event(conn, project_id=PROJECT_A)
            async with conn.transaction():
                r3 = await s.request_replay(
                    conn,
                    actor=_op("alice"),
                    actor_scope=_scope(TEAM_A, PROJECT_A),
                    outbox_event_id=e3,
                    idempotency_key=f"s3:{uuid.uuid4()}",
                    expires_at=await _future(conn),
                )
            assert not r3.ok and r3.reason_code == "rate_limited"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_l1_platform_admin_cannot_bypass_hard_cap(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
            monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "1")
            s = _replay_svc()
            _t1, e1 = await _seed_dead_event(conn)
            _t2, e2 = await _seed_dead_event(conn)
            async with conn.transaction():
                r1 = await s.request_replay(
                    conn,
                    actor=_op("root", "platform_admin"),
                    actor_scope=_scope(),
                    outbox_event_id=e1,
                    idempotency_key=f"pa1:{uuid.uuid4()}",
                    expires_at=await _future(conn),
                )
            assert r1.ok
            async with conn.transaction():
                r2 = await s.request_replay(
                    conn,
                    actor=_op("root", "platform_admin"),
                    actor_scope=_scope(),
                    outbox_event_id=e2,
                    idempotency_key=f"pa2:{uuid.uuid4()}",
                    expires_at=await _future(conn),
                )
            assert not r2.ok and r2.reason_code == "rate_limited"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_l1_rolling_window_excludes_old_requests(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
            monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "1")
            s = _replay_svc()
            repo = _replay_repo()
            _t1, e1 = await _seed_dead_event(conn)
            async with conn.transaction():
                r1 = await s.request_replay(
                    conn,
                    actor=_op("alice"),
                    actor_scope=_scope(),
                    outbox_event_id=e1,
                    idempotency_key=f"w1:{uuid.uuid4()}",
                    expires_at=await _future(conn),
                )
            assert r1.ok
            # a second request right away is capped
            _t2, e2 = await _seed_dead_event(conn)
            async with conn.transaction():
                r2 = await s.request_replay(
                    conn,
                    actor=_op("alice"),
                    actor_scope=_scope(),
                    outbox_event_id=e2,
                    idempotency_key=f"w2:{uuid.uuid4()}",
                    expires_at=await _future(conn),
                )
            assert not r2.ok and r2.reason_code == "rate_limited"
            # age the first request out of the rolling window
            await conn.execute(
                "UPDATE replay_requests SET requested_at=statement_timestamp() - interval '25 hours' "
                "WHERE requested_by='alice'"
            )
            async with conn.transaction():
                r3 = await s.request_replay(
                    conn,
                    actor=_op("alice"),
                    actor_scope=_scope(),
                    outbox_event_id=e2,
                    idempotency_key=f"w3:{uuid.uuid4()}",
                    expires_at=await _future(conn),
                )
            assert r3.ok  # the aged-out request no longer counts against the cap

            # sanity: the underlying scoped count function itself respects the window
            count_now = await repo.count_recent_requests_by_actor(
                conn, "alice", team_id=TEAM_A, project_id=PROJECT_A, window_hours=24
            )
            assert count_now == 1  # only the fresh (r3) request is inside the 24h window
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_l1_invalid_actor_cap_config_fails_closed(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
            monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "0")
            s = _replay_svc()
            _t, e = await _seed_dead_event(conn)
            with pytest.raises(ValueError):
                async with conn.transaction():
                    await s.request_replay(
                        conn,
                        actor=_op("alice"),
                        actor_scope=_scope(),
                        outbox_event_id=e,
                        idempotency_key=f"bad-cfg:{uuid.uuid4()}",
                        expires_at=await _future(conn),
                    )
        finally:
            await conn.close()

    _run(scenario())
