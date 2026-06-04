"""Stage 31 -- approval-policy + LLM proposal promotion API routes.

Mounted on the orchestrator under ``/approval-policies/*`` and
``/llm/proposals/{proposal_id}/...``. All routes are best-effort + emit
audit + notification side effects.

Hard safety rails:

* delegated policies are refused when constraints are incomplete.
* `production_deploy` / `real_github_write` / `branch_protection_modification`
  / `merge` / `delete_file` / `secret_write` / `destructive_command` /
  denylist-path / secret-content can NEVER be authorised by a policy;
  they are blocked by `ApprovalPolicyEvaluator`.
* The promote endpoint always re-runs the LLM safety policy + code
  workspace allowlist BEFORE persisting any code_change_artifact.
* A successful promotion does NOT bypass the QA gate -- the existing
  Stage 29 path still owns final pass/fail.
"""

import contextlib
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from shared.sdk.approval_policy import (
    APPROVAL_MODES,
    ApprovalPolicyStore,
    HumanApprovalPolicy,
    SCOPE_TYPES,
    evaluate_action,
)
from shared.sdk.audit.publisher import publish_audit_event
from shared.sdk.code_workspace import (
    CodeWorkspaceStore,
    DEFAULT_ALLOWED_PATHS,
    DEFAULT_DENIED_PATHS,
    compute_unified_diff,
    hash_content,
    summarize_diff,
    validate_allowed_path,
)
from shared.sdk.llm import (
    LLMInteractionStore,
    apply_llm_safety_policy,
)
from shared.sdk.llm.models import LLMFileChange, LLMPatchProposal
from shared.sdk.notifications.client import send_notification
from shared.sdk.observability.metrics import (
    APPROVAL_POLICIES_TOTAL,
    APPROVAL_POLICY_ACTION_ALLOWED_TOTAL,
    APPROVAL_POLICY_ACTION_BLOCKED_TOTAL,
    APPROVAL_POLICY_ACTIVE_TOTAL,
    APPROVAL_POLICY_DECISIONS_TOTAL,
    APPROVAL_POLICY_REVOKED_TOTAL,
    DELEGATED_ACTIONS_USED_TOTAL,
    LLM_PROMOTIONS_TOTAL,
)
from shared.sdk.observability.tracing import start_span

router = APIRouter(tags=["approval"])


# ---------------------------------------------------------------------------
# Pydantic request models.
# ---------------------------------------------------------------------------


class CreatePolicyIn(BaseModel):
    task_id: str
    workflow_id: str | None = None
    scope_type: str = "task"
    scope_id: str = ""
    approval_mode: str = "per_action"
    granted_by: str = "operator"
    allowed_stages: list[str] = Field(default_factory=list)
    allowed_agents: list[str] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    allowed_paths: list[str] = Field(default_factory=list)
    denied_paths: list[str] = Field(default_factory=list)
    max_actions: int | None = None
    max_files_changed: int | None = None
    max_auto_fix_attempts: int | None = None
    expires_at: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    activate: bool = True


class RevokeIn(BaseModel):
    revoked_by: str = "operator"
    reason: str | None = None


class ApprovalRequestIn(BaseModel):
    task_id: str
    workflow_id: str | None = None
    requested_by: str = "operator"
    approval_mode: str = "per_action"
    policy_id: str | None = None
    reason: str | None = None


class ApproveIn(BaseModel):
    approved_by: str = "operator"
    reason: str | None = None


class RejectIn(BaseModel):
    rejected_by: str = "operator"
    reason: str | None = None


