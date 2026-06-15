"""Stage 49 -- Delivery Package & Acceptance Gate operations API.

Read-only package / gate / readiness / handoff views plus a single controlled
write endpoint (``POST .../delivery-package/build``) that builds a formal
delivery package from one completed mini delivery pilot. Operator accept /
reject / request-changes endpoints are scaffolded but DISABLED by default
(``ENABLE_DELIVERY_PACKAGE_OPERATOR_ACTIONS=false``) -- they return
``action_disabled`` and NEVER auto-mark human acceptance.

The build endpoint NEVER calls an LLM, writes GitHub, opens a PR, merges,
deploys, or delivers externally. Responses carry summaries / evidence refs only
-- never file content, secrets, or chain-of-thought.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from shared.sdk.delivery_package import (
    DeliveryPackageRequest,
    DeliveryPackageStore,
    run_delivery_package_build,
)
from shared.sdk.design_review import DesignReviewStore
from shared.sdk.mini_delivery_pilot import MiniDeliveryPilotStore
from shared.sdk.project_planning import ProjectPlanningStore
from shared.sdk.workspace_operator import WorkspaceOperatorStore

router = APIRouter(prefix="/operations", tags=["delivery-package"])


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _flag(name: str, default: bool) -> bool:
    raw = str(os.environ.get(name, "true" if default else "false")).strip().lower()
    return raw not in ("false", "0", "no", "")


def _pilot_store() -> MiniDeliveryPilotStore:
    return MiniDeliveryPilotStore()


def _project_store() -> ProjectPlanningStore:
    return ProjectPlanningStore()


def _review_store() -> DesignReviewStore:
    return DesignReviewStore()


def _workspace_store() -> WorkspaceOperatorStore:
    return WorkspaceOperatorStore()


def _package_store() -> DeliveryPackageStore:
    return DeliveryPackageStore()


async def _require_package(package_id: str) -> dict:
    try:
        package = await _package_store().get_delivery_package(package_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"package store unavailable: {exc}") from exc
    if package is None:
        raise HTTPException(status_code=404, detail="delivery package not found")
    return package


# ---------------------------------------------------------------------------
# Build (write -- controlled-only).
# ---------------------------------------------------------------------------
@router.post("/mini-delivery-pilots/{pilot_id}/delivery-package/build")
async def build_delivery_package(pilot_id: str, payload: dict | None = None) -> dict:
    if not _flag("ENABLE_DELIVERY_PACKAGE", True):
        raise HTTPException(status_code=403, detail="delivery package disabled")
    body = payload or {}
    request = DeliveryPackageRequest(
        pilot_id=pilot_id,
        package_type=str(body.get("package_type") or "mini_project_delivery"),
        controlled_only=True,
        requested_by_agent="operations-api",
    )
    try:
        result = await run_delivery_package_build(
            request=request,
            pilot_store=_pilot_store(),
            project_store=_project_store(),
            review_store=_review_store(),
            workspace_store=_workspace_store(),
            package_store=_package_store(),
            emit_events=True,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503, detail=f"delivery package build failed: {exc}"
        ) from exc
    out = result.model_dump()
    out["generated_at"] = _utcnow_iso()
    return out


# ---------------------------------------------------------------------------
# Package reads.
# ---------------------------------------------------------------------------
@router.get("/delivery-packages")
async def list_packages(project_id: str | None = None) -> dict:
    rows = await _package_store().list_delivery_packages(project_id=project_id)
    return {"count": len(rows), "delivery_packages": rows}


@router.get("/delivery-packages/{package_id}")
async def get_package(package_id: str) -> dict:
    return await _require_package(package_id)


@router.get("/delivery-packages/{package_id}/sections")
async def get_package_sections(package_id: str) -> dict:
    await _require_package(package_id)
    rows = await _package_store().get_package_sections(package_id)
    ready = sum(1 for r in rows if r["status"] == "ready")
    missing = sum(1 for r in rows if r["status"] == "missing")
    return {"count": len(rows), "ready_count": ready, "missing_count": missing, "sections": rows}


@router.get("/delivery-packages/{package_id}/artifacts")
async def get_package_artifacts(package_id: str) -> dict:
    await _require_package(package_id)
    rows = await _package_store().get_package_artifacts(package_id)
    return {"count": len(rows), "artifacts": rows}


@router.get("/delivery-packages/{package_id}/report")
async def get_package_report(package_id: str) -> dict:
    await _require_package(package_id)
    report = await _package_store().get_delivery_package_report(package_id)
    if report is None:
        raise HTTPException(status_code=404, detail="delivery package report not found")
    return report


@router.get("/delivery-packages/{package_id}/handoff-summaries")
async def get_package_handoffs(package_id: str) -> dict:
    await _require_package(package_id)
    rows = await _package_store().get_handoff_summaries(package_id)
    return {"count": len(rows), "handoff_summaries": rows}


@router.get("/delivery-packages/{package_id}/readiness")
async def get_package_readiness(package_id: str) -> dict:
    await _require_package(package_id)
    snapshot = await _package_store().get_readiness_snapshot(package_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="readiness snapshot not found")
    return snapshot


@router.get("/projects/{project_id}/delivery-packages")
async def list_project_packages(project_id: str) -> dict:
    rows = await _package_store().list_delivery_packages(project_id=project_id)
    return {"count": len(rows), "delivery_packages": rows}


@router.get("/projects/{project_id}/latest-delivery-package")
async def latest_project_package(project_id: str) -> dict:
    package = await _package_store().get_latest_package(project_id)
    if package is None:
        raise HTTPException(status_code=404, detail="no delivery package for project")
    return package


# ---------------------------------------------------------------------------
# Acceptance gate reads.
# ---------------------------------------------------------------------------
@router.get("/delivery-packages/{package_id}/acceptance-gate")
async def get_acceptance_gate(package_id: str) -> dict:
    await _require_package(package_id)
    gate = await _package_store().get_acceptance_gate(package_id)
    if gate is None:
        raise HTTPException(status_code=404, detail="acceptance gate not found")
    return gate


@router.get("/delivery-packages/{package_id}/acceptance-checks")
async def get_acceptance_checks(package_id: str) -> dict:
    await _require_package(package_id)
    rows = await _package_store().get_gate_check_results(package_id)
    return {
        "count": len(rows),
        "passed": sum(1 for r in rows if r["status"] == "passed"),
        "failed": sum(1 for r in rows if r["status"] == "failed"),
        "warning": sum(1 for r in rows if r["status"] == "warning"),
        "checks": rows,
    }


@router.get("/delivery-packages/{package_id}/acceptance-checklist")
async def get_acceptance_checklist(package_id: str) -> dict:
    await _require_package(package_id)
    sections = await _package_store().get_package_sections(package_id)
    checklist = next(
        (s["content"] for s in sections if s["section_key"] == "acceptance_checklist"), None
    )
    if checklist is None:
        raise HTTPException(status_code=404, detail="acceptance checklist not found")
    return checklist


@router.get("/projects/{project_id}/acceptance-gates")
async def list_project_gates(project_id: str) -> dict:
    packages = await _package_store().list_delivery_packages(project_id=project_id)
    gates = []
    store = _package_store()
    for pkg in packages:
        gate = await store.get_acceptance_gate(pkg["id"])
        if gate is not None:
            gate["package_id"] = pkg["id"]
            gates.append(gate)
    return {"count": len(gates), "acceptance_gates": gates}


# ---------------------------------------------------------------------------
# Operator review (read + DISABLED-by-default actions).
# ---------------------------------------------------------------------------
@router.get("/delivery-packages/{package_id}/operator-review")
async def get_operator_review(package_id: str) -> dict:
    await _require_package(package_id)
    review = await _package_store().get_operator_review(package_id)
    if review is None:
        raise HTTPException(status_code=404, detail="operator review not found")
    return review


def _operator_action_disabled_response(package_id: str, action: str) -> dict:
    return {
        "package_id": package_id,
        "action": action,
        "status": "action_disabled",
        "policy": "policy_blocked",
        "human_acceptance_status": "pending",
        "reason": "operator actions are disabled by default this stage "
        "(ENABLE_DELIVERY_PACKAGE_OPERATOR_ACTIONS=false)",
        "controlled_only": True,
        "production_executed": False,
        "generated_at": _utcnow_iso(),
    }


@router.post("/delivery-packages/{package_id}/operator-review/accept")
async def operator_accept(package_id: str, payload: dict | None = None) -> dict:
    await _require_package(package_id)
    if not _flag("ENABLE_DELIVERY_PACKAGE_OPERATOR_ACTIONS", False):
        return _operator_action_disabled_response(package_id, "accept")
    # Scaffold only -- real operator-action handling is Admin Console v1.
    raise HTTPException(status_code=501, detail="operator accept not implemented this stage")


@router.post("/delivery-packages/{package_id}/operator-review/reject")
async def operator_reject(package_id: str, payload: dict | None = None) -> dict:
    await _require_package(package_id)
    if not _flag("ENABLE_DELIVERY_PACKAGE_OPERATOR_ACTIONS", False):
        return _operator_action_disabled_response(package_id, "reject")
    raise HTTPException(status_code=501, detail="operator reject not implemented this stage")


@router.post("/delivery-packages/{package_id}/operator-review/request-changes")
async def operator_request_changes(package_id: str, payload: dict | None = None) -> dict:
    await _require_package(package_id)
    if not _flag("ENABLE_DELIVERY_PACKAGE_OPERATOR_ACTIONS", False):
        return _operator_action_disabled_response(package_id, "request_changes")
    raise HTTPException(
        status_code=501, detail="operator request-changes not implemented this stage"
    )


__all__ = ["router"]
