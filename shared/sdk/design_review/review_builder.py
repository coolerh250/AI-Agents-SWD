"""Stage 46 -- aggregate all reviewers into one design review result (pure)."""

from __future__ import annotations

from dataclasses import dataclass, field

from shared.sdk.design_review.acceptance_coverage import (
    AcceptanceCoverage,
    review_acceptance_coverage,
)
from shared.sdk.design_review.architecture_reviewer import review_architecture
from shared.sdk.design_review.delivery_reviewer import review_delivery
from shared.sdk.design_review.gate_evaluator import (
    build_decisions,
    decide_go_no_go,
    evaluate_gates,
)
from shared.sdk.design_review.implementation_reviewer import review_implementation
from shared.sdk.design_review.models import (
    DesignReviewDecision,
    DesignReviewFinding,
    GoNoGoSummary,
    ProjectReviewGate,
    ReviewContext,
)
from shared.sdk.design_review.qa_reviewer import review_qa
from shared.sdk.design_review.requirement_reviewer import review_requirements
from shared.sdk.design_review.security_reviewer import review_security


@dataclass
class ReviewResult:
    findings: list[DesignReviewFinding]
    gates: list[ProjectReviewGate]
    decisions: list[DesignReviewDecision]
    summary: GoNoGoSummary
    coverage: AcceptanceCoverage
    status: str
    decision: str = field(default="planning_only")


def build_review(
    ctx: ReviewContext,
    *,
    planning_only: bool = True,
    work_item_dispatch_enabled: bool = False,
) -> ReviewResult:
    findings: list[DesignReviewFinding] = []
    findings += review_requirements(ctx)
    findings += review_architecture(ctx)
    findings += review_implementation(ctx)
    findings += review_qa(ctx)
    findings += review_security(ctx)
    findings += review_delivery(ctx)
    coverage, cov_findings = review_acceptance_coverage(ctx)
    findings += cov_findings

    gates = evaluate_gates(ctx, findings, work_item_dispatch_enabled=work_item_dispatch_enabled)
    status, decision, summary = decide_go_no_go(
        ctx,
        findings,
        gates,
        planning_only=planning_only,
        work_item_dispatch_enabled=work_item_dispatch_enabled,
    )
    decisions = build_decisions(decision, summary)
    return ReviewResult(
        findings=findings,
        gates=gates,
        decisions=decisions,
        summary=summary,
        coverage=coverage,
        status=status,
        decision=decision,
    )


__all__ = ["ReviewResult", "build_review"]
