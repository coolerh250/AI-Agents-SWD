"""Stage 46 -- acceptance-criteria coverage analysis."""

from __future__ import annotations

from dataclasses import dataclass

from shared.sdk.design_review.models import DesignReviewFinding, ReviewContext


@dataclass
class AcceptanceCoverage:
    total: int
    required: int
    mapped: int
    unmapped: int
    coverage_percent: float

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "required": self.required,
            "mapped": self.mapped,
            "unmapped": self.unmapped,
            "coverage_percent": self.coverage_percent,
        }


def compute_acceptance_coverage(ctx: ReviewContext) -> AcceptanceCoverage:
    criteria = ctx.acceptance_criteria
    total = len(criteria)
    required = len([c for c in criteria if c.get("required")])
    mapped = len([c for c in criteria if c.get("work_item_id")])
    unmapped = total - mapped
    coverage = round((mapped / total) * 100, 1) if total else 0.0
    return AcceptanceCoverage(
        total=total, required=required, mapped=mapped, unmapped=unmapped, coverage_percent=coverage
    )


def review_acceptance_coverage(
    ctx: ReviewContext,
) -> tuple[AcceptanceCoverage, list[DesignReviewFinding]]:
    cov = compute_acceptance_coverage(ctx)
    findings: list[DesignReviewFinding] = []
    if cov.required == 0:
        findings.append(
            DesignReviewFinding(
                finding_key="AC-NONE-REQUIRED",
                finding_type="acceptance_gap",
                severity="high",
                title="No required acceptance criteria",
                description="The project has no required acceptance criteria.",
                recommendation="Author required acceptance criteria.",
                created_by_agent="qa-agent",
            )
        )
    elif cov.coverage_percent < 50.0:
        findings.append(
            DesignReviewFinding(
                finding_key="AC-LOW-COVERAGE",
                finding_type="acceptance_gap",
                severity="medium",
                title="Low acceptance-criteria coverage",
                description=f"Only {cov.coverage_percent}% of acceptance criteria are mapped "
                "to work items.",
                recommendation="Map more acceptance criteria to work items.",
                created_by_agent="qa-agent",
            )
        )
    return cov, findings


__all__ = ["AcceptanceCoverage", "compute_acceptance_coverage", "review_acceptance_coverage"]
