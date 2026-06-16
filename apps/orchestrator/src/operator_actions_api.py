"""Stage 52 -- Admin Console v1 Operator Actions API.

Governed operator actions: authentication (test-local signed session), RBAC,
CSRF, policy-engine gate, one-time confirmation nonce, idempotency, audit, and
default-denied notifications. Only low-risk, reversible, allowlisted actions are
executable; high-risk actions return 403 policy_blocked / 409 action_disabled.

Acceptance is a HUMAN REVIEW acceptance only -- it never triggers GitHub, PR,
merge, deploy, external delivery, or production. ``production_executed`` stays
false everywhere.
"""

from __future__ import annotations

import contextlib
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response

from shared.sdk.delivery_package import DeliveryPackageStore
from shared.sdk.operator_actions import audit_events as ae
from shared.sdk.operator_actions import events as ev
from shared.sdk.operator_actions import OperatorActionStore
from shared.sdk.operator_actions.action_catalog import catalog_view, get_action_entry
from shared.sdk.operator_actions.auth import (
    TEST_OPERATOR_IDENTITY,
    resolve_auth_config,
    test_login_allowed,
)
from shared.sdk.operator_actions.confirmation import (
    confirmation_valid,
    expiry_ts,
    generate_nonce,
    nonce_hash,
)
from shared.sdk.operator_actions.csrf import CSRF_HEADER, issue_csrf, verify_csrf
from shared.sdk.operator_actions.idempotency import is_valid_key
from shared.sdk.operator_actions.models import (
    OperatorActionExecution,
    OperatorActionRequest,
    OperatorReviewNote,
    VerificationRerunRequest,
)
from shared.sdk.operator_actions.policy_gate import evaluate_action
from shared.sdk.operator_actions.rbac import highest_role
from shared.sdk.operator_actions.session import (
    DEFAULT_SESSION_TTL_SECONDS,
    issue_session,
    session_hash,
    verify_session,
)
from shared.sdk.operator_actions.verification_runner import (
    ALLOWLISTED_SCRIPTS,
    VerificationNotAllowed,
    requires_higher_confirmation,
    run_verification,
)

router = APIRouter(prefix="/operations/admin-console", tags=["operator-actions"])

COOKIE_NAME = "admin_console_session"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store() -> OperatorActionStore:
    return OperatorActionStore()


def _package_store() -> DeliveryPackageStore:
    return DeliveryPackageStore()


def _cookie_secure() -> bool:
    return str(os.environ.get("ADMIN_CONSOLE_COOKIE_SECURE", "false")).strip().lower() == "true"


def _policy_client():
    with contextlib.suppress(Exception):
        from shared.sdk.http_clients.policy_http_client import PolicyHttpClient

        return PolicyHttpClient()
    return None


class _AuthError(Exception):
    def __init__(self, status: int, reason: str) -> None:
        self.status = status
        self.reason = reason


async def _audit(decision_type: str, summary: str, result: str, refs: dict) -> None:
    with contextlib.suppress(Exception):
        from shared.sdk.audit.publisher import publish_audit_event

        await publish_audit_event(
            task_id="admin-console-operator-action",
            agent="operator-actions-api",
            decision_type=decision_type,
            summary=summary,
            result=result,
            artifact_refs=refs,
        )


async def _authenticate(request: Request) -> dict:
    """Resolve the signed session -> identity + roles. Fail-closed."""
    cfg = resolve_auth_config()
    if not cfg.operator_actions_enabled:
        raise _AuthError(403, "operator_actions_disabled")
    token = request.cookies.get(COOKIE_NAME, "")
    claims = verify_session(token)
    if not claims:
        raise _AuthError(401, "no_valid_session")
    sh = session_hash(token)
    sess = await _store().get_session_by_hash(sh)
    if not sess or sess.get("status") != "active":
        raise _AuthError(401, "session_revoked_or_expired")
    if sess.get("identity_status") != "active":
        raise _AuthError(403, "identity_disabled")
    ident = await _store().get_identity(sess["identity_key"])
    roles = ident.get("roles", []) if ident else []
    return {
        "identity_key": sess["identity_key"],
        "identity_id": ident.get("id") if ident else None,
        "roles": roles,
        "role": highest_role(roles),
        "session_hash": sh,
    }


