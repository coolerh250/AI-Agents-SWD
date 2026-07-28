"""Step 66C.4-BE3-C -- internal authorized dead-event replay service.

Ties replay eligibility (authoritative DB state under row locks) + the BE3-A durable authorization
(authorization_service/policy, reused UNCHANGED with action_type='replay') + rate-limit policy +
destination readiness + the replay_requests repository + the transaction-aware internal replay_dead
adapter + the durable audit outbox into one transaction per state change.

FOUNDATION only: it NEVER calls a real replay_dead in any shared runtime path, NEVER publishes an
event, and exposes NO HTTP execute endpoint. Execution is Service-Identity-only and internal
(execute_authorized_replay). Every function takes the caller's asyncpg connection and runs inside
the caller's transaction, so a state change and its evidence commit atomically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

import asyncpg

from shared.sdk.tasks import authorization_service as authz
from shared.sdk.tasks import lifecycle_outbox
from shared.sdk.tasks import replay_request_model as model
from shared.sdk.tasks import replay_request_repository as repo
from shared.sdk.tasks.authorization_policy import Actor, Scope, evaluate


@dataclass(frozen=True)
class ReplayResult:
    ok: bool
    result_kind: str
    reason_code: str
    replay_request: dict[str, Any] | None = None

    @property
    def state(self) -> str | None:
        return model.project_state(self.replay_request) if self.replay_request else None


def _deny(result_kind: str, reason_code: str) -> ReplayResult:
    return ReplayResult(False, result_kind, reason_code)


async def _emit(
    conn: asyncpg.Connection,
    *,
    clarification_id: str,
    task_id: str,
    event_type: str,
    idempotency_key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return await lifecycle_outbox.insert_lifecycle_outbox_event(
        conn,
        clarification_id=clarification_id,
        task_id=task_id,
        event_type=event_type,
        idempotency_key=idempotency_key,
        payload=payload,
    )


def _dead_eligibility_denial(
    event_row: dict[str, Any],
) -> ReplayResult | None:
    """§8 eligibility (destination/event_type/dead-state only; scope and rate-limit are checked by
    the caller, which needs DB access this pure helper does not have)."""
    status = event_row.get("status")
    if status == "published":
        return _deny("not_eligible", "already_published")
    if status != "dead":
        return _deny("not_eligible", "not_dead")
    event_type = event_row.get("event_type")
    if event_type not in lifecycle_outbox.ALLOWED_EVENT_TYPES:
        return _deny("not_eligible", "unknown_event_type")
    try:
        lifecycle_outbox.destination_for_event_type(event_type)
    except ValueError:
        return _deny("not_eligible", "unknown_destination")
    return None


async def request_replay(
    conn: asyncpg.Connection,
    *,
    actor: Actor,
    actor_scope: Scope,
    outbox_event_id: str,
    idempotency_key: str,
    expires_at: datetime,
    production_approval_reference: str | None = None,
) -> ReplayResult:
    """Operator creates a replay request + pending (two-person) authorization (one transaction)."""
    if not model.replay_api_enabled():
        return _deny("feature_disabled", "feature_disabled")

    # Idempotent re-confirm: the same request idempotency_key returns the same request (scoped).
    existing = await repo.get_replay_request_by_idempotency_key(conn, idempotency_key)
    if existing is not None:
        if str(existing["team_id"]) != (actor_scope.team_id or "") or str(
            existing["project_id"]
        ) != (actor_scope.project_id or ""):
            return _deny("not_found_masked", "resource_not_found")
        return ReplayResult(True, "ok", "operator_requested", existing)

    # Pure RBAC pre-check BEFORE any mutation, so a denied caller never touches the dead row.
    pre = evaluate(
        action="request_replay", actor=actor, actor_scope=actor_scope, resource_scope=actor_scope
    )
    if not pre.allowed:
        return _deny(pre.result_kind, pre.reason_code)

    # Step 66C.4-BE3-R1 (finding L-1 closure): serialize this actor's rate-limit check-then-insert
    # within (team, project, actor) BEFORE any row lock below, so every call path acquires locks in
    # the same order (advisory lock first, dead-row lock second) and cannot deadlock against itself.
    await repo.acquire_actor_rate_limit_lock(
        conn,
        team_id=actor_scope.team_id or "",
        project_id=actor_scope.project_id or "",
        actor_id=actor.principal_id,
    )

    event_row = await repo.lock_outbox_event(conn, outbox_event_id)
    if event_row is None:
        return _deny("not_found_masked", "resource_not_found")

    scope_row = await repo.resolve_event_scope(conn, outbox_event_id)
    if scope_row is None:
        # Unresolvable server-side scope/production-effect signal -- fail closed.
        return _deny("not_found_masked", "resource_not_found")
    if scope_row.get("project_id") is not None and str(scope_row["project_id"]) != (
        actor_scope.project_id or ""
    ):
        return _deny("not_found_masked", "resource_not_found")

    denial = _dead_eligibility_denial(event_row)
    if denial is not None:
        return denial

    # Rate limiting (§16): bounded requests per actor per window + bounded successful replays per
    # event per window. "One active request per event" is enforced by the DB partial unique index.
    window_hours = model.rate_limit_window_hours()
    actor_count = await repo.count_recent_requests_by_actor(
        conn,
        actor.principal_id,
        team_id=actor_scope.team_id or "",
        project_id=actor_scope.project_id or "",
        window_hours=window_hours,
    )
    if actor_count >= model.max_requests_per_actor_per_window():
        return _deny("rate_limited", "rate_limited")
    success_count = await repo.count_successful_replays_for_event(
        conn, outbox_event_id, window_hours=window_hours
    )
    if success_count >= model.max_successful_replays_per_event():
        return _deny("rate_limited", "rate_limited")

    state_version = model.dead_episode_state_version(
        dead_at=event_row["dead_at"], attempts=event_row["attempts"]
    )
    destination = lifecycle_outbox.destination_for_event_type(event_row["event_type"])
    # Server-side authoritative production-effect derivation (§17): from the owning task's OWN
    # production_effect column, NEVER from request input. Unresolvable -> fail closed (treated as
    # production-effect, so consume later requires an approval reference).
    production_effect = bool(scope_row.get("production_effect", True))

    # Create the durable (two-person) authorization + insert the replay request inside a SAVEPOINT:
    # a concurrent loser's UniqueViolationError (on the authorization's own active-request index)
    # only rolls back to this savepoint, never poisoning the caller's outer transaction, so the
    # denial below is always reachable cleanly (Step 66C.4-BE3-C composability fix).
    holder: dict[str, Any] = {}
    try:
        async with conn.transaction():
            auth = await authz.request_authorization(
                conn,
                actor=actor,
                actor_scope=actor_scope,
                resource_scope=actor_scope,
                action_type="replay",
                resource_type="outbox_event",
                resource_id=outbox_event_id,
                resource_state_version=state_version,
                expires_at=expires_at,
                idempotency_key=f"replay-auth:{outbox_event_id}:{idempotency_key}",
                production_effect=production_effect,
                production_approval_reference=production_approval_reference,
            )
            holder["auth"] = auth
            if auth.ok and auth.authorization is not None:
                holder["rr"] = await repo.insert_replay_request(
                    conn,
                    authorization_id=str(auth.authorization["authorization_id"]),
                    outbox_event_id=outbox_event_id,
                    event_type=event_row["event_type"],
                    destination=destination,
                    team_id=actor_scope.team_id or "",
                    project_id=actor_scope.project_id or "",
                    resource_state_version=state_version,
                    requested_by=actor.principal_id,
                    idempotency_key=idempotency_key,
                )
    except asyncpg.UniqueViolationError:
        return _deny("conflict", "active_request_exists")

    auth = holder["auth"]
    if not auth.ok or auth.authorization is None:
        if auth.result_kind == "conflict":
            return _deny("conflict", "active_request_exists")
        return _deny(auth.result_kind, auth.reason_code)
    rr = holder["rr"]

    await _emit(
        conn,
        clarification_id=str(event_row["clarification_id"]),
        task_id=str(event_row["task_id"]),
        event_type="replay.requested",
        idempotency_key=f"replay-requested:{outbox_event_id}:{rr['replay_request_id']}",
        payload={
            "replay_request_id": str(rr["replay_request_id"]),
            "outbox_event_id": outbox_event_id,
            "destination": destination,
            "reason": "operator_requested",
        },
    )
    return ReplayResult(True, "ok", "operator_requested", rr)


async def _load_visible(
    conn: asyncpg.Connection,
    replay_request_id: str,
    actor_scope: Scope,
    *,
    lock: bool = True,
) -> tuple[dict[str, Any] | None, ReplayResult | None]:
    fn = repo.lock_replay_request if lock else repo.get_replay_request
    rr = await fn(
        conn,
        replay_request_id,
        scope_team_id=actor_scope.team_id,
        scope_project_id=actor_scope.project_id,
    )
    if rr is None:
        return None, _deny("not_found_masked", "resource_not_found")
    return rr, None


async def get_replay_request(
    conn: asyncpg.Connection, replay_request_id: str, *, actor_scope: Scope
) -> ReplayResult:
    rr, masked = await _load_visible(conn, replay_request_id, actor_scope, lock=False)
    if masked is not None:
        return masked
    assert rr is not None
    return ReplayResult(True, "ok", "ok", rr)


async def authorize_replay(
    conn: asyncpg.Connection,
    replay_request_id: str,
    *,
    actor: Actor,
    actor_scope: Scope,
    policy_version: str,
) -> ReplayResult:
    """Approver authorizes a pending replay request (one transaction). Two-person control
    (requester != approver) is enforced by BOTH the authorization_policy check and the DB
    chk_rra_replay_two_person constraint (reused unchanged from BE3-A)."""
    if not model.replay_api_enabled():
        return _deny("feature_disabled", "feature_disabled")
    rr, masked = await _load_visible(conn, replay_request_id, actor_scope)
    if masked is not None:
        return masked
    assert rr is not None
    if rr["state"] != "authorization_pending":
        return _deny("invalid_transition", f"already_{rr['state']}"[:64])

    event_row = await repo.lock_outbox_event(conn, str(rr["outbox_event_id"]))
    if event_row is None:
        return _deny("not_found_masked", "resource_not_found")
    denial = _dead_eligibility_denial(event_row)
    if denial is not None:
        return denial
    current_version = model.dead_episode_state_version(
        dead_at=event_row["dead_at"], attempts=event_row["attempts"]
    )
    if current_version != rr["resource_state_version"]:
        return _deny("stale_state", "stale_state")

    outcome = await authz.authorize(
        conn,
        str(rr["authorization_id"]),
        actor=actor,
        actor_scope=actor_scope,
        policy_version=policy_version,
    )
    if not outcome.ok:
        if outcome.reason_code == "two_person_required":
            return _deny(outcome.result_kind, "requester_cannot_approve")
        return _deny(outcome.result_kind, outcome.reason_code)

    updated = await repo.transition_to_authorized(
        conn,
        replay_request_id,
        scope_team_id=actor_scope.team_id,
        scope_project_id=actor_scope.project_id,
    )
    if updated is None:
        return _deny("conflict", "conflict")
    await _emit(
        conn,
        clarification_id=str(event_row["clarification_id"]),
        task_id=str(event_row["task_id"]),
        event_type="replay.authorized",
        idempotency_key=f"replay-authorized:{rr['outbox_event_id']}:{replay_request_id}",
        payload={
            "replay_request_id": replay_request_id,
            "authorization_id": str(rr["authorization_id"]),
            "reason": "policy_allow",
        },
    )
    return ReplayResult(True, "ok", "policy_allow", updated)


async def reject_replay(
    conn: asyncpg.Connection,
    replay_request_id: str,
    *,
    actor: Actor,
    actor_scope: Scope,
    reason_code: str = "policy_deny",
) -> ReplayResult:
    """Approver rejects a pending replay request (one transaction)."""
    if not model.replay_api_enabled():
        return _deny("feature_disabled", "feature_disabled")
    model.assert_reason_code(reason_code)
    rr, masked = await _load_visible(conn, replay_request_id, actor_scope)
    if masked is not None:
        return masked
    assert rr is not None
    if rr["state"] != "authorization_pending":
        return _deny("invalid_transition", f"already_{rr['state']}"[:64])

    outcome = await authz.reject(
        conn, str(rr["authorization_id"]), actor=actor, actor_scope=actor_scope
    )
    if not outcome.ok:
        return _deny(outcome.result_kind, outcome.reason_code)

    updated = await repo.transition_to_rejected(
        conn,
        replay_request_id,
        reason_code=reason_code,
        scope_team_id=actor_scope.team_id,
        scope_project_id=actor_scope.project_id,
    )
    if updated is None:
        return _deny("conflict", "conflict")
    await _emit(
        conn,
        clarification_id=str(await _clarification_id_for(conn, rr)),
        task_id=str(await _task_id_for(conn, rr)),
        event_type="replay.rejected",
        idempotency_key=f"replay-rejected:{rr['outbox_event_id']}:{replay_request_id}",
        payload={"replay_request_id": replay_request_id, "reason": reason_code},
    )
    return ReplayResult(True, "ok", reason_code, updated)


async def cancel_replay(
    conn: asyncpg.Connection,
    replay_request_id: str,
    *,
    actor: Actor,
    actor_scope: Scope,
) -> ReplayResult:
    """Operator cancels their own pending request; platform_admin may cancel any (one transaction)."""
    if not model.replay_api_enabled():
        return _deny("feature_disabled", "feature_disabled")
    rr, masked = await _load_visible(conn, replay_request_id, actor_scope)
    if masked is not None:
        return masked
    assert rr is not None
    if actor.role != "platform_admin" and rr["requested_by"] != actor.principal_id:
        return _deny("forbidden", "rbac_denied")
    if rr["state"] != "authorization_pending":
        return _deny("invalid_transition", f"already_{rr['state']}"[:64])

    outcome = await authz.cancel(
        conn, str(rr["authorization_id"]), actor=actor, actor_scope=actor_scope
    )
    if not outcome.ok:
        return _deny(outcome.result_kind, outcome.reason_code)

    updated = await repo.transition_to_canceled(
        conn,
        replay_request_id,
        scope_team_id=actor_scope.team_id,
        scope_project_id=actor_scope.project_id,
    )
    if updated is None:
        return _deny("conflict", "conflict")
    await _emit(
        conn,
        clarification_id=str(await _clarification_id_for(conn, rr)),
        task_id=str(await _task_id_for(conn, rr)),
        event_type="replay.canceled",
        idempotency_key=f"replay-canceled:{rr['outbox_event_id']}:{replay_request_id}",
        payload={"replay_request_id": replay_request_id, "reason": "operator_canceled"},
    )
    return ReplayResult(True, "ok", "operator_canceled", updated)


async def _clarification_id_for(conn: asyncpg.Connection, rr: dict[str, Any]) -> str:
    row = await conn.fetchrow(
        "SELECT clarification_id FROM clarification_lifecycle_outbox WHERE id=$1",
        rr["outbox_event_id"],
    )
    assert row is not None
    return str(row["clarification_id"])


async def _task_id_for(conn: asyncpg.Connection, rr: dict[str, Any]) -> str:
    row = await conn.fetchrow(
        "SELECT task_id FROM clarification_lifecycle_outbox WHERE id=$1", rr["outbox_event_id"]
    )
    assert row is not None
    return str(row["task_id"])


async def execute_authorized_replay(
    conn: asyncpg.Connection,
    replay_request_id: str,
    *,
    actor: Actor,
    actor_scope: Scope,
    readiness_provider: Callable[[str], str] | None = None,
) -> ReplayResult:
    """Internal Service-Identity-only: consume the authorization and call the transaction-aware
    replay_dead adapter (one transaction). GATED: does nothing when the execution gate is disabled.
    Requires destination readiness (never assumed ready by default -- see
    replay_request_model.default_destination_readiness). Does NOT publish anything downstream."""
    if not model.replay_execution_enabled():
        return _deny("execution_gate_disabled", "execution_gate_disabled")
    rr, masked = await _load_visible(conn, replay_request_id, actor_scope)
    if masked is not None:
        return masked
    assert rr is not None
    if rr["state"] != "authorized":
        return _deny("invalid_transition", f"invalid_transition:{rr['state']}"[:64])

    event_row = await repo.lock_outbox_event(conn, str(rr["outbox_event_id"]))
    if event_row is None:
        return _deny("not_found_masked", "resource_not_found")
    denial = _dead_eligibility_denial(event_row)
    if denial is not None:
        return denial
    current_version = model.dead_episode_state_version(
        dead_at=event_row["dead_at"], attempts=event_row["attempts"]
    )
    if current_version != rr["resource_state_version"]:
        return _deny("stale_state", "stale_state")

    provider = readiness_provider or model.default_destination_readiness
    readiness = provider(rr["destination"])
    if readiness not in model.READINESS_KINDS:
        readiness = model.READINESS_UNKNOWN_DESTINATION
    if readiness != model.READINESS_READY:
        # Blocked, NOT a state transition and NOT a mutation: the request stays 'authorized' so a
        # later attempt can proceed once the destination becomes ready. No consume, no dead-row
        # mutation -- only an audit trail of the blocked attempt.
        await _emit(
            conn,
            clarification_id=str(event_row["clarification_id"]),
            task_id=str(event_row["task_id"]),
            event_type="replay.execution_blocked",
            idempotency_key=f"replay-blocked:{rr['outbox_event_id']}:{replay_request_id}:{readiness}",
            payload={"replay_request_id": replay_request_id, "reason": "destination_unavailable"},
        )
        return _deny("destination_unavailable", "destination_unavailable")

    # Consume the single-use authorization (service-identity-only + production gate + CAS). Any
    # failure returns here WITHOUT touching the dead row.
    consumed = await authz.consume(
        conn,
        str(rr["authorization_id"]),
        actor=actor,
        actor_scope=actor_scope,
        resource_state_version=rr["resource_state_version"],
    )
    if not consumed.ok:
        return _deny(consumed.result_kind, consumed.reason_code)

    # Call the transaction-aware internal replay adapter -- same guard, same transaction. If this
    # returns None (should be unreachable here since we hold the row lock and just revalidated the
    # SAME version above), raise so the WHOLE transaction (including the consume) rolls back --
    # never leave a consumed authorization with no applied replay.
    replayed_row = await repo.replay_dead_row(
        conn, str(rr["outbox_event_id"]), expected_resource_state_version=current_version
    )
    if replayed_row is None:
        raise RuntimeError("replay_dead_row guard failed after a successful authorization consume")

    updated = await repo.transition_to_executed(
        conn,
        replay_request_id,
        scope_team_id=actor_scope.team_id,
        scope_project_id=actor_scope.project_id,
    )
    if updated is None:
        raise RuntimeError(
            "replay_requests transition-to-executed failed after a successful replay"
        )

    await _emit(
        conn,
        clarification_id=str(event_row["clarification_id"]),
        task_id=str(event_row["task_id"]),
        event_type="replay.executed",
        idempotency_key=f"replay-executed:{rr['outbox_event_id']}:{replay_request_id}",
        payload={
            "replay_request_id": replay_request_id,
            "outbox_event_id": str(rr["outbox_event_id"]),
        },
    )
    return ReplayResult(True, "ok", "policy_allow", updated)
