"""Step 60 -- release readiness evaluation.

Readiness is a governance judgement, never a production approval. production_ready is
always false. Any production target, missing evidence, missing rollback, security/policy
violation, unhealthy runtime/GitOps, or unreviewed sandbox PR blocks readiness.
"""

from __future__ import annotations

from typing import Any

from . import policy
from .models import ReadinessResult


def evaluate(
    *,
    target_environment: str | None,
    evidence: dict[str, Any] | None = None,
    rollback_present: bool = False,
    security_status: str = "unknown",
    runtime_status: str = "unknown",
    gitops_status: str = "unknown",
    sandbox_pr_reviewed: bool = False,
    approval_granted: bool = False,
) -> ReadinessResult:
    evidence = evidence or {}
    blockers: list[str] = []
    missing: list[str] = []

    env, env_blocked = policy.validate_environment(target_environment)
    if env_blocked:
        # A production target is an immediate hard block.
        return ReadinessResult(
            decision="blocked_by_policy",
            production_ready=False,
            blockers=[env_blocked],
        )

    if security_status not in ("pass", "ready", "ok"):
        blockers.append("missing_or_failing_security_evidence")
    if not evidence.get("security_readiness"):
        missing.append("security_readiness")
    if not rollback_present or not evidence.get("rollback_plan"):
        missing.append("rollback_plan")
    if not evidence.get("audit_events"):
        missing.append("audit_linkage")
    if runtime_status not in ("available", "healthy", "ready", "pass"):
        blockers.append("runtime_unavailable_for_target")
    if gitops_status not in ("healthy", "synced", "ready", "pass"):
        blockers.append("gitops_unhealthy")
    if not sandbox_pr_reviewed:
        blockers.append("sandbox_pr_not_reviewed_or_merged")

    if missing:
        return ReadinessResult(
            decision="blocked_by_missing_evidence",
            production_ready=False,
            blockers=blockers,
            missing_evidence=missing,
        )
    if "missing_or_failing_security_evidence" in blockers:
        return ReadinessResult(
            decision="blocked_by_security", production_ready=False, blockers=blockers
        )
    if blockers:
        return ReadinessResult(decision="not_ready", production_ready=False, blockers=blockers)

    # Everything present for the non-production target -> ready for operator review (NOT a
    # production approval, NOT an auto-accept).
    return ReadinessResult(decision="ready_for_operator_review", production_ready=False)
