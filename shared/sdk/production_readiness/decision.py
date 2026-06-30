"""Step 62 -- production readiness decision evaluation.

The gate's decision is NEVER production_ready / approved / action-allowed. Order:
  1. a requested production action or non-zero production_executed -> blocked_by_policy
  2. a missing required-evidence hard blocker -> blocked_by_missing_evidence
  3. evidence complete but production prerequisites missing -> ready_for_operator_review
The maximum attainable decision is ready_for_operator_review.
"""

from __future__ import annotations

from .models import (
    DECISION_BLOCKED_MISSING_EVIDENCE,
    DECISION_BLOCKED_POLICY,
    DECISION_READY_FOR_OPERATOR_REVIEW,
    BlockingRuleResult,
    ReadinessDecision,
)

_POLICY_HARD = {
    "production_action_requested",
    "production_deploy_allowed",
    "production_sync_allowed",
    "production_restore_allowed",
    "production_failover_allowed",
    "production_executed_true_count_nonzero",
}


def evaluate(
    *,
    blocking_results: list[BlockingRuleResult],
    missing_evidence: list[str] | None = None,
    missing_prerequisites: list[str] | None = None,
) -> ReadinessDecision:
    missing_evidence = missing_evidence or []
    missing_prerequisites = missing_prerequisites or []

    hard_active = [r.name for r in blocking_results if r.severity == "hard" and r.active]
    prereq_active = [r.name for r in blocking_results if r.severity == "prerequisite" and r.active]

    policy_hard = [n for n in hard_active if n in _POLICY_HARD]
    evidence_hard = [n for n in hard_active if n not in _POLICY_HARD]

    if policy_hard:
        decision = DECISION_BLOCKED_POLICY
    elif evidence_hard or missing_evidence:
        decision = DECISION_BLOCKED_MISSING_EVIDENCE
    else:
        # Evidence complete. Production prerequisites are missing, so the best attainable
        # decision is operator review (never production_ready).
        decision = DECISION_READY_FOR_OPERATOR_REVIEW

    return ReadinessDecision(
        decision=decision,
        production_ready=False,
        production_approved=False,
        production_action_allowed=False,
        hard_blockers=hard_active,
        prerequisite_blockers=prereq_active,
        missing_evidence=missing_evidence,
    )
