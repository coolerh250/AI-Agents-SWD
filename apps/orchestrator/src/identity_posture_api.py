"""Step 52.4 -- read-only identity posture API.

GET-only visibility over the COMMITTED Step 52 identity posture summary. NO write
endpoints, NO login/callback/authorize/token/logout, NO role-mapping mutation, NO
break-glass route, NO IdP connection, NO secret/key-file read, NO user-provided
path. Absent summary -> ``status: unknown`` (never a fake PASS). Responses carry
statuses / booleans / enums only -- no token, secret, raw email, or real group ID.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from shared.sdk.identity_posture import (
    full_report,
    load_identity_posture_summary,
    posture_view,
    readiness_view,
    section_view,
)

router = APIRouter(prefix="/operations/identity", tags=["identity-posture"])

# Committed + copied into the image; never user-provided.
_SUMMARY_PATH = Path("infra/identity/identity-posture-summary.yaml")


def _summary() -> dict[str, Any] | None:
    return load_identity_posture_summary(_SUMMARY_PATH)


@router.get("/posture")
def identity_posture() -> dict:
    return posture_view(_summary())


@router.get("/authentication")
def identity_authentication() -> dict:
    s = _summary()
    p = (s or {}).get("identityPosture", {}) if s else {}
    return {
        "productionAuthEnabled": bool(p.get("productionAuthEnabled")),
        "testLocalEnabled": bool(p.get("testLocalEnabled")),
        "testLocalProductionFallbackAllowed": bool(p.get("testLocalProductionFallbackAllowed")),
        "status": p.get("status", "unknown"),
    }


@router.get("/session")
def identity_session() -> dict:
    return section_view(_summary(), "session")


@router.get("/csrf")
def identity_csrf() -> dict:
    # CSRF posture is structural (Step 52.1): protected mutations, header, no token logged.
    return {
        "enabled": True,
        "header": "X-CSRF-Token",
        "tokenPersisted": False,
        "getProtected": False,
    }


@router.get("/rbac")
def identity_rbac() -> dict:
    s = _summary()
    p = (s or {}).get("identityPosture", {}) if s else {}
    az = p.get("authorization", {}) or {}
    return {
        "roles": ["viewer", "reviewer", "operator", "platform_admin"],
        "platformAdminInfrastructureAuthority": bool(
            az.get("platformAdminInfrastructureAuthority")
        ),
    }


@router.get("/operator-actions")
def identity_operator_actions() -> dict:
    s = _summary()
    p = (s or {}).get("identityPosture", {}) if s else {}
    az = p.get("authorization", {}) or {}
    return {
        "humanAcceptanceIsDeployment": bool(az.get("humanAcceptanceIsDeployment")),
        "verificationRerunAllowlistedOnly": bool(az.get("verificationRerunAllowlistedOnly")),
    }


@router.get("/oidc")
def identity_oidc() -> dict:
    return section_view(_summary(), "oidc")


@router.get("/role-mapping")
def identity_role_mapping() -> dict:
    return section_view(_summary(), "roleMapping")


@router.get("/break-glass")
def identity_break_glass() -> dict:
    return section_view(_summary(), "breakGlass")


@router.get("/audit-mapping")
def identity_audit_mapping() -> dict:
    # Planned (disabled) OIDC audit enrichment uses hashes only; never raw values.
    return {
        "enrichmentEnabled": False,
        "subjectRecording": "subject_hash",
        "emailRecording": "email_hash",
        "groupRecording": "group_mapping_rule_id",
        "rawTokenPersisted": False,
        "rawClaimsPersisted": False,
    }


@router.get("/risks")
def identity_risks() -> dict:
    p = (_summary() or {}).get("identityPosture", {})
    return {"limitations": list(p.get("limitations", []))}


@router.get("/readiness")
def identity_readiness() -> dict:
    return readiness_view(_summary())


@router.get("/report")
def identity_report() -> dict:
    return full_report(_summary())


__all__ = ["router"]
