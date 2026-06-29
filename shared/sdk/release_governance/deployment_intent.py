"""Step 60 -- deployment intent builder.

A deployment intent never executes a deployment. It validates the requested action +
target environment against the policy. Production targets and any forbidden (deploy /
sync / merge / push / release / tag) action are blocked.
"""

from __future__ import annotations

import uuid

from . import policy
from .models import (
    ACTION_REQUEST_OPERATOR_REVIEW,
    ACTION_VALIDATE_ONLY,
    ALLOWED_ACTIONS,
    FORBIDDEN_ACTIONS,
    DeploymentIntent,
)


def build_intent(
    *,
    release_candidate_id: str,
    requested_action: str,
    target_environment: str | None = None,
    target_runtime: str | None = None,
    target_gitops_application: str | None = None,
) -> DeploymentIntent:
    """Build + classify a deployment intent. Never executes anything."""
    action = (requested_action or "").strip()
    env, env_blocked = policy.validate_environment(target_environment)

    intent = DeploymentIntent(
        deployment_intent_id=uuid.uuid4().hex,
        release_candidate_id=release_candidate_id,
        target_environment=env,
        requested_action=action,
        target_runtime=target_runtime,
        target_gitops_application=target_gitops_application,
    )

    # Forbidden action -> blocked.
    if action in FORBIDDEN_ACTIONS:
        intent.status = "blocked"
        intent.policy_decision = "blocked"
        intent.blocked_reason = f"forbidden_action:{action}"
        return intent
    if action not in ALLOWED_ACTIONS:
        intent.status = "blocked"
        intent.policy_decision = "blocked"
        intent.blocked_reason = f"unknown_action:{action}"
        return intent

    # Production / disallowed environment -> blocked.
    if env_blocked:
        intent.status = "blocked"
        intent.policy_decision = "blocked"
        intent.blocked_reason = env_blocked
        return intent

    # Allowed, non-production: validate-only/prepare pass; operator-review requested
    # (which is NOT an approval).
    if action == ACTION_REQUEST_OPERATOR_REVIEW:
        intent.status = "operator_review_requested"
        intent.policy_decision = "operator_review_requested"
        intent.requires_human_approval = True
    elif action == ACTION_VALIDATE_ONLY:
        intent.status = "validated"
        intent.policy_decision = "allowed_nonproduction"
    else:  # prepare_nonproduction
        intent.status = "validated"
        intent.policy_decision = "allowed_nonproduction"
        intent.requires_human_approval = True
    return intent
