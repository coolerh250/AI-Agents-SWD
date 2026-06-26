"""Step 57 -- work-item audit / event metadata builder.

Builds redacted audit metadata for project / work-item / dispatch events per
infra/delivery/project-work-item-audit-mapping.yaml. NEVER includes a secret, token,
password, or chain-of-thought; production_executed stays false.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
AUDIT_YAML = ROOT / "infra" / "delivery" / "project-work-item-audit-mapping.yaml"

# Keys that must never appear in audit metadata.
_FORBIDDEN_KEYS = {
    "secret",
    "token",
    "password",
    "chain_of_thought",
    "raw_reasoning",
    "kubeconfig",
    "webhook",
}


@lru_cache(maxsize=1)
def _mapping() -> dict[str, Any]:
    data = yaml.safe_load(AUDIT_YAML.read_text(encoding="utf-8")) or {}
    return data.get("projectWorkItemAuditMapping", {})


def audit_event_types() -> list[str]:
    return list(_mapping().get("events", []))


def build_audit_metadata(
    *,
    event_type: str,
    actor: str,
    role: str,
    reason: str,
    project_id: str,
    work_item_id: str | None = None,
    correlation_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build redacted audit metadata; drops any forbidden keys from `extra`."""
    meta: dict[str, Any] = {
        "event_type": event_type,
        "actor": actor,
        "role": role,
        "reason": reason,
        "project_id": project_id,
        "work_item_id": work_item_id,
        "correlation_id": correlation_id,
        "production_executed": False,
    }
    for k, v in (extra or {}).items():
        if k.lower() in _FORBIDDEN_KEYS:
            continue
        meta[k] = v
    return meta
