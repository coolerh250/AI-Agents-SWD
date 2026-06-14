"""Stage 46 -- QA strategy review (deterministic, no LLM)."""

from __future__ import annotations

from shared.sdk.design_review.models import DesignReviewFinding, ReviewContext


def review_qa(ctx: ReviewContext) -> list[DesignReviewFinding]:
    findings: list[DesignReviewFinding] = []
    wt = {str(w.get("work_type") or "") for w in ctx.work_items}
    if "qa" not in wt:
        findings.append(
            DesignReviewFinding(
                finding_key="QA-NO-WORK-ITEM",
                finding_type="qa_gap",
                severity="high",
                title="No QA work item",
                description="The task graph has no QA work item.",
                recommendation="Add a QA work item that runs the tests.",
                created_by_agent="qa-agent",
            )
        )
    ac = " ".join(str(c.get("description") or "") for c in ctx.acceptance_criteria).lower()
    methods = {str(c.get("verification_method") or "") for c in ctx.acceptance_criteria}
    if "pytest" not in ac and "unit_test" not in methods and "integration_test" not in methods:
        findings.append(
            DesignReviewFinding(
                finding_key="QA-NO-TESTS",
                finding_type="qa_gap",
                severity="medium",
                title="No test-based acceptance criteria",
                description="No acceptance criterion is verified by unit/integration tests.",
                recommendation="Add test-verified acceptance criteria (pytest).",
                created_by_agent="qa-agent",
            )
        )
    if "documentation_review" not in methods and "readme" not in ac:
        findings.append(
            DesignReviewFinding(
                finding_key="QA-NO-DOC-REVIEW",
                finding_type="qa_gap",
                severity="low",
                title="No documentation review criterion",
                description="No acceptance criterion covers documentation review.",
                recommendation="Add a documentation-review acceptance criterion.",
                created_by_agent="qa-agent",
            )
        )
    return findings


__all__ = ["review_qa"]