def _require_csrf(request: Request, session_hash_value: str) -> None:
    token = request.headers.get(CSRF_HEADER, "")
    if not verify_csrf(token, session_hash_value):
        raise _AuthError(403, "csrf_invalid")


def _err(status: int, reason: str) -> dict:
    return {
        "status": "policy_blocked" if status == 403 else "error",
        "reason": reason,
        "production_executed": False,
        "github_write_performed": False,
        "pr_created": False,
        "deployment_performed": False,
        "external_delivery_performed": False,
    }


# ===========================================================================
# Authentication
# ===========================================================================
@router.post("/auth/test-login")
async def test_login(payload: dict | None = None, *, response: Response) -> dict:
    if not test_login_allowed():
        return {"status": "auth_disabled", "reason": "test_login_not_allowed"}
    role = (payload or {}).get("role", "operator")
    if role not in ("viewer", "reviewer", "operator", "platform_admin"):
        role = "operator"
    identity_key = (payload or {}).get("identity_key", TEST_OPERATOR_IDENTITY)
    await _store().upsert_identity(identity_key, roles=[role])
    token, _issued, expires = issue_session(identity_key, ttl_seconds=DEFAULT_SESSION_TTL_SECONDS)
    sh = session_hash(token)
    exp_iso = datetime.fromtimestamp(expires, tz=timezone.utc).isoformat()
    await _store().create_session(identity_key, sh, exp_iso)
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="strict",
        secure=_cookie_secure(),
        max_age=DEFAULT_SESSION_TTL_SECONDS,
        path="/",
    )
    await _audit(
        ae.DECISION_OPERATOR_SESSION_CREATED,
        "operator test session created",
        "completed",
        ae.safe_operator_action_refs(identity_key=identity_key, role=role),
    )
    return {
        "status": "ok",
        "identity_key": identity_key,
        "role": role,
        "roles": [role],
        "expires_at": exp_iso,
        "csrf_token": issue_csrf(sh),
    }


@router.post("/auth/logout")
async def logout(request: Request, response: Response) -> dict:
    token = request.cookies.get(COOKIE_NAME, "")
    if token:
        await _store().revoke_session(session_hash(token))
        await _audit(
            ae.DECISION_OPERATOR_SESSION_REVOKED,
            "operator session revoked",
            "completed",
            ae.safe_operator_action_refs(),
        )
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "logged_out"}


@router.get("/auth/session")
async def get_session(request: Request) -> dict:
    try:
        ctx = await _authenticate(request)
    except _AuthError as e:
        return {"authenticated": False, "reason": e.reason}
    return {
        "authenticated": True,
        "identity_key": ctx["identity_key"],
        "roles": ctx["roles"],
        "role": ctx["role"],
        "auth_mode": resolve_auth_config().auth_mode,
    }


@router.get("/auth/csrf")
async def get_csrf(request: Request) -> dict:
    try:
        ctx = await _authenticate(request)
    except _AuthError as e:
        return {"status": "unauthenticated", "reason": e.reason}
    return {"csrf_token": issue_csrf(ctx["session_hash"])}


# ===========================================================================
# Action catalog + history
# ===========================================================================
@router.get("/operator-actions/catalog")
async def action_catalog_endpoint() -> dict:
    return catalog_view()


@router.get("/operator-actions")
async def list_operator_actions(limit: int = 50) -> dict:
    return {"actions": await _store().list_actions(limit=limit)}


@router.get("/operator-actions/{action_id}")
async def get_operator_action(action_id: str) -> dict:
    action = await _store().get_action(action_id)
    if not action:
        return {"status": "not_found"}
    return action


