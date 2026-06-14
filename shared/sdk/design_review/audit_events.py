"""Stage 46 -- design review audit decision_type constants + safe refs."""

from __future__ import annotations

DECISION_DESIGN_REVIEW_STARTED = "design_review_started"
DECISION_DESIGN_REVIEW_COMPLETED = "design_review_completed"
DECISION_DESIGN_REVIEW_FINDING_CREATED = "design_review_finding_created"
DECISION_DESIGN_REVIEW_GATE_EVALUATED = "design_review_gate_evaluated"
DECISION_DESIGN_REVIEW_GO_NO_GO_RECORDED = "design_review_go_no_go_recorded"
DECISION_DESIGN_REVIEW_BLOCKED = "design_review_blocked"

DESIGN_REVIEW_DECISION_TYPES: tuple[str, ...] = (
    DECISION_DESIGN_REVIEW_STARTED,
    DECISION_DESIGN_REVIEW_COMPLETED,
    DECISION_DESIGN_REVIEW_FINDING_CREATED,
    DECISION_DESIGN_REVIEW_GATE_EVALUATED,
    DECISION_DESIGN_REVIEW_GO_NO_GO_RECORDED,
    DECISION_DESIGN_REVIEW_BLOCKED,
)


def safe_review_artifact_refs(
    *,
    project_id: str,
    review_session_id: str | None = None,
    discussion_session_id: str | None = None,
    decision: str | None = None,
    findings_count: int | None = None,
    blocking_findings_count: int | None = None,
    gates_count: int | None = None,
) -> dict:
    refs: dict = {
        "project_id": project_id,
        "planning_only": True,
        "production_executed": False,
    }
    if review_session_id is not None:
        refs["review_session_id"] = review_session_id
    if discussion_session_id is not None:
        refs["discussion_session_id"] = discussion_session_id
    if decision is not None:
        refs["decision"] = decision
    if findings_count is not None:
        refs["findings_count"] = int(findings_count)
    if blocking_findings_count is not None:
        refs["blocking_findings_count"] = int(blocking_findings_count)
    if gates_count is not None:
        refs["gates_count"] = int(gates_count)
    return refs


__all__ = [
    "DECISION_DESIGN_REVIEW_STARTED",
    "DECISION_DESIGN_REVIEW_COMPLETED",
    "DECISION_DESIGN_REVIEW_FINDING_CREATED",
    "DECISION_DESIGN_REVIEW_GATE_EVALUATED",
    "DECISION_DESIGN_REVIEW_GO_NO_GO_RECORDED",
    "DECISION_DESIGN_REVIEW_BLOCKED",
    "DESIGN_REVIEW_DECISION_TYPES",
    "safe_review_artifact_refs",
]
