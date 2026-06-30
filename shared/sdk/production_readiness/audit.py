"""Step 62 -- production readiness audit event builder.

Builds redacted audit metadata for each readiness operation. Metadata always carries
actor / role / reason / readiness_gate_id / decision_status and production_ready=false /
production_approved=false / production_action_allowed=false / production_executed=false; it
never carries a token, secret, kubeconfig, raw prompt, chain-of-thought, or raw dump.
"""

from __future__ import annotations

from typing import Any

from .redaction import redact

EVENTS = (
    "production_readiness_report_generated",
    "production_readiness_evidence_collected",
    "production_readiness_blocking_rules_evaluated",
    "production_readiness_decision_created",
    "operator_review_package_created",
    "operator_review_requested",
    "production_action_blocked",
)


def build_audit_metadata(
    *,
    event_type: str,
    actor: str,
    role: str,
    reason: str,
    readiness_gate_id: str | None = None,
    decision_status: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if event_type not in EVENTS:
        raise ValueError(f"unknown production readiness audit event: {event_type}")
    meta: dict[str, Any] = {
        "event_type": event_type,
        "actor": actor,
        "role": role,
        "reason": reason,
        "readiness_gate_id": readiness_gate_id,
        "decision_status": decision_status,
        "production_ready": False,
        "production_approved": False,
        "production_action_allowed": False,
        "production_executed": False,
    }
    if extra:
        meta.update(extra)
    return redact(meta)
