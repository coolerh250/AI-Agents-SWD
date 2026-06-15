"""Stage 48 -- mini delivery pilot audit decision_type constants + safe refs."""

from __future__ import annotations

DECISION_MINI_DELIVERY_PILOT_STARTED = "mini_delivery_pilot_started"
DECISION_MINI_DELIVERY_PILOT_STEP_COMPLETED = "mini_delivery_pilot_step_completed"
DECISION_MINI_DELIVERY_ACCEPTANCE_EVALUATED = "mini_delivery_acceptance_evaluated"
DECISION_MINI_DELIVERY_QA_EVALUATED = "mini_delivery_qa_evaluated"
DECISION_MINI_DELIVERY_SAFETY_EVALUATED = "mini_delivery_safety_evaluated"
DECISION_MINI_DELIVERY_REPORT_CREATED = "mini_delivery_report_created"
DECISION_MINI_DELIVERY_PILOT_COMPLETED = "mini_delivery_pilot_completed"
DECISION_MINI_DELIVERY_PILOT_FAILED = "mini_delivery_pilot_failed"

MINI_DELIVERY_DECISION_TYPES: tuple[str, ...] = (
    DECISION_MINI_DELIVERY_PILOT_STARTED,
    DECISION_MINI_DELIVERY_PILOT_STEP_COMPLETED,
    DECISION_MINI_DELIVERY_ACCEPTANCE_EVALUATED,
    DECISION_MINI_DELIVERY_QA_EVALUATED,
    DECISION_MINI_DELIVERY_SAFETY_EVALUATED,
    DECISION_MINI_DELIVERY_REPORT_CREATED,
    DECISION_MINI_DELIVERY_PILOT_COMPLETED,
    DECISION_MINI_DELIVERY_PILOT_FAILED,
)


def safe_pilot_artifact_refs(
    *,
    pilot_id: str | None = None,
    pilot_key: str | None = None,
    project_id: str | None = None,
    workspace_id: str | None = None,
    design_review_session_id: str | None = None,
    status: str | None = None,
    step_key: str | None = None,
    acceptance_total: int | None = None,
    acceptance_satisfied: int | None = None,
    qa_status: str | None = None,
    safety_status: str | None = None,
) -> dict:
    """Audit ``artifact_refs`` carrying only opaque ids, counts, and statuses --
    never file content, secrets, or chain-of-thought."""
    refs: dict = {
        "controlled_only": True,
        "production_executed": False,
        "github_write_performed": False,
        "pr_created": False,
        "deployment_performed": False,
        "real_llm_used": False,
    }
    for k, v in (
        ("pilot_id", pilot_id),
        ("pilot_key", pilot_key),
        ("project_id", project_id),
        ("workspace_id", workspace_id),
        ("design_review_session_id", design_review_session_id),
        ("status", status),
        ("step_key", step_key),
        ("qa_status", qa_status),
        ("safety_status", safety_status),
    ):
        if v is not None:
            refs[k] = v
    for ik, iv in (
        ("acceptance_total", acceptance_total),
        ("acceptance_satisfied", acceptance_satisfied),
    ):
        if iv is not None:
            refs[ik] = int(iv)
    return refs


__all__ = [
    "DECISION_MINI_DELIVERY_PILOT_STARTED",
    "DECISION_MINI_DELIVERY_PILOT_STEP_COMPLETED",
    "DECISION_MINI_DELIVERY_ACCEPTANCE_EVALUATED",
    "DECISION_MINI_DELIVERY_QA_EVALUATED",
    "DECISION_MINI_DELIVERY_SAFETY_EVALUATED",
    "DECISION_MINI_DELIVERY_REPORT_CREATED",
    "DECISION_MINI_DELIVERY_PILOT_COMPLETED",
    "DECISION_MINI_DELIVERY_PILOT_FAILED",
    "MINI_DELIVERY_DECISION_TYPES",
    "safe_pilot_artifact_refs",
]
