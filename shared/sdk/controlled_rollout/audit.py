"""Step 63A -- controlled rollout review audit event builder.

Builds redacted audit metadata for each review operation. Metadata always carries actor /
role / reason / review_id / recommendation and production_ready=false /
production_approved=false / production_action_allowed=false / production_executed=false; it
never carries a token, secret, kubeconfig, raw prompt, chain-of-thought, or raw dump.
"""

from __future__ import annotations

from typing import Any

from .redaction import redact

EVENTS = (
    "controlled_rollout_review_generated",
    "controlled_rollout_criteria_evaluated",
    "controlled_rollout_target_assessed",
    "controlled_rollout_credentials_assessed",
    "controlled_rollout_gitops_assessed",
    "controlled_rollout_approval_channel_assessed",
    "controlled_rollout_recommendation_created",
    "controlled_rollout_operator_review_requested",
    "production_rollout_blocked",
)


def build_audit_metadata(
    *,
    event_type: str,
    actor: str,
    role: str,
    reason: str,
    review_id: str | None = None,
    recommendation: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if event_type not in EVENTS:
        raise ValueError(f"unknown controlled rollout review audit event: {event_type}")
    meta: dict[str, Any] = {
        "event_type": event_type,
        "actor": actor,
        "role": role,
        "reason": reason,
        "review_id": review_id,
        "recommendation": recommendation,
        "production_ready": False,
        "production_approved": False,
        "production_action_allowed": False,
        "production_executed": False,
    }
    if extra:
        meta.update(extra)
    return redact(meta)