class PromoteIn(BaseModel):
    task_id: str
    workflow_id: str | None = None
    promoted_by: str = "operator"
    approval_id: str | None = None
    policy_id: str | None = None
    promotion_mode: str = "manual"  # manual | policy_allowed | delegated_agent


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_create_payload(payload: CreatePolicyIn) -> None:
    if payload.approval_mode not in APPROVAL_MODES:
        raise HTTPException(
            status_code=400, detail=f"unknown approval_mode:{payload.approval_mode}"
        )
    if payload.scope_type not in SCOPE_TYPES:
        raise HTTPException(status_code=400, detail=f"unknown scope_type:{payload.scope_type}")
    if payload.approval_mode == "delegated":
        # Delegated mode requires the full constraint set.
        if not payload.allowed_actions:
            raise HTTPException(status_code=400, detail="delegated_missing:allowed_actions")
        if not payload.allowed_paths:
            raise HTTPException(status_code=400, detail="delegated_missing:allowed_paths")
        if not payload.denied_paths:
            raise HTTPException(status_code=400, detail="delegated_missing:denied_paths")
        if payload.max_actions is None or payload.max_actions <= 0:
            raise HTTPException(status_code=400, detail="delegated_missing:max_actions")
        if payload.max_files_changed is None or payload.max_files_changed <= 0:
            raise HTTPException(status_code=400, detail="delegated_missing:max_files_changed")
        if payload.max_auto_fix_attempts is None or payload.max_auto_fix_attempts < 0:
            raise HTTPException(status_code=400, detail="delegated_missing:max_auto_fix_attempts")
        if not payload.expires_at:
            raise HTTPException(status_code=400, detail="delegated_missing:expires_at")
    if payload.approval_mode in ("per_feature", "per_stage"):
        # per_feature / per_stage need a non-empty allowed_actions and
        # at least one allowlisted path. A policy with no constraints is
        # indistinguishable from delegated -- refuse to confuse the
        # evaluator.
        if not payload.allowed_actions:
            raise HTTPException(
                status_code=400,
                detail=f"{payload.approval_mode}_missing:allowed_actions",
            )
        if not payload.allowed_paths:
            raise HTTPException(
                status_code=400,
                detail=f"{payload.approval_mode}_missing:allowed_paths",
            )
        if payload.approval_mode == "per_stage" and not payload.allowed_stages:
            raise HTTPException(status_code=400, detail="per_stage_missing:allowed_stages")


def _parse_expires_at(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="invalid_expires_at") from None


def _proposal_to_patch(proposal_row: Any) -> tuple[LLMPatchProposal, list[str]]:
    """Reconstruct an :class:`LLMPatchProposal` from a stored proposal
    artifact so the safety policy can re-scan it without trusting the
    JSON shape."""
    plan = proposal_row.plan or {}
    raw_files: list[Any] = proposal_row.proposed_files or []
    changes: list[LLMFileChange] = []
    files: list[str] = []
    for entry in raw_files:
        if not isinstance(entry, dict):
            continue
        file_path = str(entry.get("file_path") or "")
        if not file_path:
            continue
        files.append(file_path)
        changes.append(
            LLMFileChange(
                file_path=file_path,
                change_type=str(entry.get("change_type") or "create"),
                proposed_content=str(entry.get("proposed_content") or ""),
                diff_summary=str(entry.get("diff_summary") or ""),
                reason=str(entry.get("reason") or ""),
            )
        )
    return (
        LLMPatchProposal(
            task_id=proposal_row.task_id,
            patch_id=str(plan.get("patch_id") or ""),
            proposed_files=list(files),
            changes=changes,
            rationale=str(plan.get("rationale") or ""),
            risk_level=str(plan.get("risk_level") or "low"),
            safety_notes=list(plan.get("safety_notes") or []),
            test_commands=list(plan.get("test_commands") or []),
            rollback_plan=str(plan.get("rollback_plan") or ""),
            confidence=float(plan.get("confidence_proposal") or 0.5),
            requires_human_review=True,
        ),
        files,
    )


async def _audit(
    *,
    task_id: str,
    workflow_id: str | None,
    decision_type: str,
    summary: str,
    result: str,
    artifact_refs: dict[str, Any],
) -> None:
    with contextlib.suppress(Exception):
        await publish_audit_event(
            task_id=task_id,
            workflow_id=workflow_id or "",
            agent="approval-policy",
            decision_type=decision_type,
            summary=summary,
            result=result,
            artifact_refs={**artifact_refs, "production_executed": False},
        )


async def _notify(task_id: str, event_type: str, message: str) -> None:
    with contextlib.suppress(Exception):
        await send_notification(task_id, event_type, message)


# ---------------------------------------------------------------------------
# /approval-policies routes
# ---------------------------------------------------------------------------


