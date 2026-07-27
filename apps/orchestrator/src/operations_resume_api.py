"""Step 66C.4-BE3-B -- operator-controlled resume request API (DISABLED-BY-DEFAULT).

POST /operations/resume-requests                     Operator            create request
GET  /operations/resume-requests/{id}                Operator/Approver/Audit  read state
POST /operations/resume-requests/{id}/authorize      Policy Authority    authorize
POST /operations/resume-requests/{id}/reject         Policy Authority    reject
POST /operations/resume-requests/{id}/cancel         Operator(own)/Platform Admin  cancel

Backend foundation only: NO orchestrator call, NO resume execution, NO event publish. The whole
router is gated by BE3_RESUME_API_ENABLED (fail-closed 503 when disabled -- no DB access at all).
The resume execution COMMAND path is a separate, internal, BE3_RESUME_COMMAND_ENABLED-gated service
op (resume_service.prepare_execution); it is NOT exposed here.

Principal model (be3-rbac-permission-matrix.md, §8): Operators authenticate via the existing
fail-closed test auth (task_api._authenticate, X-Task-Actor/X-Task-Role). The POLICY/SAFETY AUTHORITY
that authorizes/rejects a resume is NOT a client-asserted role and is NOT satisfiable by an ordinary
Operator, even one that knows or guesses a header value (Step 66C.4-BE3-B-C1). It requires BOTH:
  1. the authenticated actor id (X-Task-Actor) exactly matches a server-configured trusted principal
     id (BE3_RESUME_POLICY_AUTHORITY_PRINCIPAL_ID) -- an internal service account, never a human
     Operator's own actor id; and
  2. the caller presents the correct server-side capability (current or, during a rotation window,
     previous -- BE3_RESUME_POLICY_AUTHORITY_CAPABILITY[_PREVIOUS]) over a dedicated header, compared
     with hmac.compare_digest (constant-time; never `==`/`!=` on the secret).
Both conditions are always evaluated (no short-circuit) so failure timing cannot distinguish "wrong
principal" from "wrong/missing capability" from "not configured" -- every failure raises the SAME
403 policy_authority_required, and the presented value is NEVER echoed into a log, audit payload, or
exception. The capability is NEVER read from the request body, query string, or the general
X-Task-Role header. A resolved policy-authority Actor carries a fixed role label
(_POLICY_AUTHORITY_ROLE), never the caller's own X-Task-Role, and is_policy_authority=True restricts
it (in authorization_policy.evaluate) to ONLY authorize_resume/reject_resume -- it can never request,
cancel, consume, or touch the independent production-approval gate. Scope (team_id/project_id) is
supplied by the caller and enforced by EXACT null-safe equality in the repository (BE3-A-C2).
"""

from __future__ import annotations

import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

import task_api
from shared.sdk.tasks import resume_request_model as model
from shared.sdk.tasks import resume_service
from shared.sdk.tasks.audit_events import DECISION_TASK_RBAC_DENIED, safe_task_refs
from shared.sdk.tasks.authorization_policy import Actor, Scope

router = APIRouter(prefix="/operations", tags=["resume"])

_OPERATOR_ROLES = frozenset({"pm_engineering_lead", "platform_admin", "agent_operator"})
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
    "feature_disabled": 503,
    "command_gate_disabled": 503,
}


class ResumeRequestCreate(BaseModel):
    clarification_id: str
    team_id: str
    project_id: str
    idempotency_key: str
    expires_in_seconds: int = Field(default=3600, ge=1, le=86400)
    production_effect: bool = False
    production_approval_reference: str | None = None


class ResumeScopeBody(BaseModel):
    team_id: str
    project_id: str


class ResumeDecisionBody(ResumeScopeBody):
    policy_version: str = "v1"
    reason_code: str | None = None


def _require_api_enabled() -> None:
    """Fail-closed gate for the whole router. No DB access happens before this passes."""
    if not model.resume_api_enabled():
        raise HTTPException(status_code=503, detail="feature_disabled")


def _operator(request: Request) -> Actor:
    ctx = task_api._authenticate(request)
    return Actor(principal_id=ctx.actor, role=ctx.role)


