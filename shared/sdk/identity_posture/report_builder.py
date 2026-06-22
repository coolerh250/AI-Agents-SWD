"""Step 52.4 -- identity posture report builder (read-only, redacted).

Builds the per-section views the read-only API serves. Pure dict shaping over
the posture summary; carries no secret, token, raw email, or real group ID.
"""

from __future__ import annotations

from typing import Any

from shared.sdk.identity_posture.models import STATUS_UNKNOWN


def _posture(summary: dict[str, Any] | None) -> dict[str, Any]:
    return (summary or {}).get("identityPosture", {}) if summary else {}


def posture_view(summary: dict[str, Any] | None) -> dict[str, Any]:
    p = _posture(summary)
    return {
        "status": p.get("status", STATUS_UNKNOWN),
        "productionIdentityReady": bool(p.get("productionIdentityReady")),
        "productionAuthEnabled": bool(p.get("productionAuthEnabled")),
        "testLocalEnabled": bool(p.get("testLocalEnabled")),
        "testLocalProductionFallbackAllowed": bool(p.get("testLocalProductionFallbackAllowed")),
        "limitations": list(p.get("limitations", [])),
        "nextRequiredSteps": list(p.get("nextRequiredSteps", [])),
    }


def section_view(summary: dict[str, Any] | None, key: str) -> dict[str, Any]:
    return dict(_posture(summary).get(key, {}) or {})


def readiness_view(summary: dict[str, Any] | None) -> dict[str, Any]:
    p = _posture(summary)
    return {
        "status": p.get("status", STATUS_UNKNOWN),
        "productionIdentityReady": False,
        "productionAuthEnabled": bool(p.get("productionAuthEnabled")),
        "oidcEnabled": bool(p.get("oidc", {}).get("enabled")),
        "blockers": list(p.get("limitations", [])),
        "nextRequiredSteps": list(p.get("nextRequiredSteps", [])),
    }


def full_report(summary: dict[str, Any] | None) -> dict[str, Any]:
    p = _posture(summary)
    return {
        "status": p.get("status", STATUS_UNKNOWN),
        "productionIdentityReady": False,
        "posture": posture_view(summary),
        "oidc": section_view(summary, "oidc"),
        "session": section_view(summary, "session"),
        "roleMapping": section_view(summary, "roleMapping"),
        "breakGlass": section_view(summary, "breakGlass"),
        "authorization": section_view(summary, "authorization"),
        "limitations": list(p.get("limitations", [])),
        "nextRequiredSteps": list(p.get("nextRequiredSteps", [])),
    }


__all__ = ["posture_view", "section_view", "readiness_view", "full_report"]