# ===========================================================================
# Core action machinery
# ===========================================================================
async def _create_action(
    request: Request,
    *,
    action_type: str,
    target_type: str | None,
    target_id: str | None,
    reason: str,
    payload: dict,
    idempotency_key: str | None,
) -> dict:
    try:
        ctx = await _authenticate(request)
        _require_csrf(request, ctx["session_hash"])
    except _AuthError as e:
        return {"http_status": e.status, **_err(e.status, e.reason)}

    if not reason or not reason.strip():
        return {"http_status": 400, **_err(400, "reason_required")}
    if not is_valid_key(idempotency_key):
        return {"http_status": 400, **_err(400, "idempotency_key_required")}

    existing = await _store().find_action_by_idempotency(idempotency_key)
    if existing:
        return {
            "http_status": 200,
            "idempotent_replay": True,
            **existing,
            "production_executed": False,
        }

    entry = get_action_entry(action_type)
    if entry is None:
        return {"http_status": 403, **_err(403, "unknown_action_type")}

    decision = await evaluate_action(
        action_type=action_type,
        role=ctx["role"],
        target_type=target_type,
        target_id=target_id,
        policy_client=_policy_client(),
    )
    action_key = f"oa-{uuid.uuid4().hex[:16]}"
    needs_conf = decision.requires_confirmation and decision.allowed
    status = (
        "policy_blocked"
        if not decision.allowed
        else ("confirmation_required" if needs_conf else "requested")
    )
    req = OperatorActionRequest(
        action_key=action_key,
        identity_key=ctx["identity_key"],
        action_type=action_type,
        target_type=target_type,
        target_id=target_id,
        reason=reason.strip(),
        requested_payload=payload or {},
        risk_level=decision.risk_level,
        policy_status=decision.policy_status,
        confirmation_status="pending" if needs_conf else "not_required",
        idempotency_key=idempotency_key,
        status=status,
    )
    action_id = await _store().create_action_request(req, identity_id=ctx["identity_id"])

    await _audit(
        ae.DECISION_OPERATOR_ACTION_REQUESTED,
        f"operator action requested: {action_type}",
        status,
        ae.safe_operator_action_refs(
            action_key=action_key,
            action_type=action_type,
            identity_key=ctx["identity_key"],
            role=ctx["role"],
            target_type=target_type,
            target_id=target_id,
            policy_status=decision.policy_status,
            status=status,
        ),
    )

    if not decision.allowed:
        await _audit(
            ae.DECISION_OPERATOR_ACTION_POLICY_BLOCKED,
            f"policy blocked: {action_type}",
            "policy_blocked",
            ae.safe_operator_action_refs(
                action_key=action_key, action_type=action_type, policy_status=decision.policy_status
            ),
        )
        return {
            "http_status": 403,
            "action_id": action_id,
            "action_type": action_type,
            "status": "policy_blocked",
            "policy_status": decision.policy_status,
            "reason": decision.reason,
            "production_executed": False,
        }

    result: dict = {
        "http_status": 200,
        "action_id": action_id,
        "action_type": action_type,
        "status": status,
        "policy_status": decision.policy_status,
        "confirmation_required": needs_conf,
        "production_executed": False,
        "github_write_performed": False,
        "pr_created": False,
        "deployment_performed": False,
        "external_delivery_performed": False,
    }
    if needs_conf:
        nonce = generate_nonce()
        await _store().create_confirmation(
            action_id,
            ctx["identity_id"],
            nonce_hash(nonce),
            datetime.fromtimestamp(expiry_ts(), tz=timezone.utc).isoformat(),
        )
        result["confirmation_nonce"] = nonce  # returned once to the client
    else:
        await _execute_action(action_id, ctx, action_type, target_id, reason, payload, result)
    return result


async def _execute_action(action_id, ctx, action_type, target_id, reason, payload, result) -> None:
    """Run the concrete effect of an allowed, confirmed action."""
    await _store().update_action_status(action_id, status="executing")
    try:
        summary = await _apply_effect(action_type, target_id, reason, payload, ctx)
        await _store().create_execution(
            action_id,
            OperatorActionExecution(
                execution_type=action_type,
                status="completed",
                result_summary=summary,
                production_executed=False,
            ),
        )
        await _store().update_action_status(action_id, status="completed", completed=True)
        await _store().link_audit(action_id, ae.DECISION_OPERATOR_ACTION_COMPLETED)
        await _audit(
            ae.DECISION_OPERATOR_ACTION_COMPLETED,
            f"operator action completed: {action_type}",
            "completed",
            ae.safe_operator_action_refs(
                action_type=action_type,
                identity_key=ctx["identity_key"],
                status="completed",
                target_id=target_id,
            ),
        )
        result["status"] = "completed"
        result["result_summary"] = summary
    except Exception as exc:  # noqa: BLE001 - record failure, never leak internals
        await _store().create_execution(
            action_id,
            OperatorActionExecution(
                execution_type=action_type,
                status="failed",
                error_summary=str(exc)[:200],
            ),
        )
        await _store().update_action_status(action_id, status="failed", completed=True)
        await _audit(
            ae.DECISION_OPERATOR_ACTION_FAILED,
            f"operator action failed: {action_type}",
            "failed",
            ae.safe_operator_action_refs(action_type=action_type, status="failed"),
        )
        result["status"] = "failed"
        result["error"] = "action_execution_failed"


