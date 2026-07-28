"""Step 66C.4-BE3-C -- authorized dead-event replay request API (DISABLED-BY-DEFAULT).

POST /operations/replay-requests                    Operator            create a replay request
GET  /operations/replay-requests/{id}               Operator/Approver/Audit  read state
POST /operations/replay-requests/{id}/authorize     Approver (requester != approver)  authorize
POST /operations/replay-requests/{id}/reject        Operator/Approver   reject
POST /operations/replay-requests/{id}/cancel        Operator(own)/Platform Admin  cancel

Backend foundation only: NO dead-outbox replay execution in any shared runtime, NO event publish,
NO downstream consumer. The whole router is gated by BE3_REPLAY_API_ENABLED (fail-closed 503 when
disabled -- no DB access at all). The replay EXECUTION path is a separate, internal,
BE3_REPLAY_EXECUTION_ENABLED-gated Service-Identity-only service op
(replay_service.execute_authorized_replay); it is NOT exposed here and there is NO public
`/execute` or `/replay-now` endpoint.

Two-person control (Approver != requester) reuses the UNCHANGED BE3-A authorization policy/DB
constraint (action_type='replay'); no second parallel two-person mechanism is introduced. Approver
roles are the canonical TASK_ROLES {reviewer_approver, platform_admin} -- unlike resume's automated
policy authority, replay authorization is a human Approver decision.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

import task_api
from shared.sdk.tasks import replay_request_model as model
from shared.sdk.tasks import replay_service
from shared.sdk.tasks.audit_events import DECISION_TASK_RBAC_DENIED, safe_task_refs
from shared.sdk.tasks.authorization_policy import Actor, Scope

router = APIRouter(prefix="/operations", tags=["replay"])

_OPERATOR_ROLES = frozenset({"pm_engineering_lead", "platform_admin", "agent_operator"})
_APPROVER_ROLES = frozenset({"reviewer_approver", "platform_admin"})
_VIEW_ROLES = frozenset(
    {
        "pm_engineering_lead",
        "platform_admin",
        "agent_operator",
        "reviewer_approver",
        "security_compliance_reviewer",
    }
)

_STATUS_BY_KIND = {
    "forbidden": 403,
    "not_found_masked": 404,
    "conflict": 409,
    "not_eligible": 409,
    "stale_state": 409,
    "already_authorized": 409,
    "already_rejected": 409,
    "already_canceled": 409,
    "production_approval_required": 409,
    "invalid_transition": 409,
    "rate_limited": 409,
    "destination_unavailable": 409,
    "feature_disabled": 503,
    "execution_gate_disabled": 503,
}


class ReplayRequestCreate(BaseModel):
    outbox_event_id: str
    team_id: str
    project_id: str
    idempotency_key: str
    expires_in_seconds: int = Field(default=3600, ge=1, le=86400)
    production_approval_reference: str | None = None


class ReplayScopeBody(BaseModel):
    team_id: str
    project_id: str


class ReplayDecisionBody(ReplayScopeBody):
    policy_version: str = "v1"
    reason_code: str | None = None


def _require_api_enabled() -> None:
    """Fail-closed gate for the whole router. No DB access happens before this passes."""
    if not model.replay_api_enabled():
        raise HTTPException(status_code=503, detail="feature_disabled")


def _operator(request: Request) -> Actor:
    ctx = task_api._authenticate(request)
    return Actor(principal_id=ctx.actor, role=ctx.role)


async def _deny_rbac(actor: Actor, action: str, reason: str) -> None:
    refs = safe_task_refs(actor=actor.principal_id, role=actor.role, action=action, status=reason)
    await task_api._audit(
        DECISION_TASK_RBAC_DENIED, f"replay rbac denied: {reason}", "denied", refs
    )
    raise HTTPException(status_code=403, detail=reason)


def _raise_for(result: replay_service.ReplayResult) -> None:
    if result.ok:
        return
    status = _STATUS_BY_KIND.get(result.result_kind, 409)
    raise HTTPException(status_code=status, detail=result.reason_code)


async def _connect():
    return await task_api._store()._connect()


@router.post("/replay-requests", status_code=201)
async def create_replay_request(payload: ReplayRequestCreate, request: Request) -> dict[str, Any]:
    _require_api_enabled()
    actor = _operator(request)
    if actor.role not in _OPERATOR_ROLES:
        await _deny_rbac(actor, "request_replay", "rbac_denied")
    scope = Scope(team_id=payload.team_id, project_id=payload.project_id)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=payload.expires_in_seconds)
    conn = await _connect()
    try:
        async with conn.transaction():
            result = await replay_service.request_replay(
                conn,
                actor=actor,
                actor_scope=scope,
                outbox_event_id=payload.outbox_event_id,
                idempotency_key=payload.idempotency_key,
                expires_at=expires_at,
                production_approval_reference=payload.production_approval_reference,
            )
            _raise_for(result)
    finally:
        await conn.close()
    return _view(result)


@router.get("/replay-requests/{replay_request_id}")
async def get_replay_request(
    replay_request_id: str, request: Request, team_id: str, project_id: str
) -> dict[str, Any]:
    _require_api_enabled()
    actor = _operator(request)
    if actor.role not in _VIEW_ROLES:
        await _deny_rbac(actor, "view_replay_request", "rbac_denied")
    scope = Scope(team_id=team_id, project_id=project_id)
    conn = await _connect()
    try:
        result = await replay_service.get_replay_request(conn, replay_request_id, actor_scope=scope)
        _raise_for(result)
    finally:
        await conn.close()
    return _view(result)


@router.post("/replay-requests/{replay_request_id}/authorize")
async def authorize_replay_request(
    replay_request_id: str, payload: ReplayDecisionBody, request: Request
) -> dict[str, Any]:
    _require_api_enabled()
    actor = _operator(request)
    if actor.role not in _APPROVER_ROLES:
        await _deny_rbac(actor, "authorize_replay", "rbac_denied")
    scope = Scope(team_id=payload.team_id, project_id=payload.project_id)
    conn = await _connect()
    try:
        async with conn.transaction():
            result = await replay_service.authorize_replay(
                conn,
                replay_request_id,
                actor=actor,
                actor_scope=scope,
                policy_version=payload.policy_version,
            )
            _raise_for(result)
    finally:
        await conn.close()
    return _view(result)


@router.post("/replay-requests/{replay_request_id}/reject")
async def reject_replay_request(
    replay_request_id: str, payload: ReplayDecisionBody, request: Request
) -> dict[str, Any]:
    _require_api_enabled()
    actor = _operator(request)
    if actor.role not in (_OPERATOR_ROLES | _APPROVER_ROLES):
        await _deny_rbac(actor, "reject_replay", "rbac_denied")
    scope = Scope(team_id=payload.team_id, project_id=payload.project_id)
    conn = await _connect()
    try:
        async with conn.transaction():
            result = await replay_service.reject_replay(
                conn,
                replay_request_id,
                actor=actor,
                actor_scope=scope,
                reason_code=payload.reason_code or "policy_deny",
            )
            _raise_for(result)
    finally:
        await conn.close()
    return _view(result)


@router.post("/replay-requests/{replay_request_id}/cancel")
async def cancel_replay_request(
    replay_request_id: str, payload: ReplayScopeBody, request: Request
) -> dict[str, Any]:
    _require_api_enabled()
    actor = _operator(request)
    if actor.role not in _OPERATOR_ROLES:
        await _deny_rbac(actor, "cancel_replay", "rbac_denied")
    scope = Scope(team_id=payload.team_id, project_id=payload.project_id)
    conn = await _connect()
    try:
        async with conn.transaction():
            result = await replay_service.cancel_replay(
                conn, replay_request_id, actor=actor, actor_scope=scope
            )
            _raise_for(result)
    finally:
        await conn.close()
    return _view(result)


def _view(result: replay_service.ReplayResult) -> dict[str, Any]:
    rr = result.replay_request or {}
    return {
        "replay_request_id": (
            str(rr.get("replay_request_id")) if rr.get("replay_request_id") else None
        ),
        "authorization_id": str(rr.get("authorization_id")) if rr.get("authorization_id") else None,
        "outbox_event_id": str(rr.get("outbox_event_id")) if rr.get("outbox_event_id") else None,
        "destination": rr.get("destination"),
        "state": rr.get("state"),
        "reason_code": result.reason_code,
        "execution_enabled": model.replay_execution_enabled(),
        "dispatch_enabled": False,
    }


__all__ = ["router"]
