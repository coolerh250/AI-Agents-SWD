"""Step 62 (Stage 64A) -- production deployment readiness gate API.

Read endpoints are GET-only + redacted (overview / policy / checklist / evidence /
blocking-rules / blockers / prerequisites / authorization / operator-review-package /
decision / preflight / report / safety / limitations). The single write endpoint creates an
operator review REQUEST (operator auth + CSRF + reason + audit) -- it is NOT a production
approval and authorizes NO production action. There is intentionally NO deploy / sync /
approval / release / restore / failover / merge / image-push endpoint. production_ready /
production_approved / production_action_allowed are always false; no token is ever returned.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from operator_actions_api import _AuthError, _audit, _authenticate, _require_csrf

from shared.sdk.production_readiness import (
    ProductionReadinessStore,
    authorization,
    blocking_rules,
    build_audit_metadata,
    build_operator_review_package,
    checklist,
    decision,
    evidence,
    policy,
    preflight,
    prerequisites,
    production_readiness_safety_fields,
)

router = APIRouter(prefix="/operations/readiness", tags=["production-readiness"])

_store = ProductionReadinessStore()


def _err(status: int, reason: str) -> dict:
    return {
        "status": "policy_blocked" if status == 403 else "error",
        "reason": reason,
        "production_ready": False,
        "production_approved": False,
        "production_action_allowed": False,
        "production_executed": False,
    }


def _decision() -> dict:
    results = blocking_rules.evaluate()
    missing = prerequisites.missing_prerequisites()
    return decision.evaluate(
        blocking_results=results, missing_evidence=[], missing_prerequisites=missing
    ).to_dict()


# ---------------------------------------------------------------------------
# Read endpoints (GET-only, redacted, no secret)
# ---------------------------------------------------------------------------
@router.get("/overview")
async def overview() -> dict:
    results = blocking_rules.evaluate()
    return {
        "production_ready": False,
        "production_approved": False,
        "production_action_allowed": False,
        "decision": _decision()["decision"],
        "blocker_count": sum(1 for r in results if r.active),
        "missing_prerequisite_count": len(prerequisites.missing_prerequisites()),
        "checklist_category_count": len(checklist.load_categories()),
    }


@router.get("/policy")
async def get_policy() -> dict:
    p = policy.load_policy()
    return {
        "production_ready": False,
        "enabled": bool(p.get("enabled", False)),
        "allow_production_deploy": bool(p.get("allowProductionDeploy", False)),
        "allow_production_sync": bool(p.get("allowProductionSync", False)),
        "allow_production_restore": bool(p.get("allowProductionRestore", False)),
        "allow_production_failover": bool(p.get("allowProductionFailover", False)),
        "allow_auto_promotion": bool(p.get("allowAutoPromotion", False)),
        "allow_github_merge": bool(p.get("allowGitHubMerge", False)),
        "allow_image_push": bool(p.get("allowImagePush", False)),
        "allow_registry_login": bool(p.get("allowRegistryLogin", False)),
        "require_human_approval_before_production": bool(
            p.get("requireHumanApprovalBeforeProduction", True)
        ),
        "require_explicit_production_rollout_phase": bool(
            p.get("requireExplicitProductionRolloutPhase", True)
        ),
        "current_stage_allows_production_action": bool(
            p.get("currentStageAllowsProductionAction", False)
        ),
    }


@router.get("/checklist")
async def get_checklist() -> dict:
    return {"production_ready": False, "categories": checklist.load_categories()}


@router.get("/evidence")
async def get_evidence() -> dict:
    return {"production_ready": False, "evidence": evidence.load_evidence()}


@router.get("/blocking-rules")
async def get_blocking_rules() -> dict:
    return {
        "production_ready": False,
        "blocking_rules": [r.to_dict() for r in blocking_rules.evaluate()],
    }


@router.get("/blockers")
async def get_blockers() -> dict:
    active = [r.to_dict() for r in blocking_rules.evaluate() if r.active]
    return {"production_ready": False, "active_blockers": active, "count": len(active)}


@router.get("/prerequisites")
async def get_prerequisites() -> dict:
    return {
        "production_ready": False,
        "production_environment_exists": prerequisites.production_environment_exists(),
        "prerequisites": prerequisites.load_prerequisites(),
        "missing": prerequisites.missing_prerequisites(),
    }


@router.get("/authorization")
async def get_authorization() -> dict:
    return {
        "production_ready": False,
        "may_authorize": authorization.may_authorize(),
        "may_not_authorize": authorization.may_not_authorize(),
        "operator_review_is_approval": authorization.operator_review_is_approval(),
    }


@router.get("/operator-review-package")
async def get_operator_review_package() -> dict:
    dec = _decision()
    return build_operator_review_package(
        readiness_decision=dec,
        evidence_inventory=evidence.load_evidence(),
        blocking_results=[r.to_dict() for r in blocking_rules.evaluate()],
        missing_prerequisites=prerequisites.missing_prerequisites(),
        known_limitations=[],
    )


@router.get("/decision")
async def get_decision() -> dict:
    return _decision()


@router.get("/preflight")
async def get_preflight() -> dict:
    return {
        "production_ready": False,
        "rollout_status": preflight.rollout_status(),
        "rollout_execution_enabled": preflight.rollout_execution_enabled(),
        "checks": preflight.load_checks(),
    }


@router.get("/report")
async def get_report() -> dict:
    return {
        "production_ready": False,
        "production_approval": False,
        "production_action_allowed": False,
        "decision": _decision(),
        "blocking_rules": [r.to_dict() for r in blocking_rules.evaluate()],
        "missing_prerequisites": prerequisites.missing_prerequisites(),
        "rollout_status": preflight.rollout_status(),
    }


@router.get("/safety")
async def get_safety() -> dict:
    counts: dict = {}
    try:
        counts = await _store.counts()
    except Exception:  # noqa: BLE001
        counts = {}
    return {"production_ready": False, **production_readiness_safety_fields(**counts)}


@router.get("/limitations")
async def get_limitations() -> dict:
    return {
        "production_ready": False,
        "production_approval": False,
        "limitations": [
            "non-production readiness gate only; NOT production deployment / approval / rollout",
            "production environment + prerequisites not configured",
            "runtime + GitOps evidence is non-production only",
            "operator review request is NOT a production approval",
            "readiness decision is NOT a production approval; max is ready_for_operator_review",
            "Claude Code does not decide production readiness",
        ],
    }


# ---------------------------------------------------------------------------
# Write endpoint (auth + CSRF + reason + audit) -- operator review request only
# ---------------------------------------------------------------------------
@router.post("/operator-review-requests")
async def create_operator_review_request(request: Request) -> dict:
    try:
        ctx = await _authenticate(request)
        _require_csrf(request, ctx["session_hash"])
    except _AuthError as e:
        return _err(e.status, e.reason)
    body = await request.json()
    reason = (body.get("reason") or "").strip()
    if not reason:
        return _err(400, "reason_required")

    dec = _decision()
    request_id = uuid.uuid4().hex

    record = None
    try:
        record = await _store.create_operator_review_request(
            request_id=request_id,
            decision_status=dec["decision"],
            summary={"decision": dec["decision"], "production_ready": False},
        )
    except Exception:  # noqa: BLE001
        record = None

    await _audit(
        "production_readiness_operator_review",
        f"operator review requested (decision {dec['decision']})",
        "operator_review_requested",
        build_audit_metadata(
            event_type="operator_review_requested",
            actor=ctx["identity_key"],
            role=ctx["role"],
            reason=reason,
            readiness_gate_id=request_id,
            decision_status=dec["decision"],
        ),
    )
    return {
        "status": "operator_review_requested",
        "request_id": request_id,
        "decision": dec["decision"],
        "persisted": record is not None,
        "production_ready": False,
        "production_approved": False,
        "production_action_allowed": False,
        "is_production_approval": False,
    }


__all__ = ["router"]
