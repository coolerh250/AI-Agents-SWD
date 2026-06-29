"""Step 60 (Stage 62A) -- release & deployment governance API.

Read endpoints are GET-only + redacted (overview / policy / candidates / intents /
evidence / readiness / safety / limitations). The write endpoints (create candidate,
create deployment intent) reuse the operator auth + CSRF + audit and require a reason.
They NEVER deploy, sync, merge, push, or release: a production target is blocked, the
only intent actions are validate-only / prepare-nonproduction / request-operator-review,
and production_ready / production_executed are always false. No token is ever returned.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from operator_actions_api import _AuthError, _audit, _authenticate, _require_csrf

from shared.sdk.projects import ProjectStore
from shared.sdk.release_governance import (
    CandidateError,
    ReleaseGovernanceStore,
    build_audit_metadata,
    build_candidate,
    build_evidence_summary,
    build_intent,
    evaluate,
    release_governance_safety_fields,
)
from shared.sdk.release_governance import policy as _policy

router = APIRouter(prefix="/operations/release", tags=["release-governance"])

_projects = ProjectStore()
_store = ReleaseGovernanceStore()


def _err(status: int, reason: str) -> dict:
    return {
        "status": "policy_blocked" if status == 403 else "error",
        "reason": reason,
        "production_executed": False,
        "deploy_performed": False,
        "argocd_sync_performed": False,
        "merge_performed": False,
        "image_push_performed": False,
    }


# ---------------------------------------------------------------------------
# Read endpoints (GET-only, redacted, no secret)
# ---------------------------------------------------------------------------
@router.get("/overview")
async def overview() -> dict:
    counts = {
        "release_candidate_production_ready_count": 0,
        "deployment_intent_production_target_count": 0,
        "deployment_intent_production_executed_count": 0,
    }
    candidates: list = []
    intents: list = []
    try:
        counts = await _store.counts()
        candidates = await _store.list_candidates()
        intents = await _store.list_intents()
    except Exception:  # noqa: BLE001 -- DB unavailable -> empty/zero, never faked healthy
        pass
    return {
        "production_ready": False,
        "release_candidate_count": len(candidates),
        "deployment_intent_count": len(intents),
        **counts,
    }


@router.get("/policy")
async def get_policy() -> dict:
    p = _policy.load_policy()
    return {
        "production_ready": False,
        "enabled": bool(p.get("enabled", False)),
        "allow_production_deploy": bool(p.get("allowProductionDeploy", False)),
        "allow_auto_promotion": bool(p.get("allowAutoPromotion", False)),
        "allow_github_merge": bool(p.get("allowGitHubMerge", False)),
        "allow_tag_creation": bool(p.get("allowTagCreation", False)),
        "allow_release_creation": bool(p.get("allowReleaseCreation", False)),
        "allow_image_push": bool(p.get("allowImagePush", False)),
        "allow_registry_login": bool(p.get("allowRegistryLogin", False)),
        "allow_argocd_production_sync": bool(p.get("allowArgoCDProductionSync", False)),
        "require_human_approval_for_production": bool(
            p.get("requireHumanApprovalForProduction", True)
        ),
        "default_environment": p.get("defaultEnvironment"),
        "allowed_environments": p.get("allowedEnvironments", []),
        "forbidden_environments": p.get("forbiddenEnvironments", []),
    }


@router.get("/safety")
async def get_safety() -> dict:
    counts: dict = {}
    try:
        counts = await _store.counts()
    except Exception:  # noqa: BLE001
        counts = {}
    return {"production_ready": False, **release_governance_safety_fields(**counts)}


@router.get("/limitations")
async def get_limitations() -> dict:
    return {
        "production_ready": False,
        "limitations": [
            "non-production governance baseline only",
            "no production deploy / ArgoCD production sync / GitHub merge / image push",
            "release candidate accepted_nonproduction is NOT a production approval",
            "deployment intent never executes a deployment",
            "human review request is NOT human approval",
            "Claude Code does not decide production readiness",
        ],
    }


@router.get("/candidates")
async def list_candidates() -> dict:
    try:
        rows = await _store.list_candidates()
    except Exception:  # noqa: BLE001
        return {"production_ready": False, "available": False, "candidates": []}
    return {"production_ready": False, "candidates": rows}


@router.get("/candidates/{candidate_id}")
async def get_candidate(candidate_id: str) -> dict:
    try:
        rec = await _store.get_candidate(candidate_id)
    except Exception:  # noqa: BLE001
        return {"status": "unavailable"}
    return rec or {"status": "not_found"}


@router.get("/candidates/{candidate_id}/evidence")
async def candidate_evidence(candidate_id: str) -> dict:
    rec = None
    try:
        rec = await _store.get_candidate(candidate_id)
    except Exception:  # noqa: BLE001
        rec = None
    if not rec:
        return {"status": "not_found"}
    evidence = {
        "work_item_state": rec.get("work_item_ids"),
        "delivery_package": rec.get("delivery_package_ids"),
        "sandbox_draft_pr_plan_or_result": rec.get("sandbox_draft_pr_ids"),
    }
    return {"candidate_id": candidate_id, **build_evidence_summary(evidence)}


@router.get("/candidates/{candidate_id}/readiness")
async def candidate_readiness(candidate_id: str) -> dict:
    rec = None
    try:
        rec = await _store.get_candidate(candidate_id)
    except Exception:  # noqa: BLE001
        rec = None
    if not rec:
        return {"status": "not_found"}
    result = evaluate(
        target_environment=rec.get("target_environment"),
        evidence={},
        security_status=rec.get("security_status", "unknown"),
        runtime_status=rec.get("runtime_status", "unknown"),
        gitops_status=rec.get("gitops_status", "unknown"),
        sandbox_pr_reviewed=False,
    )
    return {"candidate_id": candidate_id, **result.to_dict()}


@router.get("/readiness-summary")
async def readiness_summary() -> dict:
    candidates: list = []
    try:
        candidates = await _store.list_candidates()
    except Exception:  # noqa: BLE001
        candidates = []
    return {
        "production_ready": False,
        "total": len(candidates),
        "by_status": _by(candidates, "readiness_status"),
    }


@router.get("/deployment-intents")
async def list_intents() -> dict:
    try:
        rows = await _store.list_intents()
    except Exception:  # noqa: BLE001
        return {"production_ready": False, "available": False, "deployment_intents": []}
    return {"production_ready": False, "deployment_intents": rows}


@router.get("/deployment-intents/{intent_id}")
async def get_intent(intent_id: str) -> dict:
    try:
        rec = await _store.get_intent(intent_id)
    except Exception:  # noqa: BLE001
        return {"status": "unavailable"}
    return rec or {"status": "not_found"}


def _by(rows: list, key: str) -> dict:
    out: dict[str, int] = {}
    for r in rows:
        out[r.get(key, "unknown")] = out.get(r.get(key, "unknown"), 0) + 1
    return out


# ---------------------------------------------------------------------------
# Write endpoints (auth + CSRF + reason + audit) -- governance only, no deploy
# ---------------------------------------------------------------------------
@router.post("/candidates")
async def create_candidate(request: Request) -> dict:
    try:
        ctx = await _authenticate(request)
        _require_csrf(request, ctx["session_hash"])
    except _AuthError as e:
        return _err(e.status, e.reason)
    body = await request.json()
    reason = (body.get("reason") or "").strip()
    if not reason:
        return _err(400, "reason_required")
    version_label = (body.get("version_label") or "").strip()
    if not version_label:
        return _err(400, "version_label_required")
    project_id = (body.get("project_id") or "").strip() or None
    if project_id and not await _projects.get_project(project_id):
        return _err(404, "project_not_found")

    try:
        cand = build_candidate(
            project_id=project_id,
            version_label=version_label,
            target_environment=body.get("target_environment"),
            work_item_ids=body.get("work_item_ids") or [],
            delivery_package_ids=body.get("delivery_package_ids") or [],
            sandbox_draft_pr_ids=body.get("sandbox_draft_pr_ids") or [],
        )
    except CandidateError as exc:
        return _err(403, exc.reason)

    record = None
    try:
        record = await _store.create_candidate(
            candidate_id=cand.release_candidate_id,
            project_id=cand.project_id,
            version_label=cand.version_label,
            target_environment=cand.target_environment,
            work_item_ids=cand.work_item_ids,
            delivery_package_ids=cand.delivery_package_ids,
            sandbox_draft_pr_ids=cand.sandbox_draft_pr_ids,
            status=cand.status,
            readiness_status=cand.readiness_status,
        )
    except Exception:  # noqa: BLE001
        record = None

    await _audit(
        "release_candidate_create",
        f"release candidate {cand.version_label} created ({cand.target_environment})",
        "created",
        build_audit_metadata(
            event_type="release_candidate_created",
            actor=ctx["identity_key"],
            role=ctx["role"],
            reason=reason,
            project_id=project_id,
            candidate_id=cand.release_candidate_id,
            target_environment=cand.target_environment,
            policy_decision="created_nonproduction",
        ),
    )
    out = cand.to_dict()
    out["status"] = "created"
    out["persisted"] = record is not None
    out["production_executed"] = False
    return out


@router.post("/candidates/{candidate_id}/deployment-intents")
async def create_deployment_intent(candidate_id: str, request: Request) -> dict:
    try:
        ctx = await _authenticate(request)
        _require_csrf(request, ctx["session_hash"])
    except _AuthError as e:
        return _err(e.status, e.reason)
    body = await request.json()
    reason = (body.get("reason") or "").strip()
    if not reason:
        return _err(400, "reason_required")
    requested_action = (body.get("requested_action") or "").strip()
    if not requested_action:
        return _err(400, "requested_action_required")

    cand = None
    try:
        cand = await _store.get_candidate(candidate_id)
    except Exception:  # noqa: BLE001
        cand = None
    if not cand:
        return _err(404, "release_candidate_not_found")

    intent = build_intent(
        release_candidate_id=candidate_id,
        requested_action=requested_action,
        target_environment=body.get("target_environment"),
        target_runtime=body.get("target_runtime"),
        target_gitops_application=body.get("target_gitops_application"),
    )

    record = None
    try:
        record = await _store.create_intent(
            intent_id=intent.deployment_intent_id,
            candidate_id=candidate_id,
            target_environment=intent.target_environment,
            requested_action=intent.requested_action,
            status=intent.status,
            policy_decision=intent.policy_decision,
            requires_human_approval=intent.requires_human_approval,
            blocked_reason=intent.blocked_reason,
        )
    except Exception:  # noqa: BLE001 -- e.g. a blocked production-target intent fails the
        # CHECK constraint; that is correct (production never persists). Report blocked.
        record = None

    event = (
        "deployment_intent_blocked" if intent.status == "blocked" else "deployment_intent_created"
    )
    await _audit(
        "release_deployment_intent",
        f"deployment intent {intent.requested_action} {intent.status} ({intent.target_environment})",
        intent.status,
        build_audit_metadata(
            event_type=event,
            actor=ctx["identity_key"],
            role=ctx["role"],
            reason=reason,
            candidate_id=candidate_id,
            deployment_intent_id=intent.deployment_intent_id,
            target_environment=intent.target_environment,
            policy_decision=intent.policy_decision,
            extra={"blocked_reason": intent.blocked_reason},
        ),
    )
    out = intent.to_dict()
    out["persisted"] = record is not None
    return out


__all__ = ["router"]
