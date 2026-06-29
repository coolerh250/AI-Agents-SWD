"""Step 60 -- release governance audit event builder.

Builds redacted audit metadata for each release governance operation. Metadata always
carries actor / role / reason / linkage / policy_decision and production_executed=false;
it never carries a token, secret, raw prompt, or chain-of-thought.
"""

from __future__ import annotations

from typing import Any

from .redaction import redact

EVENTS = (
    "release_candidate_created",
    "release_evidence_collected",
    "release_readiness_evaluated",
    "deployment_intent_created",
    "deployment_intent_blocked",
    "release_operator_review_requested",
    "release_candidate_archived",
)


def build_audit_metadata(
    *,
    event_type: str,
    actor: str,
    role: str,
    reason: str,
    project_id: str | None = None,
    candidate_id: str | None = None,
    deployment_intent_id: str | None = None,
    target_environment: str | None = None,
    policy_decision: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if event_type not in EVENTS:
        raise ValueError(f"unknown release governance audit event: {event_type}")
    meta: dict[str, Any] = {
        "event_type": event_type,
        "actor": actor,
        "role": role,
        "reason": reason,
        "project_id": project_id,
        "candidate_id": candidate_id,
        "deployment_intent_id": deployment_intent_id,
        "target_environment": target_environment,
        "policy_decision": policy_decision,
        "production_executed": False,
    }
    if extra:
        meta.update(extra)
    return redact(meta)
