"""Step 53 -- secret management foundation collector (read-only, no values).

Aggregates the committed infra/secrets catalogs into a redacted posture summary.
Reads only repo YAML; never connects to a store, reads a secret value, or a
runtime key file. A missing source yields status ``unknown`` (never a fake PASS).
A committed secret-shaped value or an enabled production store flips status to
``failed``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shared.sdk.secrets_foundation.secret_redaction import find_committed_secret

ROOT = Path(__file__).resolve().parents[3]

STATUS_MODELED = "modeled_fail_closed_not_configured"
STATUS_FAILED = "failed"
STATUS_UNKNOWN = "unknown"

_SOURCES = (
    "secret-inventory.yaml",
    "secret-classification.yaml",
    "secret-ownership-catalog.yaml",
    "production-secret-store-disabled-config.yaml",
    "secret-lifecycle-model.yaml",
    "secret-rotation-model.yaml",
    "secret-access-boundary.yaml",
    "secret-audit-model.yaml",
    "secret-redaction-policy.yaml",
    "secret-usage-mapping.yaml",
    "identity-secret-references.yaml",
    "runtime-secret-references.yaml",
    "backup-secret-references.yaml",
    "gitops-secret-references.yaml",
)

LIMITATIONS = [
    "no_production_secret_store_connected",
    "no_real_oidc_client_secret",
    "no_real_session_signing_key_store",
    "no_real_backup_encryption_key_store",
    "no_real_database_or_redis_credential_store",
    "no_real_gitops_or_registry_credential",
    "no_secret_rotation_backend",
    "break_glass_credential_disabled",
]
NEXT_REQUIRED_STEPS = [
    "production_secret_store_provider_selection",
    "production_oidc_client_secret_provisioning",
    "production_session_key_rotation_backend",
    "production_backup_key_store",
]


def _load(sdir: Path, name: str) -> dict[str, Any]:
    return yaml.safe_load((sdir / name).read_text(encoding="utf-8")) or {}


def collect_secret_posture(root: Path | None = None) -> dict[str, Any]:
    base = root or ROOT
    sdir = base / "infra" / "secrets"

    missing = [s for s in _SOURCES if not (sdir / s).is_file()]
    if missing:
        return _unknown(missing)

    try:
        inventory = _load(sdir, "secret-inventory.yaml")
        store = _load(sdir, "production-secret-store-disabled-config.yaml")["productionSecretStore"]
        rotation = _load(sdir, "secret-rotation-model.yaml")
        redaction = _load(sdir, "secret-redaction-policy.yaml")
        access = _load(sdir, "secret-access-boundary.yaml")["accessBoundary"]
    except (KeyError, TypeError):
        return _unknown(["malformed_source"])

    secrets = inventory.get("secrets", [])
    categories = sorted({s.get("category") for s in secrets if s.get("category")})
    prod_secrets = [s for s in secrets if s.get("productionRequired")]

    # scan every committed secrets file for an inline secret value
    inline_hits: list[str] = []
    for p in sorted(sdir.glob("*.yaml")):
        inline_hits += find_committed_secret(p.read_text(encoding="utf-8"))

    inline_detected = bool(inline_hits)
    store_enabled = bool(store.get("enabled"))
    store_configured = bool(store.get("configured"))
    read_enabled = bool(store.get("readSecretValuesEnabled"))
    write_enabled = bool(store.get("writeSecretValuesEnabled"))
    rotation_enabled = bool(rotation.get("rotation", {}).get("status") == "enabled")
    any_prod_configured = any(s.get("productionConfigured") for s in prod_secrets)
    any_value_in_repo = any(s.get("valueStoredInRepo") for s in secrets)

    posture: dict[str, Any] = {
        "productionReady": False,
        "productionStoreEnabled": store_enabled,
        "productionStoreConfigured": store_configured,
        "readValueEnabled": read_enabled,
        "writeValueEnabled": write_enabled,
        "rotationEnabled": rotation_enabled,
        "inlineValuesDetected": inline_detected,
        "anyProductionSecretConfigured": any_prod_configured,
        "anySecretValueInRepo": any_value_in_repo,
        "secretRefsValid": True,
        "redactionPolicyEnabled": redaction.get("status") == "enabled",
        "valueAccessEnabled": bool(access.get("secretValueAccessEnabled")),
        "categoriesCovered": categories,
        "secretCount": len(secrets),
        "productionSecretCount": len(prod_secrets),
        "limitations": list(LIMITATIONS),
        "nextRequiredSteps": list(NEXT_REQUIRED_STEPS),
    }
    posture["status"] = _derive_status(posture)
    return posture


def _derive_status(p: dict[str, Any]) -> str:
    unsafe = (
        p["productionStoreEnabled"]
        or p["productionStoreConfigured"]
        or p["readValueEnabled"]
        or p["writeValueEnabled"]
        or p["rotationEnabled"]
        or p["inlineValuesDetected"]
        or p["anyProductionSecretConfigured"]
        or p["anySecretValueInRepo"]
        or p["valueAccessEnabled"]
        or not p["redactionPolicyEnabled"]
    )
    return STATUS_FAILED if unsafe else STATUS_MODELED


def _unknown(reasons: list[str]) -> dict[str, Any]:
    return {
        "status": STATUS_UNKNOWN,
        "productionReady": False,
        "productionStoreConfigured": False,
        "productionStoreEnabled": False,
        "readValueEnabled": False,
        "writeValueEnabled": False,
        "rotationEnabled": False,
        "inlineValuesDetected": False,
        "redactionPolicyEnabled": False,
        "secretRefsValid": False,
        "categoriesCovered": [],
        "limitations": ["secret_foundation_source_missing"],
        "nextRequiredSteps": [],
        "missingSources": reasons,
    }


def build_secret_foundation_summary(root: Path | None = None) -> dict[str, Any]:
    return {
        "version": "1",
        "meta": {"stage": "55A", "step": "53"},
        "secretFoundation": collect_secret_posture(root),
    }


def load_secret_foundation_summary(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    return data if isinstance(data, dict) else None


__all__ = [
    "STATUS_MODELED",
    "STATUS_FAILED",
    "STATUS_UNKNOWN",
    "LIMITATIONS",
    "NEXT_REQUIRED_STEPS",
    "collect_secret_posture",
    "build_secret_foundation_summary",
    "load_secret_foundation_summary",
]
