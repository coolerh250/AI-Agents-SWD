"""Step 61 (Stage 63A) -- backup / restore / DR operations API.

Read endpoints are GET-only + redacted (overview / policy / targets / artifacts / inventory
/ cleanup-review / restore-plans / restore-validations / evidence / readiness / safety /
limitations). The write endpoints (create cleanup review, create restore plan) reuse the
operator auth + CSRF + audit and require a reason. They NEVER execute a cleanup, NEVER
execute a restore, NEVER fail over, NEVER tear down kind / ArgoCD, and NEVER upload to an
external / cloud store: a production target is blocked, an arbitrary path is rejected, and
production_restore / production_failover / production_executed are always false. There is
intentionally NO cleanup-execute / restore-execute / failover / teardown / ArgoCD-sync /
cloud-upload endpoint. No token is ever returned.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from operator_actions_api import _AuthError, _audit, _authenticate, _require_csrf

from shared.sdk.backup_restore_dr import (
    BackupRestoreDrStore,
    CleanupReviewError,
    RestorePlanError,
    backup_restore_dr_safety_fields,
    build_audit_metadata,
    build_cleanup_review,
    build_recovery_evidence,
    build_restore_plan,
    evaluate_readiness,
    load_classes,
    load_targets,
)
from shared.sdk.backup_restore_dr import policy as _policy

router = APIRouter(prefix="/operations/dr", tags=["backup-restore-dr"])

_store = BackupRestoreDrStore()


def _err(status: int, reason: str) -> dict:
    return {
        "status": "policy_blocked" if status == 403 else "error",
        "reason": reason,
        "production_restore": False,
        "production_failover": False,
        "production_executed": False,
        "cleanup_executed": False,
        "restore_executed": False,
    }


# ---------------------------------------------------------------------------
# Read endpoints (GET-only, redacted, no secret)
# ---------------------------------------------------------------------------
@router.get("/overview")
async def overview() -> dict:
    counts: dict = {
        "production_restore_plan_count": 0,
        "production_failover_plan_count": 0,
        "production_restore_executed_count": 0,
        "production_failover_executed_count": 0,
    }
    reviews: list = []
    plans: list = []
    try:
        counts = await _store.counts()
        reviews = await _store.list_cleanup_reviews()
        plans = await _store.list_restore_plans()
    except Exception:  # noqa: BLE001 -- DB unavailable -> empty/zero, never faked ready
        pass
    return {
        "production_ready": False,
        "production_restore_ready": False,
        "cleanup_review_count": len(reviews),
        "restore_plan_count": len(plans),
        "backup_target_count": len(load_targets()),
        **counts,
    }


@router.get("/policy")
async def get_policy() -> dict:
    p = _policy.load_policy()
    return {
        "production_ready": False,
        "enabled": bool(p.get("enabled", False)),
        "allow_production_restore": bool(p.get("allowProductionRestore", False)),
        "allow_production_failover": bool(p.get("allowProductionFailover", False)),
        "allow_production_backup_mutation": bool(p.get("allowProductionBackupMutation", False)),
        "allow_external_backup_upload": bool(p.get("allowExternalBackupUpload", False)),
        "allow_cloud_provider_write": bool(p.get("allowCloudProviderWrite", False)),
        "allow_argocd_production_sync": bool(p.get("allowArgoCDProductionSync", False)),
        "allow_kubernetes_production_mutation": bool(
            p.get("allowKubernetesProductionMutation", False)
        ),
        "allow_cleanup_execution": bool(p.get("allowCleanupExecution", False)),
        "allow_restore_execution": bool(p.get("allowRestoreExecution", False)),
        "allow_kind_teardown": bool(p.get("allowKindTeardown", False)),
        "allow_argocd_teardown": bool(p.get("allowArgoCDTeardown", False)),
        "require_inventory_before_cleanup": bool(p.get("requireInventoryBeforeCleanup", True)),
        "require_restore_validation": bool(p.get("requireRestoreValidation", True)),
        "require_human_approval_for_production_restore": bool(
            p.get("requireHumanApprovalForProductionRestore", True)
        ),
        "allowed_environments": p.get("allowedEnvironments", []),
        "forbidden_environments": p.get("forbiddenEnvironments", []),
    }


@router.get("/targets")
async def get_targets() -> dict:
    return {"production_ready": False, "targets": load_targets()}


@router.get("/artifacts")
async def get_artifacts() -> dict:
    return {"production_ready": False, "artifact_classes": load_classes()}


@router.get("/inventory")
async def get_inventory() -> dict:
    return {
        "production_ready": False,
        "targets": load_targets(),
        "artifact_classes": load_classes(),
    }


@router.get("/safety")
async def get_safety() -> dict:
    counts: dict = {}
    try:
        counts = await _store.counts()
    except Exception:  # noqa: BLE001
        counts = {}
    return {"production_ready": False, **backup_restore_dr_safety_fields(**counts)}


@router.get("/limitations")
async def get_limitations() -> dict:
    return {
        "production_ready": False,
        "production_restore_ready": False,
        "limitations": [
            "non-production backup / restore / DR governance baseline only",
            "no production restore / production failover / production data mutation",
            "no cleanup execution / restore execution (review + plan + validate only)",
            "no kind / ArgoCD teardown; no ArgoCD sync; no external / cloud upload",
            "DR readiness is a governance judgement, NOT production DR ready",
            "Claude Code does not decide production readiness",
        ],
    }


@router.get("/cleanup-review")
async def list_cleanup_review() -> dict:
    try:
        rows = await _store.list_cleanup_reviews()
    except Exception:  # noqa: BLE001
        return {"production_ready": False, "available": False, "cleanup_reviews": []}
    return {"production_ready": False, "cleanup_executed": False, "cleanup_reviews": rows}


@router.get("/cleanup")
async def cleanup_alias() -> dict:
    return await list_cleanup_review()


@router.get("/restore-plans")
async def list_restore_plans() -> dict:
    try:
        rows = await _store.list_restore_plans()
    except Exception:  # noqa: BLE001
        return {"production_ready": False, "available": False, "restore_plans": []}
    return {"production_ready": False, "restore_executed": False, "restore_plans": rows}


@router.get("/restore")
async def restore_alias() -> dict:
    return await list_restore_plans()


@router.get("/restore-validations")
async def list_restore_validations() -> dict:
    try:
        rows = await _store.list_restore_validations()
    except Exception:  # noqa: BLE001
        return {"production_ready": False, "available": False, "restore_validations": []}
    return {"production_ready": False, "restore_validations": rows}


@router.get("/evidence")
async def get_evidence() -> dict:
    plans: list = []
    validations: list = []
    try:
        plans = await _store.list_restore_plans()
        validations = await _store.list_restore_validations()
    except Exception:  # noqa: BLE001
        pass
    evidence = {
        "backup_inventory": load_targets(),
        "backup_target_classification": load_classes(),
        "restore_plan": plans or None,
        "restore_validation_result": validations or None,
    }
    return build_recovery_evidence(evidence)


@router.get("/readiness")
async def get_readiness() -> dict:
    plans: list = []
    validations: list = []
    try:
        plans = await _store.list_restore_plans()
        validations = await _store.list_restore_validations()
    except Exception:  # noqa: BLE001
        pass
    evidence = {
        "backup_inventory": load_targets(),
        "backup_target_classification": load_classes(),
        "restore_plan": plans or None,
        "restore_validation_result": validations or None,
    }
    result = evaluate_readiness(target_environment="nonprod", evidence=evidence)
    return result.to_dict()


# ---------------------------------------------------------------------------
# Write endpoints (auth + CSRF + reason + audit) -- review / plan only, no execution
# ---------------------------------------------------------------------------
@router.post("/cleanup-reviews")
async def create_cleanup_review(request: Request) -> dict:
    try:
        ctx = await _authenticate(request)
        _require_csrf(request, ctx["session_hash"])
    except _AuthError as e:
        return _err(e.status, e.reason)
    body = await request.json()
    reason = (body.get("reason") or "").strip()
    if not reason:
        return _err(400, "reason_required")
    scope = (body.get("scope") or "").strip()
    if not scope:
        return _err(400, "scope_required")
    candidates = body.get("candidates") or []

    try:
        review = build_cleanup_review(scope=scope, candidates=candidates)
    except CleanupReviewError as exc:
        await _audit(
            "backup_dr_cleanup_review",
            f"cleanup review blocked ({exc.reason})",
            "blocked",
            build_audit_metadata(
                event_type="cleanup_execution_blocked",
                actor=ctx["identity_key"],
                role=ctx["role"],
                reason=reason,
                target=scope,
                policy_decision="blocked",
                extra={"blocked_reason": exc.reason},
            ),
        )
        return _err(403, exc.reason)

    record = None
    try:
        record = await _store.create_cleanup_review(
            review_id=review.cleanup_review_id,
            scope=review.scope,
            candidates=review.candidates,
            allowed_count=review.allowed_count,
            blocked_count=review.blocked_count,
            requires_approval_count=review.requires_approval_count,
            risk_level=review.risk_level,
        )
    except Exception:  # noqa: BLE001
        record = None

    await _audit(
        "backup_dr_cleanup_review",
        f"cleanup review {review.scope} (risk {review.risk_level})",
        "created",
        build_audit_metadata(
            event_type="cleanup_review_created",
            actor=ctx["identity_key"],
            role=ctx["role"],
            reason=reason,
            operation_id=review.cleanup_review_id,
            target=review.scope,
            policy_decision="reviewed_no_execution",
        ),
    )
    out = review.to_dict()
    out["status"] = "created"
    out["persisted"] = record is not None
    out["cleanup_executed"] = False
    return out


@router.post("/restore-plans")
async def create_restore_plan(request: Request) -> dict:
    try:
        ctx = await _authenticate(request)
        _require_csrf(request, ctx["session_hash"])
    except _AuthError as e:
        return _err(e.status, e.reason)
    body = await request.json()
    reason = (body.get("reason") or "").strip()
    if not reason:
        return _err(400, "reason_required")
    target = (body.get("target") or "").strip()
    if not target:
        return _err(400, "target_required")
    restore_type = (body.get("restore_type") or "").strip()
    if not restore_type:
        return _err(400, "restore_type_required")

    try:
        plan = build_restore_plan(
            target=target,
            restore_type=restore_type,
            target_environment=body.get("target_environment"),
            source_artifact=(body.get("source_artifact") or "").strip() or None,
        )
    except RestorePlanError as exc:
        return _err(403, exc.reason)

    record = None
    try:
        record = await _store.create_restore_plan(
            plan_id=plan.restore_plan_id,
            target=plan.target,
            source_artifact=plan.source_artifact,
            target_environment=plan.target_environment,
            restore_type=plan.restore_type,
            status=plan.status,
            policy_decision=plan.policy_decision,
            requires_human_approval=plan.requires_human_approval,
            blocked_reason=plan.blocked_reason,
        )
    except Exception:  # noqa: BLE001 -- e.g. a blocked production-target plan fails the
        # CHECK constraint; that is correct (production never persists). Report blocked.
        record = None

    event = "production_restore_blocked" if plan.status == "blocked" else "restore_plan_created"
    await _audit(
        "backup_dr_restore_plan",
        f"restore plan {plan.restore_type} {plan.status} ({plan.target_environment})",
        plan.status,
        build_audit_metadata(
            event_type=event,
            actor=ctx["identity_key"],
            role=ctx["role"],
            reason=reason,
            operation_id=plan.restore_plan_id,
            target=plan.target,
            target_environment=plan.target_environment,
            policy_decision=plan.policy_decision,
            extra={"blocked_reason": plan.blocked_reason},
        ),
    )
    out = plan.to_dict()
    out["persisted"] = record is not None
    return out


__all__ = ["router"]
