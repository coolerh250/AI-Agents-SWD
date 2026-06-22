"""Step 53 -- read-only secret management foundation API.

GET-only visibility over the COMMITTED infra/secrets catalogs. NO write
endpoints, NO read-secret-value / write-secret / rotate-secret / configure-
provider endpoint, NO store connection, NO secret/key-file read, NO user-provided
path or secret-name lookup. Every response is passed through redaction. Absent
summary -> ``status: unknown`` (never a fake PASS).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from shared.sdk.secrets_foundation import (
    foundation_view,
    full_report,
    load_secret_foundation_summary,
    readiness_view,
    redact,
    section,
)

router = APIRouter(prefix="/operations/secrets", tags=["secret-foundation"])

_SUMMARY_PATH = Path("infra/secrets/secret-foundation-summary.yaml")


def _summary() -> dict[str, Any] | None:
    return load_secret_foundation_summary(_SUMMARY_PATH)


@router.get("/foundation")
def secrets_foundation() -> dict:
    return foundation_view(_summary())


@router.get("/inventory")
def secrets_inventory() -> dict:
    return section("secret-inventory.yaml")


@router.get("/classification")
def secrets_classification() -> dict:
    return section("secret-classification.yaml")


@router.get("/ownership")
def secrets_ownership() -> dict:
    return section("secret-ownership-catalog.yaml")


@router.get("/references")
def secrets_references() -> dict:
    return {
        "identity": section("identity-secret-references.yaml"),
        "runtime": section("runtime-secret-references.yaml"),
        "backup": section("backup-secret-references.yaml"),
        "gitops": section("gitops-secret-references.yaml"),
    }


@router.get("/lifecycle")
def secrets_lifecycle() -> dict:
    return section("secret-lifecycle-model.yaml")


@router.get("/rotation")
def secrets_rotation() -> dict:
    return section("secret-rotation-model.yaml")


@router.get("/access-boundary")
def secrets_access_boundary() -> dict:
    return section("secret-access-boundary.yaml")


@router.get("/audit-model")
def secrets_audit_model() -> dict:
    return section("secret-audit-model.yaml")


@router.get("/redaction")
def secrets_redaction() -> dict:
    return section("secret-redaction-policy.yaml")


@router.get("/usage")
def secrets_usage() -> dict:
    return redact(section("secret-usage-mapping.yaml"))


@router.get("/readiness")
def secrets_readiness() -> dict:
    return readiness_view(_summary())


@router.get("/report")
def secrets_report() -> dict:
    return full_report(_summary())


__all__ = ["router"]
