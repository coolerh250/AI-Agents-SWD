"""Step 66C.4-BE3-B-C1 -- policy authority authentication boundary and command outbox destination
routing alignment.

Two independent alignment items on top of BE3-B:

1. Policy authority: resolving is_policy_authority now requires BOTH an authenticated TRUSTED
   PRINCIPAL (a fixed server-configured internal principal id, never an ordinary Operator's own
   actor id) AND the correct server-side capability (current/previous, constant-time compared).
   Both checks always run (no short-circuit); every failure is the identical 403; the capability
   value is never logged/audited/echoed.
2. Command outbox destination routing: every lifecycle_outbox event_type has an explicit, single
   durable destination ('audit' | 'orchestrator_command'). The existing BE2 audit relay's claim
   query is restricted to audit-classified event types, so it can never claim, mis-publish, or
   falsely mark 'published' an orchestrator-command row (resume.execution_requested).

Real-PostgreSQL 16 integration; a stub event bus (never a real Redis dependency) proves the audit
relay never even attempts to publish an orchestrator-command row. Nothing calls the orchestrator,
executes resume, or activates any consumer.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
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
CAPABILITY = "current-capability-value"
PREVIOUS_CAPABILITY = "previous-capability-value"
TRUSTED_PRINCIPAL = "policy-safety-service"


def _outbox():
    from shared.sdk.tasks import lifecycle_outbox

    return lifecycle_outbox


def _relay_mod():
    from shared.sdk.tasks import outbox_relay

    return outbox_relay


def _svc():
    from shared.sdk.tasks import resume_service

    return resume_service


def _policy():
    from shared.sdk.tasks import authorization_policy

    return authorization_policy


def _api_mod():
    sys.path.insert(0, str(_ORCH_SRC))
    try:
        sys.modules.pop("operations_resume_api", None)
        return importlib.import_module("operations_resume_api")
    finally:
        if str(_ORCH_SRC) in sys.path:
            sys.path.remove(str(_ORCH_SRC))


# --------------------------------------------------------------------------------------
# 1. Policy authority: DB-less unit tests (constant-time comparison + resolver semantics)
# --------------------------------------------------------------------------------------


def test_capability_comparison_is_constant_time() -> None:
    src = inspect.getsource(_api_mod())
    assert "hmac.compare_digest" in src
    # No plain equality/inequality check on the capability value itself.
    assert "presented != expected" not in src
    assert "presented == expected" not in src


def test_capability_matches_current_and_previous(monkeypatch) -> None:
    api = _api_mod()
    assert api._capability_matches(CAPABILITY, (CAPABILITY, PREVIOUS_CAPABILITY)) is True
    assert api._capability_matches(PREVIOUS_CAPABILITY, (CAPABILITY, PREVIOUS_CAPABILITY)) is True
    assert api._capability_matches("wrong", (CAPABILITY, PREVIOUS_CAPABILITY)) is False
    # empty / oversized / no configured values -> denied without a match
    assert api._capability_matches("", (CAPABILITY,)) is False
    assert api._capability_matches("x" * 300, (CAPABILITY,)) is False
    assert api._capability_matches(CAPABILITY, ()) is False


def test_unset_server_config_can_never_be_satisfied(monkeypatch) -> None:
    api = _api_mod()
    monkeypatch.delenv("BE3_RESUME_POLICY_AUTHORITY_PRINCIPAL_ID", raising=False)
    monkeypatch.delenv("BE3_RESUME_POLICY_AUTHORITY_CAPABILITY", raising=False)
    monkeypatch.delenv("BE3_RESUME_POLICY_AUTHORITY_CAPABILITY_PREVIOUS", raising=False)
    assert api._configured_policy_authority_principal() == ""
    assert api._configured_capabilities() == ()


def test_policy_authority_role_is_not_a_task_role() -> None:
    from shared.sdk.tasks.rbac import TASK_ROLES

    api = _api_mod()
    assert api._POLICY_AUTHORITY_ROLE not in TASK_ROLES


def test_policy_authority_permission_scope_is_authorize_reject_only() -> None:
    p = _policy()
    sc = p.Scope(TEAM_A, PROJECT_A)
    authority = p.Actor(TRUSTED_PRINCIPAL, "policy_authority", is_policy_authority=True)
    assert p.evaluate(
        action="authorize_resume", actor=authority, actor_scope=sc, resource_scope=sc
    ).allowed
    assert p.evaluate(
        action="reject_resume", actor=authority, actor_scope=sc, resource_scope=sc
    ).allowed
    for forbidden_action in ("request_resume", "cancel_resume", "consume_resume"):
        outcome = p.evaluate(
            action=forbidden_action, actor=authority, actor_scope=sc, resource_scope=sc
        )
        assert not outcome.allowed, forbidden_action
        assert outcome.reason_code == "policy_authority_scope"


# --------------------------------------------------------------------------------------
# 2. Command outbox destination classification: DB-less unit tests
# --------------------------------------------------------------------------------------


def test_every_event_type_has_a_destination_classification() -> None:
    lo = _outbox()
    assert set(lo.EVENT_DESTINATIONS) == lo.ALLOWED_EVENT_TYPES


def test_command_destination_is_orchestrator_command_only() -> None:
    lo = _outbox()
    assert lo.destination_for_event_type("resume.execution_requested") == (
        lo.DESTINATION_ORCHESTRATOR_COMMAND
    )
    assert lo.destination_for_event_type("resume.authorized") == lo.DESTINATION_AUDIT
    with pytest.raises(ValueError):
        lo.destination_for_event_type("not.a.real.event")


def test_audit_relay_claimable_excludes_command_destination() -> None:
    lo = _outbox()
    claimable = lo.audit_relay_claimable_event_types()
    assert "resume.execution_requested" not in claimable
    assert "resume.authorized" in claimable
    assert "clarification.reminder_recorded" in claimable


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


async def _seed(conn) -> tuple[str, str]:
    task_id = await conn.fetchval(
        "INSERT INTO operator_tasks (title, task_type, created_by, status, project_id) "
        "VALUES ('t', 'software_delivery', 'alice', 'clarification_needed', $1) RETURNING id",
        uuid.UUID(PROJECT_A),
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


def _scope():
    return _policy().Scope(TEAM_A, PROJECT_A)


def _op():
    return _policy().Actor("alice", "agent_operator")


def _authority():
    return _policy().Actor(TRUSTED_PRINCIPAL, "policy_authority", is_policy_authority=True)


def _service_identity():
    return _policy().Actor("svc", "agent_operator", is_service_identity=True)


async def _future(conn):
    return await conn.fetchval("SELECT statement_timestamp() + interval '1 hour'")


async def _authorized_request(conn, monkeypatch) -> tuple[str, str]:
    monkeypatch.setenv("BE3_RESUME_API_ENABLED", "true")
    s = _svc()
    clar_task, clar = await _seed(conn)
    async with conn.transaction():
        req = await s.request_resume(
            conn,
            actor=_op(),
            actor_scope=_scope(),
            clarification_id=clar,
            idempotency_key=f"k:{uuid.uuid4()}",
            expires_at=await _future(conn),
        )
    rid = str(req.resume_request["resume_request_id"])
    async with conn.transaction():
        await s.authorize_resume(
            conn, rid, actor=_authority(), actor_scope=_scope(), policy_version="v1"
        )
    return clar, rid


class _RaisingBus:
    """Event bus that raises if used at all -- proves the audit relay never even attempts to
    publish a row it was never supposed to claim. Tracks call count directly (rather than relying
    on exception-swallowing semantics inside the relay's own failure handling)."""

    def __init__(self) -> None:
        self.calls = 0

    async def publish_event(self, stream, event):
        self.calls += 1
        raise AssertionError("the audit relay must never attempt to publish this row")

    async def close(self):
        pass


@pytest.fixture(autouse=True)
def _reset_gates(monkeypatch):
    monkeypatch.delenv("BE3_RESUME_API_ENABLED", raising=False)
    monkeypatch.delenv("BE3_RESUME_COMMAND_ENABLED", raising=False)
    monkeypatch.delenv("BE3_RESUME_POLICY_AUTHORITY_PRINCIPAL_ID", raising=False)
    monkeypatch.delenv("BE3_RESUME_POLICY_AUTHORITY_CAPABILITY", raising=False)
    monkeypatch.delenv("BE3_RESUME_POLICY_AUTHORITY_CAPABILITY_PREVIOUS", raising=False)
    yield


# ---- Audit relay never claims an orchestrator-command row --------------------------


@requires_pg
def test_pg_audit_relay_never_claims_orchestrator_command_row(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            _clar, rid = await _authorized_request(conn, monkeypatch)
            monkeypatch.setenv("BE3_RESUME_COMMAND_ENABLED", "true")
            s = _svc()
            async with conn.transaction():
                prep = await s.prepare_execution(
                    conn, rid, actor=_service_identity(), actor_scope=_scope()
                )
            assert prep.ok
            command_row = await conn.fetchrow(
                "SELECT * FROM clarification_lifecycle_outbox "
                "WHERE event_type='resume.execution_requested'"
            )
            assert command_row is not None and command_row["status"] == "pending"

            # Isolate the invariant under test: mark every OTHER (audit) row published, as a real
            # audit relay cycle would eventually do, so the command row is the ONLY pending row.
            await conn.execute(
                "UPDATE clarification_lifecycle_outbox "
                "SET status='published', published_at=statement_timestamp() "
                "WHERE event_type<>'resume.execution_requested' AND status='pending'"
            )

            bus = _RaisingBus()
            relay = _relay_mod().ClarificationOutboxRelay(_DSN, event_bus=bus)
            outcome = await relay.publish_one(conn)
            # nothing eligible for THIS relay to claim (the only pending row is a command row)
            assert outcome is None
            assert bus.calls == 0  # the bus was never even touched

            still = await conn.fetchrow(
                "SELECT status FROM clarification_lifecycle_outbox WHERE id=$1",
                command_row["id"],
            )
            assert still["status"] == "pending"  # untouched: not claimed, not published
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_unknown_event_type_row_never_claimed_fail_closed(monkeypatch) -> None:
    """Defense in depth: even a row inserted OUT OF BAND (bypassing the safe insert helper, which
    itself rejects an unknown event_type) with an unclassified event_type is never claimed -- the
    relay's claim set is a fail-closed allowlist, not a denylist that must be kept in sync."""

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            _task_id, clar = await _seed(conn)
            row = await conn.fetchrow(
                "INSERT INTO clarification_lifecycle_outbox "
                "(clarification_id, task_id, event_type, idempotency_key, payload) "
                "SELECT id, task_id, 'not.a.real.event', 'unknown-1', '{}'::jsonb "
                "FROM operator_clarification_requests WHERE id=$1 RETURNING id",
                uuid.UUID(clar),
            )
            relay = _relay_mod().ClarificationOutboxRelay(_DSN, event_bus=_RaisingBus())
            outcome = await relay.publish_one(conn)
            assert outcome is None
            still = await conn.fetchrow(
                "SELECT status FROM clarification_lifecycle_outbox WHERE id=$1", row["id"]
            )
            assert still["status"] == "pending"
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_command_gate_off_creates_no_command_row(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            _clar, rid = await _authorized_request(conn, monkeypatch)
            s = _svc()
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
        finally:
            await conn.close()

    _run(scenario())


@requires_pg
def test_pg_no_active_consumer_command_backlog_visible_and_untouched(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            _clar, rid = await _authorized_request(conn, monkeypatch)
            monkeypatch.setenv("BE3_RESUME_COMMAND_ENABLED", "true")
            s = _svc()
            async with conn.transaction():
                await s.prepare_execution(
                    conn, rid, actor=_service_identity(), actor_scope=_scope()
                )

            lo = _outbox()
            before = await lo.count_pending_by_destination(
                conn, lo.DESTINATION_ORCHESTRATOR_COMMAND
            )
            assert before == 1

            # Run the (only existing) relay repeatedly -- it must never touch the command backlog.
            relay = _relay_mod().ClarificationOutboxRelay(_DSN, event_bus=_RaisingBus())
            for _ in range(3):
                await relay.run_once(conn)

            after = await lo.count_pending_by_destination(conn, lo.DESTINATION_ORCHESTRATOR_COMMAND)
            assert (
                after == 1
            )  # unchanged: no consumer exists, so it stays pending (blocks activation)
        finally:
            await conn.close()

    _run(scenario())


# ---- Retry / ack-loss keep a single command identity --------------------------------


@requires_pg
def test_pg_concurrent_prepare_yields_exactly_one_command_identity(monkeypatch) -> None:
    async def scenario() -> None:
        setup = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(setup)
            _clar, rid = await _authorized_request(setup, monkeypatch)
        finally:
            await setup.close()
        monkeypatch.setenv("BE3_RESUME_COMMAND_ENABLED", "true")
        s = _svc()

        async def one():
            c = await asyncpg.connect(dsn=_DSN)
            try:
                async with c.transaction():
                    res = await s.prepare_execution(
                        c, rid, actor=_service_identity(), actor_scope=_scope()
                    )
                    return res.command_id if res.ok else None
            finally:
                await c.close()

        results = await asyncio.gather(one(), one(), one(), return_exceptions=True)
        winners = [r for r in results if isinstance(r, str)]
        assert len(winners) == 1  # exactly one CAS wins -> exactly one command identity

        verify = await asyncpg.connect(dsn=_DSN)
        try:
            n = await verify.fetchval(
                "SELECT count(*) FROM clarification_lifecycle_outbox "
                "WHERE event_type='resume.execution_requested'"
            )
            assert n == 1  # never a second command row/identity for the same request
        finally:
            await verify.close()

    _run(scenario())


@requires_pg
def test_pg_retried_prepare_after_success_reuses_no_new_identity(monkeypatch) -> None:
    """Simulates a caller retry after an ack-loss: prepare_execution is called again once the
    request is already execution_pending. No second command row/identity is ever created."""

    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            _clar, rid = await _authorized_request(conn, monkeypatch)
            monkeypatch.setenv("BE3_RESUME_COMMAND_ENABLED", "true")
            s = _svc()
            async with conn.transaction():
                first = await s.prepare_execution(
                    conn, rid, actor=_service_identity(), actor_scope=_scope()
                )
            assert first.ok
            first_command_id = first.command_id

            retry = await s.prepare_execution(
                conn, rid, actor=_service_identity(), actor_scope=_scope()
            )
            assert not retry.ok  # already execution_pending -> no second consume/command

            row = await conn.fetchrow(
                "SELECT command_id FROM resume_requests WHERE resume_request_id=$1", uuid.UUID(rid)
            )
            assert str(row["command_id"]) == first_command_id  # identity unchanged
            n = await conn.fetchval(
                "SELECT count(*) FROM clarification_lifecycle_outbox "
                "WHERE event_type='resume.execution_requested'"
            )
            assert n == 1
        finally:
            await conn.close()

    _run(scenario())


# ---- Audit evidence and command evidence never overwrite each other ----------------


@requires_pg
def test_pg_audit_and_command_evidence_are_distinct_rows(monkeypatch) -> None:
    async def scenario() -> None:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            _clar, rid = await _authorized_request(conn, monkeypatch)
            monkeypatch.setenv("BE3_RESUME_COMMAND_ENABLED", "true")
            s = _svc()
            async with conn.transaction():
                await s.prepare_execution(
                    conn, rid, actor=_service_identity(), actor_scope=_scope()
                )

            rows = await conn.fetch(
                "SELECT id, event_type, idempotency_key FROM clarification_lifecycle_outbox "
                "ORDER BY created_at"
            )
            by_type = {r["event_type"]: r for r in rows}
            assert "resume.requested" in by_type
            assert "resume.authorized" in by_type
            assert "resume.execution_requested" in by_type
            ids = {str(r["id"]) for r in rows}
            keys = {r["idempotency_key"] for r in rows}
            assert len(ids) == len(rows)  # every row has its own id
            assert len(keys) == len(rows)  # every row has its own idempotency_key
        finally:
            await conn.close()

    _run(scenario())


# --------------------------------------------------------------------------------------
# Policy authority: API-layer integration (feature gate ordering + spoof prevention)
# --------------------------------------------------------------------------------------


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
def test_api_feature_gate_off_never_compares_capability(monkeypatch) -> None:
    async def prep() -> str:
        conn = await asyncpg.connect(dsn=_DSN)
        try:
            await _reset_and_migrate(conn)
            _, clar = await _seed(conn)
            return clar
        finally:
            await conn.close()

    _run(prep())
    monkeypatch.setenv("DATABASE_URL", _DSN)
    monkeypatch.setenv("TASK_API_TEST_AUTH_ENABLED", "true")
    _task_api, api = _load_api()
    _task_api._store_singleton = None

    def _boom(*a, **k):
        raise AssertionError("capability comparison must not run while the API gate is off")

    monkeypatch.setattr(api, "_capability_matches", _boom)
    monkeypatch.delenv("BE3_RESUME_API_ENABLED", raising=False)
    c = _client(api)
    r = c.post(
        f"/operations/resume-requests/{uuid.uuid4()}/authorize",
        json={"team_id": TEAM_A, "project_id": PROJECT_A, "policy_version": "v1"},
        headers={
            "X-Task-Actor": TRUSTED_PRINCIPAL,
            "X-Task-Role": "platform_admin",
            "X-Resume-Policy-Authority": CAPABILITY,
        },
    )
    assert r.status_code == 503
    _task_api._store_singleton = None


@requires_pg
def test_api_unauthenticated_caller_denied_before_capability_check(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", _DSN)
    monkeypatch.setenv("TASK_API_TEST_AUTH_ENABLED", "true")
    monkeypatch.setenv("BE3_RESUME_API_ENABLED", "true")
    monkeypatch.setenv("BE3_RESUME_POLICY_AUTHORITY_PRINCIPAL_ID", TRUSTED_PRINCIPAL)
    monkeypatch.setenv("BE3_RESUME_POLICY_AUTHORITY_CAPABILITY", CAPABILITY)
    _task_api, api = _load_api()
    _task_api._store_singleton = None
    c = _client(api)
    # no X-Task-Actor / X-Task-Role at all, but the correct-looking capability header is present
    r = c.post(
        f"/operations/resume-requests/{uuid.uuid4()}/authorize",
        json={"team_id": TEAM_A, "project_id": PROJECT_A, "policy_version": "v1"},
        headers={"X-Resume-Policy-Authority": CAPABILITY},
    )
    assert r.status_code in (401, 403)
    _task_api._store_singleton = None


@requires_pg
def test_api_capability_never_leaks_into_response_or_audit(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", _DSN)
    monkeypatch.setenv("TASK_API_TEST_AUTH_ENABLED", "true")
    monkeypatch.setenv("BE3_RESUME_API_ENABLED", "true")
    monkeypatch.setenv("BE3_RESUME_POLICY_AUTHORITY_PRINCIPAL_ID", TRUSTED_PRINCIPAL)
    monkeypatch.setenv("BE3_RESUME_POLICY_AUTHORITY_CAPABILITY", CAPABILITY)
    _task_api, api = _load_api()
    _task_api._store_singleton = None
    c = _client(api)
    wrong = "definitely-the-wrong-capability-value"
    r = c.post(
        f"/operations/resume-requests/{uuid.uuid4()}/authorize",
        json={"team_id": TEAM_A, "project_id": PROJECT_A, "policy_version": "v1"},
        headers={
            "X-Task-Actor": TRUSTED_PRINCIPAL,
            "X-Task-Role": "platform_admin",
            "X-Resume-Policy-Authority": wrong,
        },
    )
    assert r.status_code == 403
    assert wrong not in r.text
    assert CAPABILITY not in r.text
    _task_api._store_singleton = None