async def _apply_effect(action_type, target_id, reason, payload, ctx) -> str:
    """Concrete, reversible effects. Never triggers downstream/prod."""
    ps = _package_store()
    store = _store()
    if action_type == "operator_review.add_note":
        pkg = await ps.get_delivery_package(target_id) if target_id else None
        await store.add_review_note(
            OperatorReviewNote(
                package_id=target_id,
                project_id=(pkg or {}).get("project_id"),
                identity_key=ctx["identity_key"],
                note_type=payload.get("note_type", "general"),
                summary=reason,
            ),
            identity_id=ctx["identity_id"],
        )
        await _audit(
            ae.DECISION_OPERATOR_REVIEW_NOTE_ADDED,
            "review note added",
            "completed",
            ae.safe_operator_action_refs(target_id=target_id, identity_key=ctx["identity_key"]),
        )
        return "review_note_added"

    if action_type == "delivery_package.request_changes":
        await store.apply_delivery_decision(
            target_id,
            review_status="changes_requested",
            human_acceptance_status="pending",
            package_status="ready_for_review",
            summary=reason,
            requested_changes=payload.get("requested_changes", []),
        )
        await _notify(ev.EVENT_REVIEW_CHANGES_REQUESTED)
        await _audit(
            ae.DECISION_DELIVERY_PACKAGE_CHANGES_REQUESTED,
            "changes requested",
            "completed",
            ae.safe_operator_action_refs(target_id=target_id),
        )
        return "changes_requested"

    if action_type == "delivery_package.accept":
        await _assert_acceptable(target_id)
        await store.apply_delivery_decision(
            target_id,
            review_status="accepted",
            human_acceptance_status="accepted",
            package_status="accepted",
            summary=reason,
        )
        await _notify(ev.EVENT_REVIEW_ACCEPTED)
        await _audit(
            ae.DECISION_DELIVERY_PACKAGE_OPERATOR_ACCEPTED,
            "delivery package accepted (human review only)",
            "completed",
            ae.safe_operator_action_refs(target_id=target_id, identity_key=ctx["identity_key"]),
        )
        return "accepted"

    if action_type == "delivery_package.reject":
        await store.apply_delivery_decision(
            target_id,
            review_status="rejected",
            human_acceptance_status="rejected",
            package_status="rejected",
            summary=reason,
        )
        await _notify(ev.EVENT_REVIEW_REJECTED)
        await _audit(
            ae.DECISION_DELIVERY_PACKAGE_OPERATOR_REJECTED,
            "delivery package rejected",
            "completed",
            ae.safe_operator_action_refs(target_id=target_id),
        )
        return "rejected"

    raise ValueError(f"unsupported_effect:{action_type}")


async def _assert_acceptable(package_id: str) -> None:
    ps = _package_store()
    gate = await ps.get_acceptance_gate(package_id)
    pkg = await ps.get_delivery_package(package_id)
    if not pkg or pkg.get("status") != "ready_for_review":
        raise ValueError("package_not_ready_for_review")
    if not gate:
        raise ValueError("no_acceptance_gate")
    if gate.get("decision") not in ("ready_for_operator_review", "controlled_only_complete"):
        raise ValueError("gate_not_ready")
    if int(gate.get("blocking_findings_count") or 0) != 0:
        raise ValueError("blocking_findings_present")
    if int(gate.get("failed_checks") or 0) != 0:
        raise ValueError("failed_checks_present")