@router.post("/approval-policies")
async def create_policy(payload: CreatePolicyIn) -> dict:
    _validate_create_payload(payload)
    expires = _parse_expires_at(payload.expires_at)
    store = ApprovalPolicyStore()
    initial_status = "active" if payload.activate else "pending"
    with start_span(
        "approval_policy.create",
        **{
            "service.name": "orchestrator",
            "agent": "approval-policy",
            "task_id": payload.task_id,
            "approval_mode": payload.approval_mode,
            "scope_type": payload.scope_type,
        },
    ):
        try:
            policy = await store.create_policy(
                task_id=payload.task_id,
                workflow_id=payload.workflow_id,
                scope_type=payload.scope_type,
                scope_id=payload.scope_id or payload.task_id,
                approval_mode=payload.approval_mode,
                granted_by=payload.granted_by,
                status=initial_status,
                expires_at=expires,
                max_actions=payload.max_actions,
                max_files_changed=payload.max_files_changed,
                max_auto_fix_attempts=payload.max_auto_fix_attempts,
                allowed_stages=payload.allowed_stages,
                allowed_agents=payload.allowed_agents,
                allowed_actions=payload.allowed_actions,
                allowed_paths=payload.allowed_paths,
                denied_paths=payload.denied_paths,
                constraints=payload.constraints,
                reason=payload.reason,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=503, detail=f"approval policy store unavailable: {exc}"
            ) from exc
    APPROVAL_POLICIES_TOTAL.labels(
        approval_mode=policy.approval_mode, scope_type=policy.scope_type
    ).inc()
    if policy.status == "active":
        APPROVAL_POLICY_ACTIVE_TOTAL.labels(
            approval_mode=policy.approval_mode, scope_type=policy.scope_type
        ).inc()
    await _audit(
        task_id=policy.task_id,
        workflow_id=policy.workflow_id,
        decision_type=(
            "approval_policy_activated" if policy.status == "active" else "approval_policy_created"
        ),
        summary=(
            f"approval policy {policy.policy_id} {policy.status} for "
            f"{policy.task_id} (mode={policy.approval_mode})"
        ),
        result=policy.status,
        artifact_refs={
            "policy_id": policy.policy_id,
            "approval_mode": policy.approval_mode,
            "scope_type": policy.scope_type,
            "scope_id": policy.scope_id,
            "granted_by": policy.granted_by,
            "max_actions": policy.max_actions,
            "max_files_changed": policy.max_files_changed,
        },
    )
    await _notify(
        policy.task_id,
        ("approval.policy_activated" if policy.status == "active" else "approval.policy_created"),
        (
            f"approval policy {policy.policy_id} {policy.status} for "
            f"{policy.task_id} (mode={policy.approval_mode})"
        ),
    )
    return {"policy": policy.to_dict(), "generated_at": _utcnow_iso()}


@router.get("/approval-policies")
async def list_policies(
    task_id: str | None = None,
    workflow_id: str | None = None,
    status: str | None = None,
    approval_mode: str | None = None,
    limit: int = 100,
) -> dict:
    capped = max(1, min(int(limit or 100), 500))
    try:
        rows = await ApprovalPolicyStore().list_policies(
            task_id=task_id,
            workflow_id=workflow_id,
            status=status,
            approval_mode=approval_mode,
            limit=capped,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"approval policy store unavailable: {exc}"
        ) from exc
    return {
        "count": len(rows),
        "policies": [r.to_dict() for r in rows],
        "filter": {
            "task_id": task_id,
            "workflow_id": workflow_id,
            "status": status,
            "approval_mode": approval_mode,
            "limit": capped,
        },
        "generated_at": _utcnow_iso(),
    }


@router.get("/approval-policies/{policy_id}")
async def get_policy(policy_id: str) -> dict:
    try:
        policy = await ApprovalPolicyStore().get_policy(policy_id)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"approval policy store unavailable: {exc}"
        ) from exc
    if policy is None:
        raise HTTPException(status_code=404, detail="approval policy not found")
    return {"policy": policy.to_dict(), "generated_at": _utcnow_iso()}


