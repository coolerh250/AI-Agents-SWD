"""Stage 46 -- implementation strategy review (deterministic, no LLM)."""

from __future__ import annotations

from shared.sdk.design_review.models import DesignReviewFinding, ReviewContext

_RUNNABLE_ROLES = {"requirement-agent", "development-agent", "qa-agent", "devops-agent"}


def review_implementation(ctx: ReviewContext) -> list[DesignReviewFinding]:
    findings: list[DesignReviewFinding] = []
    if ctx.graph_validation_status == "invalid":
        findings.append(
            DesignReviewFinding(
                finding_key="IMPL-GRAPH-INVALID",
                finding_type="dependency_issue",
                severity="critical",
                title="Task graph is invalid",
                description="The project graph failed dependency validation; it cannot "
                "be executed.",
                recommendation="Fix the dependency graph before any execution.",
                created_by_agent="development-agent",
            )
        )

    dev_items = [w for w in ctx.work_items if w.get("assigned_agent_role") == "development-agent"]
    mapped_wi = {c.get("work_item_id") for c in ctx.acceptance_criteria if c.get("work_item_id")}
    if dev_items and not any(w.get("id") in mapped_wi for w in dev_items):
        # Only flag when NO development work item is covered by any acceptance
        # criterion (a per-item check would be noise -- scaffolding items
        # legitimately have no direct criterion).
        findings.append(
            DesignReviewFinding(
                finding_key="IMPL-NO-AC-COVERAGE",
                finding_type="implementation_risk",
                severity="medium",
                title="No development work item is mapped to an acceptance criterion",
                description="None of the development-agent work items are mapped to an "
                "acceptance criterion.",
                recommendation="Map at least the core implementation work item to an "
                "acceptance criterion.",
                created_by_agent="development-agent",
            )
        )
    if not dev_items:
        findings.append(
            DesignReviewFinding(
                finding_key="IMPL-NO-DEV-ITEMS",
                finding_type="implementation_risk",
                severity="medium",
                title="No development work items",
                description="The graph has no development-agent work items.",
                recommendation="Add implementation work items.",
                created_by_agent="development-agent",
            )
        )
    # Future roles must remain planning-only (informational, never blocking).
    future_items = [
        w
        for w in ctx.work_items
        if w.get("assigned_agent_role") and w["assigned_agent_role"] not in _RUNNABLE_ROLES
    ]
    for w in future_items:
        if w.get("dispatch_policy") not in ("planning_only", "approval_required"):
            findings.append(
                DesignReviewFinding(
                    finding_key=f"IMPL-FUTURE-ROLE-{w.get('work_item_key', 'x')}",
                    finding_type="implementation_risk",
                    severity="medium",
                    title="Future-role work item is not planning-only",
                    description=f"Work item {w.get('work_item_key')} is assigned to a "
                    "future role but is not planning-only/approval-required.",
                    recommendation="Keep future-role work items planning-only.",
                    work_item_key=w.get("work_item_key"),
                    created_by_agent="development-agent",
                )
            )
    return findings


__all__ = ["review_implementation"]