# The policy authority is an internal machine identity, not one of the six TASK_ROLES -- this is
# an audit label only (authorization_policy.evaluate branches on is_policy_authority BEFORE any
# TASK_ROLES membership check, so this string never needs to be a valid TASK_ROLE).
_POLICY_AUTHORITY_ROLE = "policy_authority"

# Defense in depth: bound the header before any comparison so an oversized/malformed value is
# rejected outright rather than fed into hmac.compare_digest.
_MAX_CAPABILITY_HEADER_CHARS = 256


def _configured_policy_authority_principal() -> str:
    """The single trusted internal principal id allowed to ever become the policy authority.
    Unset -> the mechanism is off and can never be satisfied (fail-closed)."""
    return os.environ.get("BE3_RESUME_POLICY_AUTHORITY_PRINCIPAL_ID", "").strip()


def _configured_capabilities() -> tuple[str, ...]:
    """Current + optional previous capability value, enabling smooth rotation: an operator sets a
    new BE3_RESUME_POLICY_AUTHORITY_CAPABILITY and keeps the old value in
    BE3_RESUME_POLICY_AUTHORITY_CAPABILITY_PREVIOUS until every internal caller has picked up the
    new one, then clears _PREVIOUS. Unset/empty entries are dropped; both unset -> [] (fail-closed:
    nothing can ever match)."""
    values = (
        os.environ.get("BE3_RESUME_POLICY_AUTHORITY_CAPABILITY", "").strip(),
        os.environ.get("BE3_RESUME_POLICY_AUTHORITY_CAPABILITY_PREVIOUS", "").strip(),
    )
    return tuple(v for v in values if v)


def _capability_matches(presented: str, configured: tuple[str, ...]) -> bool:
    """Constant-time membership check. Rejects an empty/oversized presented value outright (never
    compared); otherwise compares against EVERY configured value (no short-circuit on the first
    match) so timing does not reveal which rotation slot, if any, is currently valid."""
    if not presented or len(presented) > _MAX_CAPABILITY_HEADER_CHARS or not configured:
        return False
    matched = False
    presented_bytes = presented.encode("utf-8")
    for value in configured:
        if hmac.compare_digest(presented_bytes, value.encode("utf-8")):
            matched = True
    return matched


def _policy_authority(request: Request) -> Actor:
    """Resolve the policy/safety authority: an authenticated TRUSTED PRINCIPAL (a fixed,
    server-configured internal principal id -- never an arbitrary Operator, even one who adds the
    header themselves) presenting the correct server-side capability (current or previous) over a
    dedicated header. NEVER read from the request body, query string, or the general X-Task-Role
    header. Both checks always run (no short-circuit); every failure -- missing/empty/oversized/
    malformed capability, an unconfigured server, or a mismatched principal id -- raises the
    IDENTICAL 403 policy_authority_required, and the presented value is never logged, audited, or
    echoed in the response."""
    ctx = task_api._authenticate(request)
    trusted_principal = _configured_policy_authority_principal()
    presented = request.headers.get("X-Resume-Policy-Authority", "").strip()
    configured = _configured_capabilities()
    principal_ok = bool(trusted_principal) and ctx.actor == trusted_principal
    capability_ok = _capability_matches(presented, configured)
    if not (principal_ok and capability_ok):
        raise HTTPException(status_code=403, detail="policy_authority_required")
    return Actor(principal_id=ctx.actor, role=_POLICY_AUTHORITY_ROLE, is_policy_authority=True)


async def _deny_rbac(actor: Actor, action: str, reason: str) -> None:
    refs = safe_task_refs(actor=actor.principal_id, role=actor.role, action=action, status=reason)
    await task_api._audit(
        DECISION_TASK_RBAC_DENIED, f"resume rbac denied: {reason}", "denied", refs
    )
    raise HTTPException(status_code=403, detail=reason)


def _raise_for(result: resume_service.ResumeResult) -> None:
    if result.ok:
        return
    status = _STATUS_BY_KIND.get(result.result_kind, 409)
    raise HTTPException(status_code=status, detail=result.reason_code)


async def _connect():
    return await task_api._store()._connect()


