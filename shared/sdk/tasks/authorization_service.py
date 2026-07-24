"""Step 66C.4-BE3-A -- internal resume/replay authorization service.

Ties the policy service (RBAC + isolation + separation + production gate) to the durable repository
(CAS transitions). Returns a safe, API-independent structured outcome for every operation.

This service is a FOUNDATION only. It does NOT execute resume, does NOT call the dead-outbox replay adapter, does NOT
publish an execution command, and exposes NO HTTP route. Consuming an authorization records a
durable single-use CAS; the actual resume/replay execution is a later stage (BE3-B / BE3-C), gated
and unauthorized here.

Every method takes the caller's asyncpg connection and runs inside the caller's transaction, so an
authorization transition and its audit/outbox row can commit atomically under the caller's boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg

from shared.sdk.tasks import authorization_repository as repo
from shared.sdk.tasks.authorization_model import (
    build_audit_payload,
    project_state,
)
from shared.sdk.tasks.authorization_policy import Actor, PolicyOutcome, Scope, evaluate


@dataclass(frozen=True)
class ServiceResult:
    ok: bool
    result_kind: str
    reason_code: str
    authorization: dict[str, Any] | None = None
    audit_payload: dict[str, Any] | None = None

    @property
    def state(self) -> str | None:
        return self.audit_payload.get("state") if self.audit_payload else None


def _deny(outcome: PolicyOutcome) -> ServiceResult:
    return ServiceResult(False, outcome.result_kind, outcome.reason_code)


async def _audit(
    conn: asyncpg.Connection, *, event: str, row: dict[str, Any], actor: Actor, reason_code: str
) -> dict[str, Any]:
    now = await repo.db_now(conn)
    return build_audit_payload(
        event=event,
        authorization_id=str(row["authorization_id"]),
        action_type=row["action_type"],
        resource_type=row["resource_type"],
        resource_id=str(row["resource_id"]),
        actor_id=actor.principal_id,
        actor_role=actor.role,
        reason_code=reason_code,
        state=project_state(row, now=now),
        team_id=str(row["team_id"]) if row.get("team_id") else None,
        project_id=str(row["project_id"]) if row.get("project_id") else None,
        request_id=str(row["request_id"]),
        policy_result=row.get("policy_result"),
        policy_version=row.get("policy_version"),
        resource_state_version=row.get("resource_state_version"),
        production_effect=row.get("production_effect"),
        idempotency_key=row.get("idempotency_key"),
    )


async def request_authorization(
    conn: asyncpg.Connection,
    *,
    actor: Actor,
    actor_scope: Scope,
    resource_scope: Scope,
    action_type: str,
    resource_type: str,
    resource_id: str,
    resource_state_version: str,
    expires_at: datetime,
    idempotency_key: str,
    production_effect: bool = False,
    production_approval_reference: str | None = None,
) -> ServiceResult:
    outcome = evaluate(
        action=f"request_{action_type}",
        actor=actor,
        actor_scope=actor_scope,
        resource_scope=resource_scope,
    )
    if not outcome.allowed:
        return _deny(outcome)
    try:
        row = await repo.create_request(
            conn,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            requested_by=actor.principal_id,
            requested_role=actor.role,
            resource_state_version=resource_state_version,
            expires_at=expires_at,
            idempotency_key=idempotency_key,
            team_id=resource_scope.team_id,
            project_id=resource_scope.project_id,
            production_effect=production_effect,
            production_approval_reference=production_approval_reference,
        )
    except asyncpg.UniqueViolationError as exc:
        # Idempotent re-confirm on the same key; otherwise an active request already exists.
        existing = await conn.fetchrow(
            "SELECT * FROM resume_replay_authorizations WHERE idempotency_key=$1",
            idempotency_key,
        )
        if existing is not None:
            row = dict(existing)
            return ServiceResult(
                True,
                "ok",
                "conflict" if "uq_rra_active_request" in str(exc) else "ok",
                row,
                await _audit(
                    conn, event="authorization.requested", row=row, actor=actor, reason_code="ok"
                ),
            )
        return ServiceResult(False, "conflict", "conflict")
    return ServiceResult(
        True,
        "ok",
        "policy_allow",
        row,
        await _audit(
            conn, event="authorization.requested", row=row, actor=actor, reason_code="policy_allow"
        ),
    )


async def _load_visible(
    conn: asyncpg.Connection, authorization_id: str, actor: Actor, actor_scope: Scope
) -> tuple[dict[str, Any] | None, ServiceResult | None]:
    row = await repo.get_authorization(conn, authorization_id)
    if row is None:
        return None, ServiceResult(False, "not_found_masked", "resource_not_found")
    resource_scope = Scope(
        team_id=str(row["team_id"]) if row.get("team_id") else None,
        project_id=str(row["project_id"]) if row.get("project_id") else None,
    )
    # Reuse the isolation check via a benign action to avoid leaking existence across scope.
    iso = evaluate(
        action="revoke",
        actor=(
            actor if not actor.is_service_identity else Actor(actor.principal_id, "platform_admin")
        ),
        actor_scope=actor_scope,
        resource_scope=resource_scope,
    )
    if not iso.allowed and iso.result_kind == "not_found_masked":
        return None, ServiceResult(False, "not_found_masked", "resource_not_found")
    return row, None


async def authorize(
    conn: asyncpg.Connection,
    authorization_id: str,
    *,
    actor: Actor,
    actor_scope: Scope,
    policy_version: str,
) -> ServiceResult:
    row, masked = await _load_visible(conn, authorization_id, actor, actor_scope)
    if masked is not None:
        return masked
    assert row is not None
    resource_scope = Scope(
        team_id=str(row["team_id"]) if row.get("team_id") else None,
        project_id=str(row["project_id"]) if row.get("project_id") else None,
    )
    outcome = evaluate(
        action=f"authorize_{row['action_type']}",
        actor=actor,
        actor_scope=actor_scope,
        resource_scope=resource_scope,
        requested_by=row["requested_by"],
    )
    if not outcome.allowed:
        return _deny(outcome)
    updated = await repo.approve(
        conn,
        authorization_id,
        decided_by=actor.principal_id,
        decided_role=actor.role,
        reason_code="policy_allow",
        policy_result="allow",
        policy_version=policy_version,
    )
    if updated is None:
        return ServiceResult(False, "already_decided", "already_decided")
    return ServiceResult(
        True,
        "ok",
        "policy_allow",
        updated,
        await _audit(
            conn,
            event="authorization.authorized",
            row=updated,
            actor=actor,
            reason_code="policy_allow",
        ),
    )


async def _decide_simple(
    conn: asyncpg.Connection,
    authorization_id: str,
    *,
    actor: Actor,
    actor_scope: Scope,
    op: str,
    event: str,
    reason_code: str,
) -> ServiceResult:
    row, masked = await _load_visible(conn, authorization_id, actor, actor_scope)
    if masked is not None:
        return masked
    assert row is not None
    resource_scope = Scope(
        team_id=str(row["team_id"]) if row.get("team_id") else None,
        project_id=str(row["project_id"]) if row.get("project_id") else None,
    )
    outcome = evaluate(
        action=f"{op}_{row['action_type']}" if op in ("reject", "cancel") else op,
        actor=actor,
        actor_scope=actor_scope,
        resource_scope=resource_scope,
    )
    if not outcome.allowed:
        return _deny(outcome)
    fn = {"reject": repo.reject, "cancel": repo.cancel}.get(op)
    if fn is not None:
        updated = await fn(
            conn,
            authorization_id,
            decided_by=actor.principal_id,
            decided_role=actor.role,
            reason_code=reason_code,
        )
    else:  # revoke
        updated = await repo.revoke(
            conn, authorization_id, revoked_by=actor.principal_id, reason_code=reason_code
        )
    if updated is None:
        return ServiceResult(False, "invalid_transition", "invalid_transition")
    return ServiceResult(
        True,
        "ok",
        reason_code,
        updated,
        await _audit(conn, event=event, row=updated, actor=actor, reason_code=reason_code),
    )


async def reject(conn, authorization_id, *, actor, actor_scope) -> ServiceResult:
    return await _decide_simple(
        conn,
        authorization_id,
        actor=actor,
        actor_scope=actor_scope,
        op="reject",
        event="authorization.rejected",
        reason_code="policy_deny",
    )


async def cancel(conn, authorization_id, *, actor, actor_scope) -> ServiceResult:
    return await _decide_simple(
        conn,
        authorization_id,
        actor=actor,
        actor_scope=actor_scope,
        op="cancel",
        event="authorization.canceled",
        reason_code="operator_canceled",
    )


async def revoke(conn, authorization_id, *, actor, actor_scope) -> ServiceResult:
    return await _decide_simple(
        conn,
        authorization_id,
        actor=actor,
        actor_scope=actor_scope,
        op="revoke",
        event="authorization.revoked",
        reason_code="operator_revoked",
    )


async def consume(
    conn: asyncpg.Connection,
    authorization_id: str,
    *,
    actor: Actor,
    actor_scope: Scope,
    resource_state_version: str,
) -> ServiceResult:
    """Single-use consume by the Service Identity ONLY. Does NOT execute resume/replay."""
    row, masked = await _load_visible(conn, authorization_id, actor, actor_scope)
    if masked is not None:
        return masked
    assert row is not None
    resource_scope = Scope(
        team_id=str(row["team_id"]) if row.get("team_id") else None,
        project_id=str(row["project_id"]) if row.get("project_id") else None,
    )
    outcome = evaluate(
        action=f"consume_{row['action_type']}",
        actor=actor,
        actor_scope=actor_scope,
        resource_scope=resource_scope,
        production_effect=bool(row.get("production_effect")),
        production_approval_reference=row.get("production_approval_reference"),
    )
    if not outcome.allowed:
        return _deny(outcome)
    updated = await repo.consume(
        conn,
        authorization_id,
        consumed_by=actor.principal_id,
        resource_state_version=resource_state_version,
    )
    if updated is not None:
        return ServiceResult(
            True,
            "ok",
            "policy_allow",
            updated,
            await _audit(
                conn,
                event="authorization.consumed",
                row=updated,
                actor=actor,
                reason_code="policy_allow",
            ),
        )
    # Classify the CAS failure with a safe reason code (re-read authoritative state).
    current = await repo.get_authorization(conn, authorization_id)
    now = await repo.db_now(conn)
    if current is None:
        return ServiceResult(False, "not_found_masked", "resource_not_found")
    if current.get("consumed_at") is not None:
        kind = "already_consumed"
    elif current.get("revoked_at") is not None:
        kind = "revoked"
    elif project_state(current, now=now) == "expired":
        kind = "expired"
    elif current.get("decision") != "authorized":
        kind = "invalid_transition"
    elif current.get("resource_state_version") != resource_state_version:
        kind = "stale_state"
    else:
        kind = "conflict"
    reason = {
        "stale_state": "stale_state",
        "expired": "expired",
        "revoked": "revoked",
        "already_consumed": "already_consumed",
        "invalid_transition": "invalid_transition",
        "conflict": "conflict",
    }[kind]
    return ServiceResult(
        False,
        kind,
        reason,
        None,
        await _audit(
            conn,
            event="authorization.consume_rejected",
            row=current,
            actor=actor,
            reason_code=reason,
        ),
    )
