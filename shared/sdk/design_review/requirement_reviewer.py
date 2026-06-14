"""Stage 46 -- requirement review (deterministic, no LLM)."""

from __future__ import annotations

from shared.sdk.design_review.models import DesignReviewFinding, ReviewContext


def _ac_text(ctx: ReviewContext) -> str:
    return " ".join(str(c.get("description") or "") for c in ctx.acceptance_criteria).lower()


def review_requirements(ctx: ReviewContext) -> list[DesignReviewFinding]:
    findings: list[DesignReviewFinding] = []
    brief = ctx.brief or {}
    if not brief.get("scope"):
        findings.append(
            DesignReviewFinding(
                finding_key="REQ-SCOPE",
                finding_type="requirement_gap",
                severity="high",
                title="Project scope missing",
                description="The project brief does not declare a scope.",
                recommendation="Author scope before implementation.",
                created_by_agent="requirement-agent",
            )
        )
    if not brief.get("non_scope"):
        findings.append(
            DesignReviewFinding(
                finding_key="REQ-NONSCOPE",
                finding_type="scope_risk",
                severity="medium",
                title="Non-scope not declared",
                description="The brief does not declare non-scope; scope-creep risk.",
                recommendation="Declare non-scope explicitly.",
                created_by_agent="requirement-agent",
            )
        )
    if not ctx.user_stories:
        findings.append(
            DesignReviewFinding(
                finding_key="REQ-STORIES",
                finding_type="requirement_gap",
                severity="medium",
                title="No user stories",
                description="No user stories were generated for the project.",
                recommendation="Generate user stories from the brief.",
                created_by_agent="requirement-agent",
            )
        )
    ac = _ac_text(ctx)
    # CRUD / tests / docs coverage signal (low severity informational gaps).
    if not any(k in ac for k in ("create", "list", "get", "update", "delete")):
        findings.append(
            DesignReviewFinding(
                finding_key="REQ-CRUD-COVERAGE",
                finding_type="acceptance_gap",
                severity="medium",
                title="Acceptance criteria do not cover CRUD",
                description="No acceptance criterion references CRUD operations.",
                recommendation="Add CRUD acceptance criteria.",
                created_by_agent="requirement-agent",
            )
        )
    if "test" not in ac and "pytest" not in ac:
        findings.append(
            DesignReviewFinding(
                finding_key="REQ-TEST-COVERAGE",
                finding_type="qa_gap",
                severity="medium",
                title="Acceptance criteria do not reference tests",
                description="No acceptance criterion references a test suite.",
                recommendation="Add a test-passing acceptance criterion.",
                created_by_agent="requirement-agent",
            )
        )
    if not any(k in ac for k in ("readme", "document", "doc")):
        findings.append(
            DesignReviewFinding(
                finding_key="REQ-DOC-COVERAGE",
                finding_type="requirement_gap",
                severity="low",
                title="Acceptance criteria do not reference documentation",
                description="No acceptance criterion references README/docs.",
                recommendation="Add a documentation acceptance criterion.",
                created_by_agent="requirement-agent",
            )
        )
    if brief.get("requires_clarification") or brief.get("metadata", {}).get(
        "requires_clarification"
    ):
        findings.append(
            DesignReviewFinding(
                finding_key="REQ-CLARIFY",
                finding_type="requirement_gap",
                severity="high",
                title="Clarification required",
                description="The brief was flagged as requiring clarification.",
                recommendation="Resolve clarification before review.",
                created_by_agent="requirement-agent",
            )
        )
    return findings


__all__ = ["review_requirements"]
