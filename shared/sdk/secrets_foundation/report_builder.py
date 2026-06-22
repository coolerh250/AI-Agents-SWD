"""Step 53 -- secret foundation report builder (read-only, redacted).

Shapes the per-section views the read-only API serves, reading the committed
catalogs. Every view is passed through redaction so no secret-shaped value can
escape.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shared.sdk.secrets_foundation.collector import (
    STATUS_UNKNOWN,
    load_secret_foundation_summary,
)
from shared.sdk.secrets_foundation.secret_redaction import redact

ROOT = Path(__file__).resolve().parents[3]
_SUMMARY = ROOT / "infra" / "secrets" / "secret-foundation-summary.yaml"


def _posture(summary: dict[str, Any] | None) -> dict[str, Any]:
    return (summary or {}).get("secretFoundation", {}) if summary else {}


def _catalog(name: str, root: Path | None = None) -> dict[str, Any]:
    p = (root or ROOT) / "infra" / "secrets" / name
    if not p.is_file():
        return {}
    return redact(yaml.safe_load(p.read_text(encoding="utf-8")) or {})


def foundation_view(summary: dict[str, Any] | None) -> dict[str, Any]:
    p = _posture(summary)
    return {
        "status": p.get("status", STATUS_UNKNOWN),
        "productionReady": False,
        "productionStoreConfigured": bool(p.get("productionStoreConfigured")),
        "productionStoreEnabled": bool(p.get("productionStoreEnabled")),
        "readValueEnabled": bool(p.get("readValueEnabled")),
        "writeValueEnabled": bool(p.get("writeValueEnabled")),
        "rotationEnabled": bool(p.get("rotationEnabled")),
        "inlineValuesDetected": bool(p.get("inlineValuesDetected")),
        "redactionPolicyEnabled": bool(p.get("redactionPolicyEnabled")),
        "categoriesCovered": list(p.get("categoriesCovered", [])),
        "limitations": list(p.get("limitations", [])),
        "nextRequiredSteps": list(p.get("nextRequiredSteps", [])),
    }


def readiness_view(summary: dict[str, Any] | None) -> dict[str, Any]:
    p = _posture(summary)
    return {
        "status": p.get("status", STATUS_UNKNOWN),
        "productionReady": False,
        "productionStoreConfigured": bool(p.get("productionStoreConfigured")),
        "blockers": list(p.get("limitations", [])),
        "nextRequiredSteps": list(p.get("nextRequiredSteps", [])),
    }


def full_report(summary: dict[str, Any] | None, root: Path | None = None) -> dict[str, Any]:
    return {
        "status": _posture(summary).get("status", STATUS_UNKNOWN),
        "productionReady": False,
        "foundation": foundation_view(summary),
        "inventory": _catalog("secret-inventory.yaml", root),
        "classification": _catalog("secret-classification.yaml", root),
        "ownership": _catalog("secret-ownership-catalog.yaml", root),
        "references": {
            "identity": _catalog("identity-secret-references.yaml", root),
            "runtime": _catalog("runtime-secret-references.yaml", root),
            "backup": _catalog("backup-secret-references.yaml", root),
            "gitops": _catalog("gitops-secret-references.yaml", root),
        },
        "lifecycle": _catalog("secret-lifecycle-model.yaml", root),
        "rotation": _catalog("secret-rotation-model.yaml", root),
        "accessBoundary": _catalog("secret-access-boundary.yaml", root),
        "auditModel": _catalog("secret-audit-model.yaml", root),
        "redaction": _catalog("secret-redaction-policy.yaml", root),
        "usage": _catalog("secret-usage-mapping.yaml", root),
    }


def section(name: str, root: Path | None = None) -> dict[str, Any]:
    return _catalog(name, root)


def load_summary() -> dict[str, Any] | None:
    return load_secret_foundation_summary(_SUMMARY)


__all__ = [
    "foundation_view",
    "readiness_view",
    "full_report",
    "section",
    "load_summary",
]
