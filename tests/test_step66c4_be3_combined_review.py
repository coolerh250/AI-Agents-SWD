"""Step 66C.4-BE3-R -- INDEPENDENT combined security/authorization/transaction review tests.

Written by the independent reviewer to RE-DERIVE (not re-run) the mandatory BE3 A+B+C safety
claims from scratch: durable single-use authorization + CAS concurrency, exact null-safe scope
isolation, consume/replay/audit rollback completeness, two-person replay control at BOTH layers,
policy-authority unforgeability, command-vs-audit destination routing, dead-episode composite
version collision behaviour, destination-readiness fail-closed, rate-limit hard-cap structure,
production-approval reference handling, and feature-gate no-side-effect.

Real PostgreSQL 16 (fail-closed destructive-PG guard) + real Redis 7 for the relay routing test.
Nothing here calls a real orchestrator, executes a real resume, or publishes a business event to a
shared runtime; the only Redis publish is the audit relay against an isolated ephemeral broker.
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
_REDIS_URL = os.environ.get("BE3_REVIEW_REDIS_URL")


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
requires_redis = pytest.mark.skipif(
    not _REDIS_URL, reason="isolated ephemeral Redis 7 not configured (BE3_REVIEW_REDIS_URL)"
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


def _replay_repo():
    from shared.sdk.tasks import replay_request_repository

    return replay_request_repository


def _replay_svc():
    from shared.sdk.tasks import replay_service

    return replay_service


def _replay_model():
    from shared.sdk.tasks import replay_request_model

    return replay_request_model


def _outbox():
    from shared.sdk.tasks import lifecycle_outbox

    return lifecycle_outbox


# ---- schema / seed helpers ----------------------------------------------------------------------


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


async def _connect():
    return await asyncpg.connect(dsn=_DSN)


async def _future(conn, hours: int = 1) -> datetime:
    return await conn.fetchval(
        "SELECT statement_timestamp() + ($1 || ' hours')::interval", str(hours)
    )


async def _make_authorized_auth(
    conn,
    *,
    action="resume",
    resource_id=None,
    state_version="v1",
    team=TEAM_A,
    project=PROJECT_A,
    production=False,
    prod_ref=None,
    requested_by="alice",
    decided_by="bob",
    hours=1,
):
    """Create a pending authorization then CAS it to authorized via the raw repository."""
    r = _authz_repo()
    resource_id = resource_id or str(uuid.uuid4())
    row = await r.create_request(
        conn,
        action_type=action,
        resource_type="clarification" if action == "resume" else "outbox_event",
        resource_id=resource_id,
        requested_by=requested_by,
        requested_role="agent_operator",
        resource_state_version=state_version,
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
        decided_by=decided_by,
        decided_role="reviewer_approver",
        reason_code="policy_allow",
        policy_result="allow",
        policy_version="v1",
        scope_team_id=team,
        scope_project_id=project,
    )
    assert approved is not None
    return approved


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


def _op(principal="alice", role="agent_operator"):
    return _policy().Actor(principal, role)


def _approver(principal="bob", role="reviewer_approver"):
    return _policy().Actor(principal, role)


def _svc_identity(principal="svc"):
    return _policy().Actor(principal, "agent_operator", is_service_identity=True)


def _scope(team=TEAM_A, project=PROJECT_A):
    return _policy().Scope(team, project)


# =================================================================================================
# A. Authorization -- single-use CAS, concurrency, expiry/revoke/stale, rollback
# =================================================================================================


@requires_pg
async def test_concurrent_consume_yields_exactly_one_db_transition() -> None:
    setup = await _connect()
    try:
        await _reset_and_migrate(setup)
        auth = await _make_authorized_auth(setup)
        auth_id = str(auth["authorization_id"])
    finally:
        await setup.close()

    async def _try_consume():
        c = await _connect()
        try:
            async with c.transaction():
                return await _authz_repo().consume(
                    c,
                    auth_id,
                    consumed_by="svc",
                    resource_state_version="v1",
                    scope_team_id=TEAM_A,
                    scope_project_id=PROJECT_A,
                )
        finally:
            await c.close()

    results = await asyncio.gather(*[_try_consume() for _ in range(8)])
    winners = [r for r in results if r is not None]
    assert len(winners) == 1, f"expected exactly one consume winner, got {len(winners)}"

    verify = await _connect()
    try:
        row = await verify.fetchrow(
            "SELECT consumed_at, consumed_by FROM resume_replay_authorizations WHERE authorization_id=$1",
            uuid.UUID(auth_id),
        )
        assert row["consumed_at"] is not None
        assert row["consumed_by"] == "svc"
    finally:
        await verify.close()


@requires_pg
async def test_null_and_cross_scope_direct_repo_calls_isolate() -> None:
    conn = await _connect()
    try:
        await _reset_and_migrate(conn)
        auth = await _make_authorized_auth(conn, team=TEAM_A, project=PROJECT_A)
        auth_id = str(auth["authorization_id"])

        r = _authz_repo()
        # correct scope reads it
        assert (
            await r.get_authorization(
                conn, auth_id, scope_team_id=TEAM_A, scope_project_id=PROJECT_A
            )
            is not None
        )
        # NULL caller scope is NOT a wildcard -> reads nothing
        assert (
            await r.get_authorization(conn, auth_id, scope_team_id=None, scope_project_id=None)
            is None
        )
        # cross-team / cross-project reads nothing
        assert (
            await r.get_authorization(
                conn, auth_id, scope_team_id=TEAM_B, scope_project_id=PROJECT_A
            )
            is None
        )
        assert (
            await r.get_authorization(
                conn, auth_id, scope_team_id=TEAM_A, scope_project_id=PROJECT_B
            )
            is None
        )
        # a cross-scope consume affects 0 rows (returns None) and does NOT consume
        async with conn.transaction():
            blocked = await r.consume(
                conn,
                auth_id,
                consumed_by="attacker",
                resource_state_version="v1",
                scope_team_id=TEAM_B,
                scope_project_id=PROJECT_B,
            )
        assert blocked is None
        still = await r.get_authorization(
            conn, auth_id, scope_team_id=TEAM_A, scope_project_id=PROJECT_A
        )
        assert still["consumed_at"] is None
    finally:
        await conn.close()


@requires_pg
async def test_consume_rollback_leaves_authorization_unconsumed() -> None:
    """Consume then force a rollback in the SAME transaction; the CAS must not persist."""
    conn = await _connect()
    try:
        await _reset_and_migrate(conn)
        auth = await _make_authorized_auth(conn)
        auth_id = str(auth["authorization_id"])

        class _Boom(Exception):
            pass

        with pytest.raises(_Boom):
            async with conn.transaction():
                row = await _authz_repo().consume(
                    conn,
                    auth_id,
                    consumed_by="svc",
                    resource_state_version="v1",
                    scope_team_id=TEAM_A,
                    scope_project_id=PROJECT_A,
                )
                assert row is not None  # CAS won inside the tx
                raise _Boom()  # ... but we roll back

        after = await _authz_repo().get_authorization(
            conn, auth_id, scope_team_id=TEAM_A, scope_project_id=PROJECT_A
        )
        assert after["consumed_at"] is None, "rollback must restore the unconsumed state"
        # and it is still consumable afterwards
        async with conn.transaction():
            ok = await _authz_repo().consume(
                conn,
                auth_id,
                consumed_by="svc",
                resource_state_version="v1",
                scope_team_id=TEAM_A,
                scope_project_id=PROJECT_A,
            )
        assert ok is not None
    finally:
        await conn.close()


@requires_pg
async def test_expired_and_revoked_and_stale_never_consume() -> None:
    conn = await _connect()
    try:
        await _reset_and_migrate(conn)
        r = _authz_repo()

        # expired: authorized but expires in the past
        expired = await r.create_request(
            conn,
            action_type="resume",
            resource_type="clarification",
            resource_id=str(uuid.uuid4()),
            requested_by="alice",
            requested_role="agent_operator",
            resource_state_version="v1",
            expires_at=await conn.fetchval("SELECT statement_timestamp() + interval '1 second'"),
            idempotency_key=f"exp:{uuid.uuid4()}",
            team_id=TEAM_A,
            project_id=PROJECT_A,
        )
        await r.approve(
            conn,
            str(expired["authorization_id"]),
            decided_by="bob",
            decided_role="reviewer_approver",
            reason_code="policy_allow",
            policy_result="allow",
            policy_version="v1",
            scope_team_id=TEAM_A,
            scope_project_id=PROJECT_A,
        )
        await conn.execute("SELECT pg_sleep(1.2)")
        async with conn.transaction():
            assert (
                await r.consume(
                    conn,
                    str(expired["authorization_id"]),
                    consumed_by="svc",
                    resource_state_version="v1",
                    scope_team_id=TEAM_A,
                    scope_project_id=PROJECT_A,
                )
                is None
            )

        # revoked: cannot consume
        revoked = await _make_authorized_auth(conn)
        await r.revoke(
            conn,
            str(revoked["authorization_id"]),
            revoked_by="op",
            reason_code="operator_revoked",
            scope_team_id=TEAM_A,
            scope_project_id=PROJECT_A,
        )
        async with conn.transaction():
            assert (
                await r.consume(
                    conn,
                    str(revoked["authorization_id"]),
                    consumed_by="svc",
                    resource_state_version="v1",
                    scope_team_id=TEAM_A,
                    scope_project_id=PROJECT_A,
                )
                is None
            )

        # stale state version: consume with a different version fails
        stale = await _make_authorized_auth(conn, state_version="v1")
        async with conn.transaction():
            assert (
                await r.consume(
                    conn,
                    str(stale["authorization_id"]),
                    consumed_by="svc",
                    resource_state_version="v2-DIFFERENT",
                    scope_team_id=TEAM_A,
                    scope_project_id=PROJECT_A,
                )
                is None
            )
    finally:
        await conn.close()


@requires_pg
async def test_replay_two_person_db_constraint_blocks_self_approval() -> None:
    """The chk_rra_replay_two_person DB constraint must reject a replay authorized by its requester,
    independent of the policy layer."""
    conn = await _connect()
    try:
        await _reset_and_migrate(conn)
        r = _authz_repo()
        row = await r.create_request(
            conn,
            action_type="replay",
            resource_type="outbox_event",
            resource_id=str(uuid.uuid4()),
            requested_by="same-actor",
            requested_role="agent_operator",
            resource_state_version="v1",
            expires_at=await _future(conn),
            idempotency_key=f"rp:{uuid.uuid4()}",
            team_id=TEAM_A,
            project_id=PROJECT_A,
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await r.approve(
                conn,
                str(row["authorization_id"]),
                decided_by="same-actor",  # requester == approver
                decided_role="reviewer_approver",
                reason_code="policy_allow",
                policy_result="allow",
                policy_version="v1",
                scope_team_id=TEAM_A,
                scope_project_id=PROJECT_A,
            )
    finally:
        await conn.close()


# =================================================================================================
# D. Policy-authority capability (DB-less unit) -- constant-time membership + fail-closed + rotation
# =================================================================================================


def test_policy_authority_capability_matching_fail_closed(monkeypatch) -> None:
    import operations_resume_api as api

    monkeypatch.setenv("BE3_RESUME_POLICY_AUTHORITY_CAPABILITY", "current-secret")
    monkeypatch.setenv("BE3_RESUME_POLICY_AUTHORITY_CAPABILITY_PREVIOUS", "previous-secret")
    configured = api._configured_capabilities()
    assert configured == ("current-secret", "previous-secret")
    # current + previous both accepted (rotation)
    assert api._capability_matches("current-secret", configured) is True
    assert api._capability_matches("previous-secret", configured) is True
    # wrong / empty / oversized all fail
    assert api._capability_matches("wrong", configured) is False
    assert api._capability_matches("", configured) is False
    assert api._capability_matches("x" * 1000, configured) is False

    # empty configured -> nothing matches, even an empty presented value
    monkeypatch.delenv("BE3_RESUME_POLICY_AUTHORITY_CAPABILITY", raising=False)
    monkeypatch.delenv("BE3_RESUME_POLICY_AUTHORITY_CAPABILITY_PREVIOUS", raising=False)
    assert api._configured_capabilities() == ()
    assert api._capability_matches("", ()) is False
    assert api._capability_matches("current-secret", ()) is False
    # unset principal -> mechanism off
    monkeypatch.delenv("BE3_RESUME_POLICY_AUTHORITY_PRINCIPAL_ID", raising=False)
    assert api._configured_policy_authority_principal() == ""
    # rotation with an empty PREVIOUS never introduces an empty valid credential
    monkeypatch.setenv("BE3_RESUME_POLICY_AUTHORITY_CAPABILITY", "only-current")
    monkeypatch.setenv("BE3_RESUME_POLICY_AUTHORITY_CAPABILITY_PREVIOUS", "")
    assert api._configured_capabilities() == ("only-current",)
    assert api._capability_matches("", api._configured_capabilities()) is False


def test_policy_authority_uses_constant_time_compare() -> None:
    import inspect

    import operations_resume_api as api

    src = inspect.getsource(api._capability_matches)
    assert "compare_digest" in src, "capability comparison must use hmac.compare_digest"
    # the secret must never be compared with a plain ==/!= operator on the raw value
    assert "==" not in src.replace("!=", ""), "no plain equality on the secret"


# =================================================================================================
# F. Command-vs-audit routing (DB-less structural + real-Redis relay behaviour)
# =================================================================================================


def test_destination_routing_is_total_and_failclosed() -> None:
    lo = _outbox()
    # every allowlisted event type has exactly one destination
    assert set(lo.EVENT_DESTINATIONS) == set(lo.ALLOWED_EVENT_TYPES)
    # the only command destination is the resume execution command
    cmd = [t for t, d in lo.EVENT_DESTINATIONS.items() if d == lo.DESTINATION_ORCHESTRATOR_COMMAND]
    assert cmd == ["resume.execution_requested"]
    # audit relay claimable set never contains a command row
    assert "resume.execution_requested" not in lo.audit_relay_claimable_event_types()
    # unknown event type fails closed
    with pytest.raises(ValueError):
        lo.destination_for_event_type("totally.unknown.event")


@requires_pg
@requires_redis
async def test_audit_relay_never_claims_orchestrator_command_row() -> None:
    from shared.sdk.event_bus.redis_streams import RedisStreamEventBus
    from shared.sdk.tasks.outbox_relay import ClarificationOutboxRelay

    conn = await _connect()
    try:
        await _reset_and_migrate(conn)
        task_id, _ = await _seed_dead_event(conn, status="pending", attempts=0)
        clar_id = await conn.fetchval(
            "SELECT clarification_id FROM clarification_lifecycle_outbox LIMIT 1"
        )
        lo = _outbox()
        # one audit-destination row and one orchestrator-command row, both pending
        async with conn.transaction():
            audit_row = await lo.insert_lifecycle_outbox_event(
                conn,
                clarification_id=str(clar_id),
                task_id=task_id,
                event_type="resume.requested",
                idempotency_key=f"aud:{uuid.uuid4()}",
                payload={"resume_request_id": str(uuid.uuid4())},
            )
            cmd_row = await lo.insert_lifecycle_outbox_event(
                conn,
                clarification_id=str(clar_id),
                task_id=task_id,
                event_type="resume.execution_requested",
                idempotency_key=f"cmd:{uuid.uuid4()}",
                payload={"resume_request_id": str(uuid.uuid4())},
            )
    finally:
        await conn.close()

    bus = RedisStreamEventBus(redis_url=_REDIS_URL)
    relay = ClarificationOutboxRelay(database_url=_DSN, event_bus=bus)
    try:
        counts = await relay.run_once()
    finally:
        await relay.close()

    check = await _connect()
    try:
        audit_status = await check.fetchval(
            "SELECT status FROM clarification_lifecycle_outbox WHERE id=$1",
            uuid.UUID(str(audit_row["id"])),
        )
        cmd_status = await check.fetchval(
            "SELECT status, published_at FROM clarification_lifecycle_outbox WHERE id=$1",
            uuid.UUID(str(cmd_row["id"])),
        )
        cmd_published_at = await check.fetchval(
            "SELECT published_at FROM clarification_lifecycle_outbox WHERE id=$1",
            uuid.UUID(str(cmd_row["id"])),
        )
        # the audit row was published; the command row was NEVER claimed/published
        assert audit_status == "published", audit_status
        assert cmd_status == "pending", cmd_status
        assert cmd_published_at is None
        assert counts["published"] >= 1
    finally:
        await check.close()


# =================================================================================================
# H/I/K. Dead-episode composite version + replay execution rollback + readiness fail-closed
# =================================================================================================


@requires_pg
async def test_dead_episode_version_changes_on_redeath_and_invalidates_stale_replay() -> None:
    """Prove the dead_at:attempts composite (a) is PG-time based, (b) changes when the row leaves
    and re-enters dead (attempts strictly increases), and (c) a request bound to the OLD episode
    fails the CAS with NO mutation."""
    conn = await _connect()
    try:
        await _reset_and_migrate(conn)
        _, event_id = await _seed_dead_event(conn, attempts=5)
        rmodel = _replay_model()
        rrepo = _replay_repo()

        row1 = await conn.fetchrow(
            "SELECT dead_at, attempts FROM clarification_lifecycle_outbox WHERE id=$1",
            uuid.UUID(event_id),
        )
        v_episode1 = rmodel.dead_episode_state_version(
            dead_at=row1["dead_at"], attempts=row1["attempts"]
        )

        # Replay episode 1 (dead -> pending) via the transaction-aware adapter, version-guarded.
        async with conn.transaction():
            replayed = await rrepo.replay_dead_row(
                conn, event_id, expected_resource_state_version=v_episode1
            )
        assert replayed is not None
        assert replayed["dead_at"] is None
        assert replayed["status"] == "pending"
        assert int(replayed["attempts"]) == 5, "manual replay must NOT reset attempts"
        assert replayed["published_at"] is None

        # A stale request still bound to episode 1 must now fail the CAS with NO mutation.
        async with conn.transaction():
            stale = await rrepo.replay_dead_row(
                conn, event_id, expected_resource_state_version=v_episode1
            )
        assert stale is None  # row is no longer 'dead'

        # Re-death: attempts is preserved at 5, so the next failure increments to 6 and goes dead.
        await conn.execute(
            "UPDATE clarification_lifecycle_outbox "
            "SET status='dead', attempts=6, dead_at=statement_timestamp() "
            "WHERE id=$1",
            uuid.UUID(event_id),
        )
        row2 = await conn.fetchrow(
            "SELECT dead_at, attempts FROM clarification_lifecycle_outbox WHERE id=$1",
            uuid.UUID(event_id),
        )
        v_episode2 = rmodel.dead_episode_state_version(
            dead_at=row2["dead_at"], attempts=row2["attempts"]
        )
        assert v_episode1 != v_episode2, "a new dead episode MUST produce a new version"

        # Episode-1 snapshot cannot replay episode 2 (version guard).
        async with conn.transaction():
            wrong = await rrepo.replay_dead_row(
                conn, event_id, expected_resource_state_version=v_episode1
            )
        assert wrong is None
        # A dead row still has dead_at (round-trip through PG time is consistent/canonical).
        assert row2["dead_at"] is not None
        assert row2["dead_at"].tzinfo is not None
    finally:
        await conn.close()


@requires_pg
async def test_destination_not_ready_blocks_execution_without_any_mutation(monkeypatch) -> None:
    monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
    monkeypatch.setenv("BE3_REPLAY_EXECUTION_ENABLED", "true")
    svc = _replay_svc()

    conn = await _connect()
    try:
        await _reset_and_migrate(conn)
        _, event_id = await _seed_dead_event(conn, attempts=5)
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
        async with conn.transaction():
            authd = await svc.authorize_replay(
                conn, rid, actor=_approver(), actor_scope=_scope(), policy_version="v1"
            )
        assert authd.ok, authd.reason_code

        auth_id = await conn.fetchval(
            "SELECT authorization_id FROM replay_requests WHERE replay_request_id=$1",
            uuid.UUID(rid),
        )

        # default readiness provider reports not_configured -> execution blocked, no side effects
        async with conn.transaction():
            blocked = await svc.execute_authorized_replay(
                conn, rid, actor=_svc_identity(), actor_scope=_scope()
            )
        assert not blocked.ok
        assert blocked.reason_code == "destination_unavailable"

        # authorization NOT consumed, dead row NOT mutated, request still 'authorized'
        consumed_at = await conn.fetchval(
            "SELECT consumed_at FROM resume_replay_authorizations WHERE authorization_id=$1",
            auth_id,
        )
        assert consumed_at is None
        ev = await conn.fetchrow(
            "SELECT status, dead_at FROM clarification_lifecycle_outbox WHERE id=$1",
            uuid.UUID(event_id),
        )
        assert ev["status"] == "dead"
        assert ev["dead_at"] is not None
        state = await conn.fetchval(
            "SELECT state FROM replay_requests WHERE replay_request_id=$1", uuid.UUID(rid)
        )
        assert state == "authorized"
    finally:
        await conn.close()


@requires_pg
async def test_replay_execution_rollback_restores_all_state(monkeypatch) -> None:
    """With a READY provider the execute path consumes + requeues; if the caller transaction rolls
    back, the consume, dead-row requeue and request transition must ALL revert together."""
    monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
    monkeypatch.setenv("BE3_REPLAY_EXECUTION_ENABLED", "true")
    svc = _replay_svc()
    model = _replay_model()

    conn = await _connect()
    try:
        await _reset_and_migrate(conn)
        _, event_id = await _seed_dead_event(conn, attempts=5)
        async with conn.transaction():
            req = await svc.request_replay(
                conn,
                actor=_op(),
                actor_scope=_scope(),
                outbox_event_id=event_id,
                idempotency_key=f"k:{uuid.uuid4()}",
                expires_at=await _future(conn),
            )
        rid = str(req.replay_request["replay_request_id"])
        async with conn.transaction():
            await svc.authorize_replay(
                conn, rid, actor=_approver(), actor_scope=_scope(), policy_version="v1"
            )
        auth_id = await conn.fetchval(
            "SELECT authorization_id FROM replay_requests WHERE replay_request_id=$1",
            uuid.UUID(rid),
        )

        class _Boom(Exception):
            pass

        with pytest.raises(_Boom):
            async with conn.transaction():
                res = await svc.execute_authorized_replay(
                    conn,
                    rid,
                    actor=_svc_identity(),
                    actor_scope=_scope(),
                    readiness_provider=lambda _d: model.READINESS_READY,
                )
                assert res.ok, res.reason_code
                # inside the tx the mutation is visible ...
                assert (
                    await conn.fetchval(
                        "SELECT consumed_at FROM resume_replay_authorizations WHERE authorization_id=$1",
                        auth_id,
                    )
                    is not None
                )
                raise _Boom()  # ... but we roll the whole unit of work back

        # after rollback: consume reverted, dead row still dead, request back to authorized
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
        assert (
            await conn.fetchval(
                "SELECT state FROM replay_requests WHERE replay_request_id=$1", uuid.UUID(rid)
            )
            == "authorized"
        )

        # and a fresh committed execute then succeeds exactly once
        async with conn.transaction():
            ok = await svc.execute_authorized_replay(
                conn,
                rid,
                actor=_svc_identity(),
                actor_scope=_scope(),
                readiness_provider=lambda _d: model.READINESS_READY,
            )
        assert ok.ok and ok.state == "executed"
        ev2 = await conn.fetchrow(
            "SELECT status, dead_at, attempts, published_at FROM clarification_lifecycle_outbox WHERE id=$1",
            uuid.UUID(event_id),
        )
        assert ev2["status"] == "pending"
        assert ev2["dead_at"] is None
        assert int(ev2["attempts"]) == 5  # attempts preserved, not reset
        assert ev2["published_at"] is None
    finally:
        await conn.close()


# =================================================================================================
# G/L. Replay one-active-request-per-event hard cap + per-actor soft cap under concurrency
# =================================================================================================


@requires_pg
async def test_one_active_replay_request_per_event_under_concurrency(monkeypatch) -> None:
    monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
    svc = _replay_svc()

    setup = await _connect()
    try:
        await _reset_and_migrate(setup)
        _, event_id = await _seed_dead_event(setup, attempts=5)
    finally:
        await setup.close()

    async def _req():
        c = await _connect()
        try:
            async with c.transaction():
                return await svc.request_replay(
                    c,
                    actor=_op(),
                    actor_scope=_scope(),
                    outbox_event_id=event_id,
                    idempotency_key=f"k:{uuid.uuid4()}",
                    expires_at=await _future(c),
                )
        finally:
            await c.close()

    results = await asyncio.gather(*[_req() for _ in range(6)], return_exceptions=True)
    ok = [r for r in results if not isinstance(r, Exception) and getattr(r, "ok", False)]
    assert len(ok) == 1, f"exactly one active replay request per event, got {len(ok)}"

    verify = await _connect()
    try:
        n = await verify.fetchval(
            "SELECT count(*) FROM replay_requests WHERE outbox_event_id=$1 "
            "AND state IN ('authorization_pending','authorized')",
            uuid.UUID(event_id),
        )
        assert n == 1
    finally:
        await verify.close()


@requires_pg
async def test_per_actor_replay_request_rate_limit_concurrency_characterisation(
    monkeypatch,
) -> None:
    """Characterise the per-actor request cap under concurrent burst. The cap is a COUNT-based
    check with no per-actor lock, so a concurrent burst across DISTINCT events can transiently
    overshoot. Recorded as evidence for finding L-1 (soft cap). The per-EVENT hard cap and the
    one-active-request-per-event invariant remain index-enforced and are covered separately."""
    monkeypatch.setenv("BE3_REPLAY_API_ENABLED", "true")
    monkeypatch.setenv("BE3_REPLAY_MAX_REQUESTS_PER_ACTOR", "2")
    svc = _replay_svc()

    setup = await _connect()
    try:
        await _reset_and_migrate(setup)
        events = []
        for _ in range(6):
            _, eid = await _seed_dead_event(setup, attempts=5)
            events.append(eid)
    finally:
        await setup.close()

    async def _req(eid):
        c = await _connect()
        try:
            async with c.transaction():
                return await svc.request_replay(
                    c,
                    actor=_op("storm"),
                    actor_scope=_scope(),
                    outbox_event_id=eid,
                    idempotency_key=f"k:{uuid.uuid4()}",
                    expires_at=await _future(c),
                )
        finally:
            await c.close()

    results = await asyncio.gather(*[_req(e) for e in events], return_exceptions=True)
    created = [r for r in results if not isinstance(r, Exception) and getattr(r, "ok", False)]

    # Sequential enforcement is exact: after the burst, a fresh sequential request is rate_limited.
    seq = await _connect()
    try:
        _, extra = await _seed_dead_event(seq, attempts=5)
        async with seq.transaction():
            after = await svc.request_replay(
                seq,
                actor=_op("storm"),
                actor_scope=_scope(),
                outbox_event_id=extra,
                idempotency_key=f"k:{uuid.uuid4()}",
                expires_at=await _future(seq),
            )
        assert not after.ok and after.reason_code == "rate_limited"
    finally:
        await seq.close()

    # Record the observed concurrent count (>= cap; may exceed under burst -> soft cap).
    assert len(created) >= 1
    globals()["_OBSERVED_CONCURRENT_ACTOR_REQUESTS"] = len(created)


# =================================================================================================
# M. Production-approval reference -- only checked for non-emptiness (NOT resolved)
# =================================================================================================


@requires_pg
async def test_production_approval_reference_is_only_nonempty_checked() -> None:
    """FINDING M-1 evidence: a production-effect authorization consumes with ANY non-empty
    reference string; the reference is never resolved to a real, non-expired, correct-resource
    production approval. An empty/absent reference is correctly blocked."""
    conn = await _connect()
    try:
        await _reset_and_migrate(conn)
        authz = _authz()

        # production_effect=True with a BOGUS but non-empty reference -> consume SUCCEEDS
        auth = await _make_authorized_auth(
            conn, production=True, prod_ref="totally-bogus-unresolvable-reference-12345"
        )
        async with conn.transaction():
            res = await authz.consume(
                conn,
                str(auth["authorization_id"]),
                actor=_svc_identity(),
                actor_scope=_scope(),
                resource_state_version="v1",
            )
        assert (
            res.ok
        ), "production consume succeeded with an unverified reference -> reference is not resolved"

        # production_effect=True with NO reference -> correctly blocked
        auth2 = await _make_authorized_auth(conn, production=True, prod_ref=None)
        async with conn.transaction():
            res2 = await authz.consume(
                conn,
                str(auth2["authorization_id"]),
                actor=_svc_identity(),
                actor_scope=_scope(),
                resource_state_version="v1",
            )
        assert not res2.ok
        assert res2.reason_code == "production_approval_required"
    finally:
        await conn.close()


# =================================================================================================
# O. Feature gates -- off means zero DB side effect
# =================================================================================================


@requires_pg
async def test_feature_gates_off_produce_zero_side_effects(monkeypatch) -> None:
    monkeypatch.delenv("BE3_REPLAY_API_ENABLED", raising=False)
    monkeypatch.delenv("BE3_REPLAY_EXECUTION_ENABLED", raising=False)
    svc = _replay_svc()
    model = _replay_model()
    assert model.replay_api_enabled() is False
    assert model.replay_execution_enabled() is False

    conn = await _connect()
    try:
        await _reset_and_migrate(conn)
        _, event_id = await _seed_dead_event(conn, attempts=5)
        async with conn.transaction():
            res = await svc.request_replay(
                conn,
                actor=_op(),
                actor_scope=_scope(),
                outbox_event_id=event_id,
                idempotency_key=f"k:{uuid.uuid4()}",
                expires_at=await _future(conn),
            )
        assert not res.ok and res.reason_code == "feature_disabled"
        # no request, no authorization created
        assert await conn.fetchval("SELECT count(*) FROM replay_requests") == 0
        assert await conn.fetchval("SELECT count(*) FROM resume_replay_authorizations") == 0
    finally:
        await conn.close()
