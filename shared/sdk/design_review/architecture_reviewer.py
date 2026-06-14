"""Stage 46 -- architecture review (deterministic, no LLM)."""

from __future__ import annotations

from shared.sdk.design_review.models import DesignReviewFinding, ReviewContext


def _work_types(ctx: ReviewContext) -> set[str]:
    return {str(w.get("work_type") or "") for w in ctx.work_items}


def review_architecture(ctx: ReviewContext) -> list[DesignReviewFinding]:
    findings: list[DesignReviewFinding] = []
    wt = _work_types(ctx)
    if "architecture" not in wt:
        findings.append(
            DesignReviewFinding(
                finding_key="ARCH-NO-DESIGN",
                finding_type="architecture_risk",
                severity="high",
                title="No architecture/design work item",
                description="The task graph has no architecture work item to define "
                "the API contract and data model.",
                recommendation="Add an architecture/data-model design work item.",
                created_by_agent="architecture-capability",
            )
        )
    if "backend" not in wt:
        findings.append(
            DesignReviewFinding(
                finding_key="ARCH-NO-BACKEND",
                finding_type="architecture_risk",
                severity="medium",
                title="No backend work item",
                description="No backend implementation work item is present.",
                recommendation="Add a backend implementation work item.",
                created_by_agent="architecture-capability",
            )
        )
    if "database" not in wt and "integration" not in wt:
        findings.append(
            DesignReviewFinding(
                finding_key="ARCH-NO-PERSISTENCE",
                finding_type="architecture_risk",
                severity="low",
                title="No explicit persistence work item",
                description="No database/persistence work item is present.",
                recommendation="Confirm persistence is covered by a work item.",
                created_by_agent="architecture-capability",
            )
        )
    if not ctx.dependencies:
        findings.append(
            DesignReviewFinding(
                finding_key="ARCH-NO-DEPS",
                finding_type="dependency_issue",
                severity="medium",
                title="Work items have no dependencies",
                description="The graph has no dependency edges; sequencing is undefined.",
                recommendation="Add dependency edges between work items.",
                created_by_agent="architecture-capability",
            )
        )
    return findings


__all__ = ["review_architecture"]