async def _notify(event_type: str) -> None:
    """Publish an operator-action notification. These namespaces are
    default-denied for real external delivery (sandbox only)."""
    with contextlib.suppress(Exception):
        from shared.sdk.event_bus.redis_streams import RedisStreamEventBus

        bus = RedisStreamEventBus()
        await bus.publish_event(
            ev.STREAM_OPERATOR_ACTIONS,
            {"event_type": event_type, "production_executed": False, "external_sent": False},
        )


@router.post("/operator-actions/{action_id}/confirmation")
async def issue_confirmation(action_id: str, request: Request) -> dict:
    try:
        ctx = await _authenticate(request)
        _require_csrf(request, ctx["session_hash"])
    except _AuthError as e:
        return {"http_status": e.status, **_err(e.status, e.reason)}
    action = await _store().get_action(action_id)
    if not action:
        return {"status": "not_found"}
    nonce = generate_nonce()
    await _store().create_confirmation(
        action_id,
        ctx["identity_id"],
        nonce_hash(nonce),
        datetime.fromtimestamp(expiry_ts(), tz=timezone.utc).isoformat(),
    )
    return {"status": "confirmation_issued", "action_id": action_id, "confirmation_nonce": nonce}


@router.post("/operator-actions/{action_id}/execute")
async def execute_action(action_id: str, request: Request, payload: dict | None = None) -> dict:
    try:
        ctx = await _authenticate(request)
        _require_csrf(request, ctx["session_hash"])
    except _AuthError as e:
        return {"http_status": e.status, **_err(e.status, e.reason)}
    action = await _store().get_action(action_id)
    if not action:
        return {"http_status": 404, "status": "not_found"}
    if action["status"] == "completed":
        return {
            "http_status": 200,
            "status": "completed",
            "idempotent_replay": True,
            "production_executed": False,
        }
    if action["status"] != "confirmation_required":
        return {"http_status": 409, "status": action["status"], "reason": "not_awaiting_execute"}

    conf = await _store().get_latest_confirmation(action_id)
    if not conf:
        return {"http_status": 403, **_err(403, "confirmation_missing")}
    provided = (payload or {}).get("confirmation_nonce", "")
    ok, why = confirmation_valid(
        provided_nonce=provided,
        stored_hash=conf["nonce_hash"],
        used=conf["used"],
        expires_ts=int(datetime.fromisoformat(conf["expires_at"]).timestamp()),
        same_identity=(conf["identity_key"] == ctx["identity_key"]),
    )
    if not ok:
        return {"http_status": 403, **_err(403, why)}
    await _store().mark_confirmation_used(conf["id"])
    await _store().update_action_status(
        action_id, status="approved", confirmation_status="confirmed"
    )
    await _audit(
        ae.DECISION_OPERATOR_ACTION_CONFIRMED,
        "operator action confirmed",
        "completed",
        ae.safe_operator_action_refs(action_type=action["action_type"]),
    )
    result = {
        "http_status": 200,
        "action_id": action_id,
        "action_type": action["action_type"],
        "status": "approved",
        "production_executed": False,
        "github_write_performed": False,
        "pr_created": False,
        "deployment_performed": False,
        "external_delivery_performed": False,
    }
    await _execute_action(
        action_id,
        ctx,
        action["action_type"],
        action.get("target_id"),
        action.get("reason", "confirmed"),
        {},
        result,
    )
    return result


# ===========================================================================
# Convenience delivery-package review endpoints
# ===========================================================================
async def _review_request(request, package_id, action_type, payload) -> dict:
    body = payload or {}
    return await _create_action(
        request,
        action_type=action_type,
        target_type="delivery_package",
        target_id=package_id,
        reason=body.get("reason", ""),
        payload=body,
        idempotency_key=request.headers.get("Idempotency-Key"),
    )


