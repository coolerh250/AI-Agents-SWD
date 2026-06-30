"""Step 61 -- restore plan builder.

A restore plan never executes a restore. It validates the restore type + target
environment against the policy. A production target environment and any forbidden restore
type (production / overwrite / failover / customer data) are blocked. production_restore is
always false.
"""

from __future__ import annotations

import uuid

from . import policy
from .models import FORBIDDEN_RESTORE_TYPES, RESTORE_TYPES, RestorePlan


class RestorePlanError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def build_restore_plan(
    *,
    target: str,
    restore_type: str,
    target_environment: str | None = None,
    source_artifact: str | None = None,
) -> RestorePlan:
    """Build + classify a restore plan. Never executes a restore."""
    rtype = (restore_type or "").strip()
    env, env_blocked = policy.validate_environment(target_environment)

    plan = RestorePlan(
        restore_plan_id=uuid.uuid4().hex,
        target=target,
        source_artifact=source_artifact,
        target_environment=env,
        restore_type=rtype,
    )

    if rtype in FORBIDDEN_RESTORE_TYPES:
        plan.status = "blocked"
        plan.policy_decision = "blocked"
        plan.blocked_reason = f"forbidden_restore_type:{rtype}"
        return plan
    if rtype not in RESTORE_TYPES:
        plan.status = "blocked"
        plan.policy_decision = "blocked"
        plan.blocked_reason = f"unknown_restore_type:{rtype}"
        return plan
    if env_blocked:
        plan.status = "blocked"
        plan.policy_decision = "blocked"
        plan.blocked_reason = env_blocked
        return plan

    # Allowed, non-production: planned, validation + rollback required, human approval for
    # the copy-restore variant (which is still NOT a production restore).
    plan.status = "planned"
    plan.policy_decision = "allowed_nonproduction"
    plan.requires_human_approval = rtype == "restore_nonproduction_copy"
    return plan
