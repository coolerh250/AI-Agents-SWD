"""Stage 49 -- delivery package audit decision_type constants + safe refs."""

from __future__ import annotations

DECISION_DELIVERY_PACKAGE_BUILD_STARTED = "delivery_package_build_started"
DECISION_DELIVERY_PACKAGE_SECTIONS_CREATED = "delivery_package_sections_created"
DECISION_DELIVERY_PACKAGE_ACCEPTANCE_GATE_EVALUATED = "delivery_package_acceptance_gate_evaluated"
DECISION_DELIVERY_PACKAGE_READY_FOR_REVIEW = "delivery_package_ready_for_review"
DECISION_DELIVERY_PACKAGE_BUILD_FAILED = "delivery_package_build_failed"
DECISION_OPERATOR_ACCEPTANCE_REVIEW_CREATED = "operator_acceptance_review_created"
DECISION_HANDOFF_SUMMARY_CREATED = "handoff_summary_created"
DECISION_DELIVERY_READINESS_SNAPSHOT_CREATED = "delivery_readiness_snapshot_created"

DELIVERY_PACKAGE_DECISION_TYPES: tuple[str, ...] = (
    DECISION_DELIVERY_PACKAGE_BUILD_STARTED,
    DECISION_DELIVERY_PACKAGE_SECTIONS_CREATED,
    DECISION_DELIVERY_PACKAGE_ACCEPTANCE_GATE_EVALUATED,
    DECISION_DELIVERY_PACKAGE_READY_FOR_REVIEW,
    DECISION_DELIVERY_PACKAGE_BUILD_FAILED,
    DECISION_OPERATOR_ACCEPTANCE_REVIEW_CREATED,
    DECISION_HANDOFF_SUMMARY_CREATED,
    DECISION_DELIVERY_READINESS_SNAPSHOT_CREATED,
)


def safe_package_artifact_refs(
    *,
    package_id: str | None = None,
    package_key: str | None = None,
    project_id: str | None = None,
    pilot_id: str | None = None,
    workspace_id: str | None = None,
    gate_run_id: str | None = None,
    status: str | None = None,
    decision: str | None = None,
    human_acceptance_status: str | None = None,
    readiness_status: str | None = None,
    sections_ready_count: int | None = None,
    sections_missing_count: int | None = None,
    blocking_findings_count: int | None = None,
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
        "external_delivery_performed": False,
        "auto_accept": False,
    }
    for key, value in (
        ("package_id", package_id),
        ("package_key", package_key),
        ("project_id", project_id),
        ("pilot_id", pilot_id),
        ("workspace_id", workspace_id),
        ("gate_run_id", gate_run_id),
        ("status", status),
        ("decision", decision),
        ("human_acceptance_status", human_acceptance_status),
        ("readiness_status", readiness_status),
    ):
        if value is not None:
            refs[key] = value
    for ikey, ivalue in (
        ("sections_ready_count", sections_ready_count),
        ("sections_missing_count", sections_missing_count),
        ("blocking_findings_count", blocking_findings_count),
    ):
        if ivalue is not None:
            refs[ikey] = int(ivalue)
    return refs


__all__ = [
    "DECISION_DELIVERY_PACKAGE_BUILD_STARTED",
    "DECISION_DELIVERY_PACKAGE_SECTIONS_CREATED",
    "DECISION_DELIVERY_PACKAGE_ACCEPTANCE_GATE_EVALUATED",
    "DECISION_DELIVERY_PACKAGE_READY_FOR_REVIEW",
    "DECISION_DELIVERY_PACKAGE_BUILD_FAILED",
    "DECISION_OPERATOR_ACCEPTANCE_REVIEW_CREATED",
    "DECISION_HANDOFF_SUMMARY_CREATED",
    "DECISION_DELIVERY_READINESS_SNAPSHOT_CREATED",
    "DELIVERY_PACKAGE_DECISION_TYPES",
    "safe_package_artifact_refs",
]