@router.post("/approval-policies/{policy_id}/activate")
async def activate_policy(policy_id: str) -> dict:
    store = ApprovalPolicyStore()
    with start_span(
        "approval_policy.activate",
        **{
            "service.name": "orchestrator",
            "agent": "approval-policy",
            "policy_id": policy_id,
        },
    ):
        policy = await store.update_policy_status(policy_id, status="active")
    if policy is None:
        raise HTTPException(status_code=404, detail="approval policy not found")
    APPROVAL_POLICY_ACTIVE_TOTAL.labels(
        approval_mode=policy.approval_mode, scope_type=policy.scope_type
    ).inc()
    await _audit(
        task_id=policy.task_id,
        workflow_id=policy.workflow_id,
        decision_type="approval_policy_activated",
        summary=(
            f"approval policy {policy.policy_id} activated for {policy.task_id} "
            f"(mode={policy.approval_mode})"
        ),
        result="active",
        artifact_refs={
            "policy_id": policy.policy_id,
            "approval_mode": policy.approval_mode,
            "scope_type": policy.scope_type,
        },
    )
    await _notify(
        policy.task_id,
        "approval.policy_activated",
        f"approval policy {policy.policy_id} activated for {policy.task_id}",
    )
    return {"policy": policy.to_dict(), "generated_at": _utcnow_iso()}


@router.post("/approval-policies/{policy_id}/revoke")
async def revoke_policy(policy_id: str, payload: RevokeIn) -> dict:
    store = ApprovalPolicyStore()
    with start_span(
        "approval_policy.revoke",
        **{
            "service.name": "orchestrator",
            "agent": "approval-policy",
            "policy_id": policy_id,
        },
    ):
        policy = await store.update_policy_status(policy_id, status="revoked")
    if policy is None:
        raise HTTPException(status_code=404, detail="approval policy not found")
    APPROVAL_POLICY_REVOKED_TOTAL.labels(
        approval_mode=policy.approval_mode, scope_type=policy.scope_type
    ).inc()
    await _audit(
        task_id=policy.task_id,
        workflow_id=policy.workflow_id,
        decision_type="approval_policy_revoked",
        summary=(
            f"approval policy {policy.policy_id} revoked by {payload.revoked_by} "
            f"({payload.reason or 'no reason'})"
        ),
        result="revoked",
        artifact_refs={
            "policy_id": policy.policy_id,
            "approval_mode": policy.approval_mode,
            "scope_type": policy.scope_type,
            "revoked_by": payload.revoked_by,
            "reason": payload.reason,
        },
    )
    await _notify(
        policy.task_id,
        "approval.policy_revoked",
        f"approval policy {policy.policy_id} revoked",
    )
    return {"policy": policy.to_dict(), "generated_at": _utcnow_iso()}


@router.get("/approval-policies/{policy_id}/decisions")
async def list_policy_decisions(policy_id: str, limit: int = 200) -> dict:
    capped = max(1, min(int(limit or 200), 500))
    try:
        rows = await ApprovalPolicyStore().list_decisions(policy_id=policy_id, limit=capped)
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"approval policy store unavailable: {exc}"
        ) from exc
    return {
        "policy_id": policy_id,
        "count": len(rows),
        "decisions": [r.to_dict() for r in rows],
        "generated_at": _utcnow_iso(),
    }


# ---------------------------------------------------------------------------
# LLM proposal approval + promotion routes
# ---------------------------------------------------------------------------


@router.post("/llm/proposals/{proposal_id}/approval/request")
async def request_proposal_approval(proposal_id: str, payload: ApprovalRequestIn) -> dict:
    if payload.approval_mode not in APPROVAL_MODES:
        raise HTTPException(
            status_code=400, detail=f"unknown approval_mode:{payload.approval_mode}"
        )
    llm_store = LLMInteractionStore()
    proposal_rows = await llm_store.list_proposals(task_id=payload.task_id, limit=200)
    proposal = next((r for r in proposal_rows if r.proposal_id == proposal_id), None)
    if proposal is None:
        raise HTTPException(status_code=404, detail="llm proposal not found")
    store = ApprovalPolicyStore()
    approval = await store.request_approval(
        proposal_id=proposal_id,
        task_id=payload.task_id,
        workflow_id=payload.workflow_id,
        approval_mode=payload.approval_mode,
        policy_id=payload.policy_id,
        requested_by=payload.requested_by,
        safety_snapshot={
            "proposal_status": proposal.status,
            "proposal_safety_result": proposal.safety_result,
            "production_executed": False,
        },
    )
    await _audit(
        task_id=payload.task_id,
        workflow_id=payload.workflow_id,
        decision_type="llm_proposal_approval_requested",
        summary=(
            f"approval requested for proposal {proposal_id} " f"(mode={payload.approval_mode})"
        ),
        result="requested",
        artifact_refs={
            "approval_id": approval.approval_id,
            "proposal_id": proposal_id,
            "approval_mode": payload.approval_mode,
            "policy_id": payload.policy_id,
            "requested_by": payload.requested_by,
        },
    )
    return {"approval": approval.to_dict(), "generated_at": _utcnow_iso()}


