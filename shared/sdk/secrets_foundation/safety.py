"""Step 53 -- flat /operations/safety secret management fields.

Booleans / enums only. Absent summary -> safe `unknown` posture;
``secrets_production_ready`` is ALWAYS false. The *_committed flags reflect a
repo scan and must all be false.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shared.sdk.secrets_foundation.secret_redaction import find_committed_secret

STATUS_UNKNOWN = "unknown"

# committed-secret probes -> (field, regex-ish reason substrings handled by detector)
_COMMITTED_FIELDS = (
    "secrets_client_secret_committed",
    "secrets_jwt_committed",
    "secrets_private_key_committed",
    "secrets_kubeconfig_committed",
    "secrets_github_token_committed",
    "secrets_argocd_token_committed",
    "secrets_registry_credential_committed",
    "secrets_backup_key_committed",
    "secrets_session_key_committed",
    "secrets_audit_key_committed",
)


def _scan_committed(root: Path) -> dict[str, bool]:
    """Scan the secrets surface for committed secret shapes. All expected false."""
    sdir = root / "infra" / "secrets"
    hits: list[str] = []
    if sdir.is_dir():
        for p in sdir.glob("*.yaml"):
            hits += find_committed_secret(p.read_text(encoding="utf-8"))
    any_hit = bool(hits)
    return {f: any_hit for f in _COMMITTED_FIELDS}


def secret_safety_fields(summary: dict[str, Any] | None, root: Path) -> dict[str, Any]:
    p = (summary or {}).get("secretFoundation", {}) if summary else {}
    status = p.get("status", STATUS_UNKNOWN)
    fields: dict[str, Any] = {
        "secrets_foundation_enabled": True,
        "secrets_foundation_status": status,
        "secrets_production_store_configured": bool(p.get("productionStoreConfigured")),
        "secrets_production_store_enabled": bool(p.get("productionStoreEnabled")),
        "secrets_read_value_enabled": bool(p.get("readValueEnabled")),
        "secrets_write_value_enabled": bool(p.get("writeValueEnabled")),
        "secrets_rotation_enabled": bool(p.get("rotationEnabled")),
        "secrets_inline_values_detected": bool(p.get("inlineValuesDetected")),
        "secrets_redaction_policy_enabled": bool(p.get("redactionPolicyEnabled")),
        "secrets_secret_refs_valid": bool(p.get("secretRefsValid")),
        "secrets_production_ready": False,
    }
    fields.update(_scan_committed(root))
    return fields


__all__ = ["secret_safety_fields"]
