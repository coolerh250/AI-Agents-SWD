"""Step 63A (Stage 65A) -- controlled production rollout pilot go/no-go REVIEW API.

Read endpoints are GET-only + redacted (policy / criteria / production-target / credentials
/ gitops / approval-channel / rollback-dr / scope / risks / decision-package /
recommendation / safety). The single write endpoint creates an operator review REQUEST
(operator auth + CSRF + reason + audit) -- it is NOT a production approval, does not change
the recommendation, and authorizes NO production action. There is intentionally NO rollout /
deploy / sync / approval / release / restore / failover / merge / image-push endpoint. A Go
/ Conditional Go recommendation is not an approval; no token is ever returned.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request

from operator_actions_api import _AuthError, _audit, _authenticate, _require_csrf

from shared.sdk.controlled_rollout import (
    build_audit_metadata,
    build_operator_decision_package,
    controlled_rollout_safety_fields,
    loaders,
    recommendation,
)
from shared.sdk.production_readiness import ProductionReadinessStore

router = APIRouter(
    prefix="/operations/readiness/controlled-rollout", tags=["controlled-rollout-review"]
)

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


# ---------------------------------------------------------------------------
# Read endpoints (GET-only, redacted, no secret)
# ---------------------------------------------------------------------------
@router.get("/policy")
async def get_policy() -> dict:
    p = loaders.load("policy")
    return {
        "production_ready": False,
        "enabled": bool(p.get("enabled", False)),
        "allows_production_action": bool(p.get("allowsProductionAction", False)),
        "allows_production_deploy": bool(p.get("allowsProductionDeploy", False)),
        "allows_production_sync": bool(p.get("allowsProductionSync", False)),
        "allows_production_restore": bool(p.get("allowsProductionRestore", False)),
        "allows_production_failover": bool(p.get("allowsProductionFailover", False)),
        "operator_review_is_approval": bool(p.get("operatorReviewIsApproval", False)),
        "go_recommendation_is_approval": bool(p.get("goRecommendationIsApproval", False)),
        "conditional_go_is_approval": bool(p.get("conditionalGoIsApproval", False)),
        "requires_explicit_operator_approval_for_pilot": bool(
            p.get("requiresExplicitOperatorApprovalForPilot", True)
        ),
        "requires_separate_pilot_execution_stage": bool(
            p.get("requiresSeparatePilotExecutionStage", True)
        ),
    }


@router.get("/criteria")
async def get_criteria() -> dict:
    c = loaders.load("criteria")
    return {
        "production_ready": False,
        "outcomes": c.get("outcomes", []),
        "criteria": c.get("criteria", []),
    }


@router.get("/production-target")
async def get_production_target() -> dict:
    return {
        "production_ready": False,
        **loaders.load("target"),
        "missing": loaders.missing_target_items(),
    }


@router.get("/credentials")
async def get_credentials() -> dict:
    return {
        "production_ready": False,
        **loaders.load("credentials"),
        "missing": loaders.missing_credential_refs(),
    }


@router.get("/gitops")
async def get_gitops() -> dict:
    return {
        "production_ready": False,
        **loaders.load("gitops"),
        "missing": loaders.missing_gitops_items(),
    }


@router.get("/approval-channel")
async def get_approval_channel() -> dict:
    return {
        "production_ready": False,
        **loaders.load("approval_channel"),
        "missing": loaders.missing_approval_items(),
    }


@router.get("/rollback-dr")
async def get_rollback_dr() -> dict:
    return {"production_ready": False, **loaders.load("rollback_dr")}


@router.get("/scope")
async def get_scope() -> dict:
    return {"production_ready": False, **loaders.load("scope")}


@router.get("/risks")
async def get_risks() -> dict:
    return {"production_ready": False, "risks": loaders.load("risk_register").get("risks", [])}


@router.get("/decision-package")
async def get_decision_package() -> dict:
    return build_operator_decision_package()


@router.get("/recommendation")
async def get_recommendation() -> dict:
    return {"production_ready": False, **recommendation.evaluate()}


@router.get("/safety")
async def get_safety() -> dict:
    return {"production_ready": False, **controlled_rollout_safety_fields()}


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

    rec = recommendation.evaluate()
    request_id = uuid.uuid4().hex

    record = None
    try:
        record = await _store.create_operator_review_request(
            request_id=request_id,
            decision_status=f"controlled_rollout:{rec['recommendation']}",
            summary={"recommendation": rec["recommendation"], "production_ready": False},
        )
    except Exception:  # noqa: BLE001
        record = None

    await _audit(
        "controlled_rollout_operator_review",
        f"controlled rollout operator review requested (recommendation {rec['recommendation']})",
        "operator_review_requested",
        build_audit_metadata(
            event_type="controlled_rollout_operator_review_requested",
            actor=ctx["identity_key"],
            role=ctx["role"],
            reason=reason,
            review_id=request_id,
            recommendation=rec["recommendation"],
        ),
    )
    return {
        "status": "operator_review_requested",
        "request_id": request_id,
        "recommendation": rec["recommendation"],
        "persisted": record is not None,
        "production_ready": False,
        "production_approved": False,
        "production_action_allowed": False,
        "is_production_approval": False,
        "recommendation_is_approval": False,
    }


__all__ = ["router"]