@router.post("/llm/proposals/{proposal_id}/approval/approve")
async def approve_proposal(proposal_id: str, payload: ApproveIn) -> dict:
    store = ApprovalPolicyStore()
    existing = await store.get_latest_approval(proposal_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="approval request not found")
    approval = await store.approve_proposal(
        existing.approval_id,
        approved_by=payload.approved_by,
        reason=payload.reason,
    )
    if approval is None:
        raise HTTPException(status_code=503, detail="failed to record approval")
    await store.record_decision(
        policy_id=approval.policy_id,
        task_id=approval.task_id,
        workflow_id=approval.workflow_id,
        proposal_id=proposal_id,
        action_type="llm_proposal_approve",
        decision="approved",
        decided_by=payload.approved_by,
        reason=payload.reason,
        safety_snapshot=approval.safety_snapshot,
    )
    APPROVAL_POLICY_DECISIONS_TOTAL.labels(
        approval_mode=approval.approval_mode,
        action_type="llm_proposal_approve",
        decision="approved",
    ).inc()
    await _audit(
        task_id=approval.task_id,
        workflow_id=approval.workflow_id,
        decision_type="llm_proposal_approved",
        summary=(
            f"proposal {proposal_id} approved by {payload.approved_by} "
            f"({payload.reason or 'no reason'})"
        ),
        result="approved",
        artifact_refs={
            "proposal_id": proposal_id,
            "approval_id": approval.approval_id,
            "approval_mode": approval.approval_mode,
            "approved_by": payload.approved_by,
        },
    )
    await _notify(
        approval.task_id,
        "llm.proposal_approved",
        f"proposal {proposal_id} approved",
    )
    return {"approval": approval.to_dict(), "generated_at": _utcnow_iso()}


@router.post("/llm/proposals/{proposal_id}/approval/reject")
async def reject_proposal(proposal_id: str, payload: RejectIn) -> dict:
    store = ApprovalPolicyStore()
    existing = await store.get_latest_approval(proposal_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="approval request not found")
    approval = await store.reject_proposal(
        existing.approval_id,
        rejected_by=payload.rejected_by,
        reason=payload.reason,
    )
    if approval is None:
        raise HTTPException(status_code=503, detail="failed to record rejection")
    await store.record_decision(
        policy_id=approval.policy_id,
        task_id=approval.task_id,
        workflow_id=approval.workflow_id,
        proposal_id=proposal_id,
        action_type="llm_proposal_reject",
        decision="rejected",
        decided_by=payload.rejected_by,
        reason=payload.reason,
        safety_snapshot=approval.safety_snapshot,
    )
    APPROVAL_POLICY_DECISIONS_TOTAL.labels(
        approval_mode=approval.approval_mode,
        action_type="llm_proposal_reject",
        decision="rejected",
    ).inc()
    await _audit(
        task_id=approval.task_id,
        workflow_id=approval.workflow_id,
        decision_type="llm_proposal_rejected",
        summary=(
            f"proposal {proposal_id} rejected by {payload.rejected_by} "
            f"({payload.reason or 'no reason'})"
        ),
        result="rejected",
        artifact_refs={
            "proposal_id": proposal_id,
            "approval_id": approval.approval_id,
            "approval_mode": approval.approval_mode,
            "rejected_by": payload.rejected_by,
        },
    )
    await _notify(
        approval.task_id,
        "llm.proposal_rejected",
        f"proposal {proposal_id} rejected",
    )
    return {"approval": approval.to_dict(), "generated_at": _utcnow_iso()}


