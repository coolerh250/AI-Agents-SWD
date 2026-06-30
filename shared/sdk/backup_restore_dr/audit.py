"""Step 61 -- backup / restore / DR audit event builder.

Builds redacted audit metadata for each backup / restore / DR governance operation.
Metadata always carries actor / role / reason / linkage / policy_decision and
production_restore=false / production_failover=false / production_executed=false; it never
carries a token, secret, raw dump, kubeconfig, or chain-of-thought.
"""

from __future__ import annotations

from typing import Any

from .redaction import redact

EVENTS = (
    "backup_inventory_generated",
    "cleanup_review_created",
    "restore_plan_created",
    "restore_validation_completed",
    "dr_readiness_evaluated",
    "recovery_evidence_collected",
    "cleanup_execution_blocked",
    "production_restore_blocked",
    "production_failover_blocked",
)


def build_audit_metadata(
    *,
    event_type: str,
    actor: str,
    role: str,
    reason: str,
    operation_id: str | None = None,
    target: str | None = None,
    target_environment: str | None = None,
    policy_decision: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if event_type not in EVENTS:
        raise ValueError(f"unknown backup/restore/DR audit event: {event_type}")
    meta: dict[str, Any] = {
        "event_type": event_type,
        "actor": actor,
        "role": role,
        "reason": reason,
        "operation_id": operation_id,
        "target": target,
        "target_environment": target_environment,
        "policy_decision": policy_decision,
        "production_restore": False,
        "production_failover": False,
        "production_executed": False,
    }
    if extra:
        meta.update(extra)
    return redact(meta)