@router.post("/resume-requests", status_code=201)
async def create_resume_request(payload: ResumeRequestCreate, request: Request) -> dict[str, Any]:
    _require_api_enabled()
    actor = _operator(request)
    if actor.role not in _OPERATOR_ROLES:
        await _deny_rbac(actor, "request_resume", "rbac_denied")
    scope = Scope(team_id=payload.team_id, project_id=payload.project_id)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=payload.expires_in_seconds)
    conn = await _connect()
    try:
        async with conn.transaction():
            result = await resume_service.request_resume(
                conn,
                actor=actor,
                actor_scope=scope,
                clarification_id=payload.clarification_id,
                idempotency_key=payload.idempotency_key,
                expires_at=expires_at,
                production_effect=payload.production_effect,
                production_approval_reference=payload.production_approval_reference,
            )
            _raise_for(result)
    finally:
        await conn.close()
    return _view(result)


@router.get("/resume-requests/{resume_request_id}")
async def get_resume_request(
    resume_request_id: str, request: Request, team_id: str, project_id: str
) -> dict[str, Any]:
    _require_api_enabled()
    actor = _operator(request)
    if actor.role not in _VIEW_ROLES:
        await _deny_rbac(actor, "view_resume_request", "rbac_denied")
    scope = Scope(team_id=team_id, project_id=project_id)
    conn = await _connect()
    try:
        result = await resume_service.get_resume_request(conn, resume_request_id, actor_scope=scope)
        _raise_for(result)
    finally:
        await conn.close()
    return _view(result)


@router.post("/resume-requests/{resume_request_id}/authorize")
async def authorize_resume_request(
    resume_request_id: str, payload: ResumeDecisionBody, request: Request
) -> dict[str, Any]:
    _require_api_enabled()
    actor = _policy_authority(request)
    scope = Scope(team_id=payload.team_id, project_id=payload.project_id)
    conn = await _connect()
    try:
        async with conn.transaction():
            result = await resume_service.authorize_resume(
                conn,
                resume_request_id,
                actor=actor,
                actor_scope=scope,
                policy_version=payload.policy_version,
            )
            _raise_for(result)
    finally:
        await conn.close()
    return _view(result)


@router.post("/resume-requests/{resume_request_id}/reject")
async def reject_resume_request(
    resume_request_id: str, payload: ResumeDecisionBody, request: Request
) -> dict[str, Any]:
    _require_api_enabled()
    actor = _policy_authority(request)
    scope = Scope(team_id=payload.team_id, project_id=payload.project_id)
    conn = await _connect()
    try:
        async with conn.transaction():
            result = await resume_service.reject_resume(
                conn,
                resume_request_id,
                actor=actor,
                actor_scope=scope,
                reason_code=payload.reason_code or "policy_deny",
            )
            _raise_for(result)
    finally:
        await conn.close()
    return _view(result)


@router.post("/resume-requests/{resume_request_id}/cancel")
async def cancel_resume_request(
    resume_request_id: str, payload: ResumeScopeBody, request: Request
) -> dict[str, Any]:
    _require_api_enabled()
    actor = _operator(request)
    if actor.role not in _OPERATOR_ROLES:
        await _deny_rbac(actor, "cancel_resume", "rbac_denied")
    scope = Scope(team_id=payload.team_id, project_id=payload.project_id)
    conn = await _connect()
    try:
        async with conn.transaction():
            result = await resume_service.cancel_resume(
                conn, resume_request_id, actor=actor, actor_scope=scope
            )
            _raise_for(result)
    finally:
        await conn.close()
    return _view(result)


def _view(result: resume_service.ResumeResult) -> dict[str, Any]:
    rr = result.resume_request or {}
    return {
        "resume_request_id": (
            str(rr.get("resume_request_id")) if rr.get("resume_request_id") else None
        ),
        "authorization_id": str(rr.get("authorization_id")) if rr.get("authorization_id") else None,
        "clarification_id": str(rr.get("clarification_id")) if rr.get("clarification_id") else None,
        "task_id": str(rr.get("task_id")) if rr.get("task_id") else None,
        "state": rr.get("state"),
        "reason_code": result.reason_code,
        "resume_dispatch_enabled": model.resume_command_enabled(),
        "dispatch_enabled": False,
    }


__all__ = ["router"]