# ===========================================================================
# Verification rerun
# ===========================================================================
@router.post("/verifications/rerun")
async def verification_rerun(request: Request, payload: dict | None = None) -> dict:
    try:
        ctx = await _authenticate(request)
        _require_csrf(request, ctx["session_hash"])
    except _AuthError as e:
        return {"http_status": e.status, **_err(e.status, e.reason)}

    body = payload or {}
    script_key = body.get("script_key") or body.get("verification_key") or ""
    reason = body.get("reason", "")
    idem = request.headers.get("Idempotency-Key")
    if script_key not in ALLOWLISTED_SCRIPTS:
        return {"http_status": 403, **_err(403, "verification_not_allowlisted")}

    create = await _create_action(
        request,
        action_type="verification.rerun",
        target_type="verification",
        target_id=script_key,
        reason=reason,
        payload={"script_key": script_key},
        idempotency_key=idem,
    )
    # verification.rerun requires confirmation; full_regression requires a higher
    # confirmation level (must be explicitly acknowledged in the payload).
    if create.get("status") == "confirmation_required":
        if requires_higher_confirmation(script_key) and not body.get("high_risk_ack"):
            return {
                **create,
                "higher_confirmation_required": True,
                "reason_required": "full_regression requires high_risk_ack=true",
            }
        return create
    return create


@router.post("/verifications/{action_id}/run")
async def verification_run(action_id: str, request: Request, payload: dict | None = None) -> dict:
    """Execute a confirmed verification rerun action (after confirmation)."""
    try:
        ctx = await _authenticate(request)
        _require_csrf(request, ctx["session_hash"])
    except _AuthError as e:
        return {"http_status": e.status, **_err(e.status, e.reason)}
    action = await _store().get_action(action_id)
    if not action or action["action_type"] != "verification.rerun":
        return {"http_status": 404, "status": "not_found"}
    conf = await _store().get_latest_confirmation(action_id)
    if not conf:
        return {"http_status": 403, **_err(403, "confirmation_missing")}
    ok, why = confirmation_valid(
        provided_nonce=(payload or {}).get("confirmation_nonce", ""),
        stored_hash=conf["nonce_hash"],
        used=conf["used"],
        expires_ts=int(datetime.fromisoformat(conf["expires_at"]).timestamp()),
        same_identity=(conf["identity_key"] == ctx["identity_key"]),
    )
    if not ok:
        return {"http_status": 403, **_err(403, why)}
    await _store().mark_confirmation_used(conf["id"])
    script_key = action.get("target_id")
    await _audit(
        ae.DECISION_VERIFICATION_RERUN_STARTED,
        f"verification rerun: {script_key}",
        "started",
        ae.safe_operator_action_refs(verification_key=script_key),
    )
    await _store().update_action_status(action_id, status="executing")
    try:
        res = run_verification(script_key, verification_key=script_key)
    except VerificationNotAllowed:
        await _store().update_action_status(action_id, status="failed", completed=True)
        return {"http_status": 403, **_err(403, "verification_not_allowlisted")}
    rerun_id = await _store().create_rerun(
        action_id,
        VerificationRerunRequest(
            verification_key=res.verification_key,
            script_key=res.script_key,
            status=res.status,
            report_path=res.report_path,
            result_marker=res.result_marker,
            exit_code=res.exit_code,
        ),
    )
    await _store().create_execution(
        action_id,
        OperatorActionExecution(
            execution_type="verification.rerun",
            status=res.status,
            result_summary=res.result_marker or res.status,
            production_executed=False,
        ),
    )
    await _store().update_action_status(action_id, status="completed", completed=True)
    decision = (
        ae.DECISION_VERIFICATION_RERUN_COMPLETED
        if res.status == "completed"
        else ae.DECISION_VERIFICATION_RERUN_FAILED
    )
    await _audit(
        decision,
        f"verification rerun {res.status}: {script_key}",
        res.status,
        ae.safe_operator_action_refs(verification_key=script_key, result_marker=res.result_marker),
    )
    await _notify(ev.EVENT_RERUN_COMPLETED if res.status == "completed" else ev.EVENT_RERUN_FAILED)
    return {
        "http_status": 200,
        "action_id": action_id,
        "rerun_id": rerun_id,
        "status": res.status,
        "result_marker": res.result_marker,
        "exit_code": res.exit_code,
        "production_executed": False,
    }


@router.get("/verifications/reruns")
async def list_reruns(limit: int = 50) -> dict:
    return {"reruns": await _store().list_reruns(limit=limit)}


@router.get("/verifications/reruns/{rerun_id}")
async def get_rerun(rerun_id: str) -> dict:
    r = await _store().get_rerun(rerun_id)
    return r or {"status": "not_found"}


__all__ = ["router", "_create_action", "_review_request"]
