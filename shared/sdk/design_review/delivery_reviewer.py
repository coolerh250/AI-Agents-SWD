"""Stage 46 -- delivery readiness review (deterministic, no LLM)."""

from __future__ import annotations

from shared.sdk.design_review.models import DesignReviewFinding, ReviewContext


def review_delivery(ctx: ReviewContext) -> list[DesignReviewFinding]:
    findings: list[DesignReviewFinding] = []
    wt = {str(w.get("work_type") or "") for w in ctx.work_items}
    titles = " ".join(str(w.get("title") or "") for w in ctx.work_items).lower()
    if "release" not in wt and "delivery" not in titles:
        findings.append(
            DesignReviewFinding(
                finding_key="DEL-NO-SUMMARY",
                finding_type="delivery_risk",
                severity="medium",
                title="No delivery summary work item",
                description="No release/delivery-summary work item is present in the graph.",
                recommendation="Add a delivery-summary work item.",
                created_by_agent="delivery-capability",
            )
        )
    ac = " ".join(str(c.get("description") or "") for c in ctx.acceptance_criteria).lower()
    if "readme" not in ac and "documentation" not in titles and "documentation" not in ac:
        findings.append(
            DesignReviewFinding(
                finding_key="DEL-NO-README",
                finding_type="delivery_risk",
                severity="low",
                title="README not in the delivery path",
                description="No README/documentation appears in the delivery path.",
                recommendation="Ensure README is part of delivery.",
                created_by_agent="delivery-capability",
            )
        )
    # Delivery readiness may be false now, but the path must exist (informational).
    findings.append(
        DesignReviewFinding(
            finding_key="DEL-READINESS-PENDING",
            finding_type="delivery_risk",
            severity="low",
            title="Delivery readiness pending (expected)",
            description="Delivery readiness is false pre-execution; the delivery path exists. "
            "This is expected at the planning/review stage.",
            recommendation="Re-evaluate readiness after implementation + QA.",
            status="accepted",
            created_by_agent="delivery-capability",
        )
    )
    return findings


__all__ = ["review_delivery"]