async def _select_authorising_policy(
    *,
    store: ApprovalPolicyStore,
    task_id: str,
    workflow_id: str | None,
    action_type: str,
    stage: str,
    agent: str,
    paths: list[str],
    files_changed: int,
    content_samples: list[str],
    explicit_policy_id: str | None,
) -> tuple[HumanApprovalPolicy | None, Any]:
    """Return ``(authorising_policy, evaluator_result)``."""
    if explicit_policy_id:
        policy = await store.get_policy(explicit_policy_id)
        candidates = [policy] if policy is not None else []
    else:
        candidates = await store.list_active_policies_for(task_id=task_id)
    result = evaluate_action(
        task_id=task_id,
        workflow_id=workflow_id,
        action_type=action_type,
        stage=stage,
        agent=agent,
        paths=paths,
        files_changed=files_changed,
        content_samples=content_samples,
        candidate_policies=candidates,
    )
    chosen: HumanApprovalPolicy | None = None
    if result.allowed and result.policy_id:
        chosen = next(
            (p for p in candidates if p is not None and p.policy_id == result.policy_id),
            None,
        )
    return chosen, result


@router.post("/llm/proposals/{proposal_id}/promote")
async def promote_proposal(proposal_id: str, payload: PromoteIn) -> dict:
    # 1. Load the proposal.
    llm_store = LLMInteractionStore()
    proposal_rows = await llm_store.list_proposals(task_id=payload.task_id, limit=200)
    proposal_row = next((r for r in proposal_rows if r.proposal_id == proposal_id), None)
    if proposal_row is None:
        raise HTTPException(status_code=404, detail="llm proposal not found")

    # 2. Re-validate the proposal against the safety policy. A
    #    `proposal.status` of `blocked` is a hard refusal.
    patch, files = _proposal_to_patch(proposal_row)
    safety_result = apply_llm_safety_policy(patch)
    approval_store = ApprovalPolicyStore()

    # 3. Hard policy block check.
    if proposal_row.status == "blocked" or not safety_result.get("allowed"):
        promotion = await approval_store.create_promotion(
            proposal_id=proposal_id,
            task_id=payload.task_id,
            workflow_id=payload.workflow_id,
            approval_id=payload.approval_id,
            policy_id=payload.policy_id,
            promotion_mode=payload.promotion_mode,
            promoted_by=payload.promoted_by,
            status="blocked_by_policy",
            validation_result={
                "stage": "llm_safety_policy",
                "result": safety_result,
                "reason": (
                    "proposal_blocked"
                    if proposal_row.status == "blocked"
                    else "llm_safety_violation"
                ),
            },
            error="llm safety policy refused promotion",
        )
        LLM_PROMOTIONS_TOTAL.labels(
            promotion_mode=payload.promotion_mode, status="blocked_by_policy"
        ).inc()
        APPROVAL_POLICY_ACTION_BLOCKED_TOTAL.labels(
            reason="llm_safety_policy", action_type="llm_proposal_promote"
        ).inc()
        await _audit(
            task_id=payload.task_id,
            workflow_id=payload.workflow_id,
            decision_type="llm_promotion_blocked",
            summary=(f"proposal {proposal_id} promotion blocked by llm safety policy"),
            result="blocked",
            artifact_refs={
                "proposal_id": proposal_id,
                "promotion_id": promotion.promotion_id,
                "safety_result": safety_result,
                "promotion_mode": payload.promotion_mode,
            },
        )
        await _notify(
            payload.task_id,
            "llm.promotion_blocked",
            f"proposal {proposal_id} promotion blocked by llm safety policy",
        )
        return {"promotion": promotion.to_dict(), "generated_at": _utcnow_iso()}

    # 4. Approval gate: per_action requires an approved approval row; the
    #    other modes can authorise via an active policy.
    files_count = len(files)
    content_samples = [c.proposed_content for c in patch.changes]
    chosen_policy, eval_result = await _select_authorising_policy(
        store=approval_store,
        task_id=payload.task_id,
        workflow_id=payload.workflow_id,
        action_type="llm_proposal_promote",
        stage="code_generation",
        agent=payload.promoted_by,
        paths=files,
        files_changed=files_count,
        content_samples=content_samples,
        explicit_policy_id=payload.policy_id,
    )

    explicit_approval = None
    if payload.approval_id:
        existing = await approval_store.list_approvals(
            task_id=payload.task_id, proposal_id=proposal_id, limit=20
        )
        explicit_approval = next(
            (a for a in existing if a.approval_id == payload.approval_id),
            None,
        )
    else:
        explicit_approval = await approval_store.get_latest_approval(proposal_id)
    explicit_ok = explicit_approval is not None and explicit_approval.status == "approved"

    if not eval_result.allowed and not explicit_ok:
        promotion = await approval_store.create_promotion(
            proposal_id=proposal_id,
            task_id=payload.task_id,
            workflow_id=payload.workflow_id,
            approval_id=payload.approval_id,
            policy_id=payload.policy_id,
            promotion_mode=payload.promotion_mode,
            promoted_by=payload.promoted_by,
            status="blocked_by_policy",
            validation_result={
                "stage": "approval_policy",
                "result": eval_result.to_dict(),
                "reason": eval_result.reason,
            },
            error=eval_result.reason,
        )
        LLM_PROMOTIONS_TOTAL.labels(
            promotion_mode=payload.promotion_mode, status="blocked_by_policy"
        ).inc()
        APPROVAL_POLICY_ACTION_BLOCKED_TOTAL.labels(
            reason=eval_result.reason or "no_active_policy",
            action_type="llm_proposal_promote",
        ).inc()
        await _audit(
            task_id=payload.task_id,
            workflow_id=payload.workflow_id,
            decision_type="approval_policy_action_blocked",
            summary=(
                f"proposal {proposal_id} promotion blocked "
                f"({eval_result.reason}, hard={eval_result.hard_policy_block})"
            ),
            result="blocked",
            artifact_refs={
                "proposal_id": proposal_id,
                "promotion_id": promotion.promotion_id,
                "evaluation": eval_result.to_dict(),
                "hard_policy_block": eval_result.hard_policy_block,
                "promotion_mode": payload.promotion_mode,
            },
        )
        await _notify(
            payload.task_id,
            "approval.action_blocked",
            (f"proposal {proposal_id} promotion blocked " f"({eval_result.reason})"),
        )
        return {"promotion": promotion.to_dict(), "generated_at": _utcnow_iso()}

    # 5. Determine the effective promotion_mode + policy linkage.
    effective_mode = payload.promotion_mode
    effective_policy_id = payload.policy_id or (
        chosen_policy.policy_id if chosen_policy is not None else None
    )
    decision_source = "explicit_approval" if explicit_ok else "policy_allows"
    if eval_result.allowed and not explicit_ok:
        # Policy authorised -- override the promotion_mode to one that
        # records the policy attribution.
        if chosen_policy is not None and chosen_policy.approval_mode == "delegated":
            effective_mode = "delegated_agent"
        else:
            effective_mode = "policy_allowed"

    # 6. Materialise files into the workspace.
    workspace_store = CodeWorkspaceStore()
    workspace = None
    with contextlib.suppress(Exception):
        workspace = await workspace_store.get_workspace(payload.task_id)
    workspace_id = workspace.workspace_id if workspace is not None else None
    accepted: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    for change in patch.changes:
        ok_path, why = validate_allowed_path(
            change.file_path,
            allowed=DEFAULT_ALLOWED_PATHS,
            denied=DEFAULT_DENIED_PATHS,
        )
        if not ok_path:
            refused.append({"file_path": change.file_path, "reason": why})
            continue
        if workspace_id is None:
            refused.append({"file_path": change.file_path, "reason": "no_workspace"})
            continue
        content = change.proposed_content or ""
        diff_text = compute_unified_diff("", content, file_path=change.file_path)
        diff_summary_dict = summarize_diff(diff_text)
        diff_summary_str = (
            f"+{diff_summary_dict.get('added', 0)}/-{diff_summary_dict.get('removed', 0)}"
            f" ({diff_summary_dict.get('hunks', 0)} hunks)"
        )
        with contextlib.suppress(Exception):
            artifact = await workspace_store.add_code_change_artifact(
                task_id=payload.task_id,
                workflow_id=payload.workflow_id,
                workspace_id=workspace_id,
                file_path=change.file_path,
                change_type=change.change_type,
                before_sha="",
                after_sha=hash_content(content),
                diff_summary=diff_summary_str,
                diff_text=diff_text[:4000],
                generated_content_preview=content[:20000],
                validation_status="pending",
            )
            accepted.append(
                {
                    "file_path": change.file_path,
                    "change_type": change.change_type,
                    "artifact_id": artifact.artifact_id,
                }
            )

    promotion_status = "promoted" if accepted else "validation_failed"
    promotion = await approval_store.create_promotion(
        proposal_id=proposal_id,
        task_id=payload.task_id,
        workflow_id=payload.workflow_id,
        approval_id=(
            payload.approval_id or (explicit_approval.approval_id if explicit_approval else None)
        ),
        policy_id=effective_policy_id,
        workspace_id=workspace_id,
        promotion_mode=effective_mode,
        promoted_by=payload.promoted_by,
        status=promotion_status,
        promoted_files=accepted,
        validation_result={
            "stage": "promotion",
            "accepted": accepted,
            "refused": refused,
            "decision_source": decision_source,
            "evaluation": eval_result.to_dict(),
        },
    )
    await approval_store.update_promotion(
        promotion.promotion_id,
        status=promotion_status,
        promoted_at_now=True,
    )

    # 7. Bookkeeping: decision row + policy actions_used + linked proposal.
    if effective_policy_id is not None:
        with contextlib.suppress(Exception):
            await approval_store.increment_actions_used(effective_policy_id)
        DELEGATED_ACTIONS_USED_TOTAL.labels(
            scope_type=(chosen_policy.scope_type if chosen_policy is not None else "task")
        ).inc()
    decision_label = "approved" if explicit_ok else "delegated"
    await approval_store.record_decision(
        policy_id=effective_policy_id,
        task_id=payload.task_id,
        workflow_id=payload.workflow_id,
        proposal_id=proposal_id,
        promotion_id=promotion.promotion_id,
        action_type="llm_proposal_promote",
        decision=decision_label,
        decided_by=payload.promoted_by,
        reason=eval_result.reason if not explicit_ok else "explicit_approval",
        safety_snapshot=eval_result.safety_snapshot,
    )
    APPROVAL_POLICY_DECISIONS_TOTAL.labels(
        approval_mode=(chosen_policy.approval_mode if chosen_policy is not None else "per_action"),
        action_type="llm_proposal_promote",
        decision=decision_label,
    ).inc()
    APPROVAL_POLICY_ACTION_ALLOWED_TOTAL.labels(
        approval_mode=(chosen_policy.approval_mode if chosen_policy is not None else "per_action"),
        action_type="llm_proposal_promote",
    ).inc()
    LLM_PROMOTIONS_TOTAL.labels(promotion_mode=effective_mode, status=promotion_status).inc()
    with contextlib.suppress(Exception):
        await llm_store.update_proposal_status(
            proposal_id,
            status="accepted_for_workspace" if accepted else "policy_passed",
            linked_workspace_id=workspace_id,
        )
    await _audit(
        task_id=payload.task_id,
        workflow_id=payload.workflow_id,
        decision_type="llm_proposal_promoted",
        summary=(
            f"proposal {proposal_id} promoted by {payload.promoted_by} "
            f"(mode={effective_mode}, files={len(accepted)})"
        ),
        result=promotion_status,
        artifact_refs={
            "proposal_id": proposal_id,
            "promotion_id": promotion.promotion_id,
            "promotion_mode": effective_mode,
            "policy_id": effective_policy_id,
            "approval_id": (
                payload.approval_id
                or (explicit_approval.approval_id if explicit_approval else None)
            ),
            "decision_source": decision_source,
            "accepted_files": [a["file_path"] for a in accepted],
            "refused_files": refused,
        },
    )
    await _notify(
        payload.task_id,
        "llm.proposal_promoted",
        (f"proposal {proposal_id} promoted " f"(mode={effective_mode}, files={len(accepted)})"),
    )
    # Re-fetch for the latest promoted_at timestamp; fall back to the
    # in-memory record so the response always carries promotion_mode +
    # status + accepted_files even when the fetch fails.
    final_promotion = promotion
    with contextlib.suppress(Exception):
        fetched = await approval_store.get_promotion(promotion.promotion_id)
        if fetched is not None:
            final_promotion = fetched
            final_promotion.promotion_mode = effective_mode
            final_promotion.status = promotion_status
    return {
        "promotion": final_promotion.to_dict() if final_promotion is not None else {},
        "accepted_files": accepted,
        "refused_files": refused,
        "evaluation": eval_result.to_dict(),
        "decision_source": decision_source,
        "promotion_mode": effective_mode,
        "generated_at": _utcnow_iso(),
    }
