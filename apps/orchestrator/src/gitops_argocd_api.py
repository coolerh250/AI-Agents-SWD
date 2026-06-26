"""Step 56 (Stage 58A) -- read-only non-production ArgoCD manual-sync API.

GET-only visibility over the COMMITTED non-production ArgoCD summary / plan / install
boundary / project policy. There is NO sync endpoint, NO install endpoint, NO
delete / rollback / promote endpoint, NO mutation of any kind, NO arbitrary
namespace / command input, and NO cluster call. The live runtime sync report is
never committed and is absent in the image, so the report view degrades to
``not_run``. Responses carry statuses / enums / names / the public git revision only
-- never a kubeconfig, token, admin password, secret, or rendered manifest.
"""

from __future__ import annotations

from fastapi import APIRouter

from shared.sdk.argocd_sync import posture

router = APIRouter(prefix="/operations/gitops/nonprod-argocd", tags=["gitops-argocd"])


@router.get("/preflight")
def nonprod_argocd_preflight() -> dict:
    return posture.preflight_view()


@router.get("/install")
def nonprod_argocd_install() -> dict:
    return posture.install_view()


@router.get("/project")
def nonprod_argocd_project() -> dict:
    return posture.project_view()


@router.get("/application")
def nonprod_argocd_application() -> dict:
    return posture.application_view()


@router.get("/sync")
def nonprod_argocd_sync() -> dict:
    return posture.sync_view()


@router.get("/safety")
def nonprod_argocd_safety() -> dict:
    return posture.safety_view()


@router.get("/report")
def nonprod_argocd_report() -> dict:
    return posture.report_view()


@router.get("/readiness")
def nonprod_argocd_readiness() -> dict:
    return posture.readiness_view()


__all__ = ["router"]
