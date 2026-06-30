"""Step 61 -- non-production restore validation builder.

Validation is safe and non-destructive: metadata / schema / redaction / freshness checks
and at most a dry-run. It never overwrites an active Postgres or Redis, never triggers an
ArgoCD sync, and never mutates the kind cluster. A production target environment or an
arbitrary restore path is blocked. Validation failure is reported, never hidden.
"""

from __future__ import annotations

import uuid

from . import policy
from .models import VALIDATION_TYPES, RestoreValidationResult


def build_restore_validation_result(
    *,
    restore_plan_id: str | None,
    target_environment: str | None = None,
    validation_types: list[str] | None = None,
    checks: list[dict] | None = None,
    missing: list[str] | None = None,
) -> RestoreValidationResult:
    """Build a restore validation result. Never overwrites active runtime."""
    requested = [v for v in (validation_types or []) if v in VALIDATION_TYPES]
    env, env_blocked = policy.validate_environment(target_environment)

    result = RestoreValidationResult(
        validation_id=uuid.uuid4().hex,
        restore_plan_id=restore_plan_id,
        validation_types=requested,
        checks=list(checks or []),
        missing=list(missing or []),
    )

    if env_blocked:
        result.status = "blocked"
        result.missing.append(env_blocked)
        return result
    if not requested:
        result.status = "blocked"
        result.missing.append("no_known_validation_type")
        return result
    if result.missing or any(not c.get("passed", False) for c in result.checks):
        result.status = "failed"
        return result
    result.status = "passed"
    return result
