"""Stage 46 -- design review summary report builder (no secrets/CoT)."""

from __future__ import annotations

from shared.sdk.design_review.review_builder import ReviewResult


def build_review_summary(
    *,
    project_id: str,
    review_session_id: str | None,
    result: ReviewResult,
    next_suggested_stage: str | None = None,
) -> dict:
    """Build a redacted design-review summary artifact (dict)."""
    return {
        "project_id": project_id,
        "review_session_id": review_session_id,
        "decision": result.decision,
        "status": result.status,
        "gates": [{"gate_type": g.gate_type, "status": g.status} for g in result.gates],
        "findings_summary": {
            "total": len(result.findings),
            "blocking": result.summary.blocking_findings_count,
            "by_severity": _by_severity(result),
        },
        "recommendations": [f.recommendation for f in result.findings if f.recommendation][:10],
        "acceptance_coverage": result.coverage.to_dict(),
        "next_suggested_stage": next_suggested_stage or result.summary.next_suggested_stage,
        "planning_only": True,
        "production_executed": False,
    }


def _by_severity(result: ReviewResult) -> dict[str, int]:
    out = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for f in result.findings:
        if f.severity in out:
            out[f.severity] += 1
    return out


__all__ = ["build_review_summary"]
