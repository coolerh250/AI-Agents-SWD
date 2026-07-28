"""Step 66C.4-BE3-R1 (finding M-1 closure) -- internal production-action approval service.

Ties the granter RBAC (canonical TASK_ROLES {reviewer_approver, platform_admin} -- the "Approve /
reject gated action" capability) to the durable production_action_approvals repository (CAS
transitions). Grant/revoke are INTERNAL service operations only in this stage: no HTTP endpoint is
registered anywhere (be3-r1-m1-production-approval-contract.md §2.8) -- tests, and any future
authorized API layer, call these functions directly, exactly as every other BE3 service is composed.

Every function takes the caller's asyncpg connection and runs inside the caller's transaction.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg

from shared.sdk.tasks import production_approval_model as model
from shared.sdk.tasks import production_approval_repository as repo
from shared.sdk.tasks.authorization_policy import Actor, Scope


@dataclass(frozen=True)
class ApprovalResult:
    ok: bool
    result_kind: str
    reason_code: str
    approval: dict[str, Any] | None = None
    audit_payload: dict[str, Any] | None = None


def _deny(result_kind: str, reason_code: str) -> ApprovalResult:
    return ApprovalResult(False, result_kind, reason_code)


async def _audit(
    conn: asyncpg.Connection, *, event: str, row: dict[str, Any], actor: Actor, reason_code: str
) -> dict[str, Any]:
    now = await repo.db_now(conn)
    return model.build_production_approval_audit_payload(
        event=event,
        approval_id=str(row["approval_id"]),
        action_type=row["action_type"],
        resource_type=row["resource_type"],
        resource_id=str(row["resource_id"]),
        actor_id=actor.principal_id,
        actor_role=actor.role,
        reason_code=reason_code,
        state=model.project_state(row, now=now),
        team_id=str(row["team_id"]) if row.get("team_id") else None,
        project_id=str(row["project_id"]) if row.get("project_id") else None,
        resource_state_version=row.get("resource_state_version"),
        authorization_id=(
            str(row["consumed_by_authorization_id"])
            if row.get("consumed_by_authorization_id")
            else None
        ),
        idempotency_key=row.get("idempotency_key"),
    )


async def grant_production_approval(
    conn: asyncpg.Connection,
    *,
    actor: Actor,
    actor_scope: Scope,
    action_type: str,
    resource_type: str,
    resource_id: str,
    resource_state_version: str,
    expires_at: datetime,
    idempotency_key: str,
    reason_code: str | None = None,
) -> ApprovalResult:
    """A canonical Approver (reviewer_approver / platform_admin) grants a single-use, resource-bound
    production approval (one transaction). This is a schema-level, no-HTTP-endpoint capability in
    this stage -- callers are internal (tests, and a future authorized API)."""
    if action_type not in model.ACTION_TYPES:
        return _deny("forbidden", "unknown_action_type")
    if resource_type not in model.RESOURCE_TYPES:
        return _deny("forbidden", "unknown_resource_type")
    if not model.can_grant(actor.role):
        return _deny("forbidden", "rbac_denied")

    # Idempotent re-confirm: the same idempotency_key returns the same approval (scoped).
    existing = await repo.get_approval_by_idempotency_key(conn, idempotency_key)
    if existing is not None:
        if str(existing["team_id"]) != (actor_scope.team_id or "") or str(
            existing["project_id"]
        ) != (actor_scope.project_id or ""):
            return _deny("not_found_masked", "not_found")
        return ApprovalResult(True, "ok", "granted", existing)

    try:
        row = await repo.insert_approval(
            conn,
            action_type=action_type,
            resource_type=resource_type,
            resource_id=resource_id,
            team_id=actor_scope.team_id or "",
            project_id=actor_scope.project_id or "",
            resource_state_version=resource_state_version,
            granted_by=actor.principal_id,
            granted_role=actor.role,
            expires_at=expires_at,
            idempotency_key=idempotency_key,
            reason_code=reason_code,
        )
    except asyncpg.UniqueViolationError:
        return _deny("conflict", "conflict")

    return ApprovalResult(
        True,
        "ok",
        "granted",
        row,
        await _audit(
            conn, event="production_approval.granted", row=row, actor=actor, reason_code="granted"
        ),
    )


async def revoke_production_approval(
    conn: asyncpg.Connection,
    approval_id: str,
    *,
    actor: Actor,
    actor_scope: Scope,
    reason_code: str = "operator_revoked",
) -> ApprovalResult:
    """A canonical Approver revokes a still-granted (unconsumed) approval (one transaction)."""
    if not model.can_grant(actor.role):
        return _deny("forbidden", "rbac_denied")
    model.assert_reason_code(reason_code)
    row = await repo.get_approval(
        conn,
        approval_id,
        scope_team_id=actor_scope.team_id,
        scope_project_id=actor_scope.project_id,
    )
    if row is None:
        return _deny("not_found_masked", "not_found")

    updated = await repo.revoke_approval(
        conn,
        approval_id,
        revoked_by=actor.principal_id,
        reason_code=reason_code,
        scope_team_id=actor_scope.team_id,
        scope_project_id=actor_scope.project_id,
    )
    if updated is None:
        return _deny("invalid_transition", "invalid_transition")
    return ApprovalResult(
        True,
        "ok",
        reason_code,
        updated,
        await _audit(
            conn,
            event="production_approval.revoked",
            row=updated,
            actor=actor,
            reason_code=reason_code,
        ),
    )
