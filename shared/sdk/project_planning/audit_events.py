"""Stage 45 -- audit decision_type constants for project planning.

Audit rows carry only project decisions / artifacts / summaries -- never
chain-of-thought, never secrets. The ``artifact_refs`` shape is limited
to opaque ids + counts + booleans.
"""

from __future__ import annotations

DECISION_PROJECT_PLANNING_STARTED = "project_planning_started"
DECISION_PROJECT_BRIEF_CREATED = "project_brief_created"
DECISION_PROJECT_TASK_GRAPH_CREATED = "project_task_graph_created"
DECISION_PROJECT_TASK_GRAPH_VALIDATED = "project_task_graph_validated"
DECISION_PROJECT_WORK_ITEM_ASSIGNED = "project_work_item_assigned"
DECISION_PROJECT_PLANNING_COMPLETED = "project_planning_completed"
DECISION_PROJECT_PLANNING_FAILED = "project_planning_failed"
DECISION_PROJECT_DELIVERY_READINESS_EVALUATED = "project_delivery_readiness_evaluated"

STAGE_45_DECISION_TYPES: tuple[str, ...] = (
    DECISION_PROJECT_PLANNING_STARTED,
    DECISION_PROJECT_BRIEF_CREATED,
    DECISION_PROJECT_TASK_GRAPH_CREATED,
    DECISION_PROJECT_TASK_GRAPH_VALIDATED,
    DECISION_PROJECT_WORK_ITEM_ASSIGNED,
    DECISION_PROJECT_PLANNING_COMPLETED,
    DECISION_PROJECT_PLANNING_FAILED,
    DECISION_PROJECT_DELIVERY_READINESS_EVALUATED,
)


def safe_project_artifact_refs(
    *,
    project_id: str,
    graph_snapshot_id: str | None = None,
    brief_id: str | None = None,
    validation_status: str | None = None,
    work_items_count: int | None = None,
    dependencies_count: int | None = None,
    acceptance_criteria_count: int | None = None,
    template: str | None = None,
    requires_clarification: bool | None = None,
) -> dict:
    """Build an audit-safe artifact_refs dict (opaque ids + counts only)."""
    refs: dict = {
        "project_id": project_id,
        "planning_only": True,
        "production_executed": False,
    }
    if graph_snapshot_id is not None:
        refs["graph_snapshot_id"] = graph_snapshot_id
    if brief_id is not None:
        refs["brief_id"] = brief_id
    if validation_status is not None:
        refs["validation_status"] = validation_status
    if work_items_count is not None:
        refs["work_items_count"] = int(work_items_count)
    if dependencies_count is not None:
        refs["dependencies_count"] = int(dependencies_count)
    if acceptance_criteria_count is not None:
        refs["acceptance_criteria_count"] = int(acceptance_criteria_count)
    if template is not None:
        refs["template"] = template
    if requires_clarification is not None:
        refs["requires_clarification"] = bool(requires_clarification)
    return refs


__all__ = [
    "DECISION_PROJECT_PLANNING_STARTED",
    "DECISION_PROJECT_BRIEF_CREATED",
    "DECISION_PROJECT_TASK_GRAPH_CREATED",
    "DECISION_PROJECT_TASK_GRAPH_VALIDATED",
    "DECISION_PROJECT_WORK_ITEM_ASSIGNED",
    "DECISION_PROJECT_PLANNING_COMPLETED",
    "DECISION_PROJECT_PLANNING_FAILED",
    "DECISION_PROJECT_DELIVERY_READINESS_EVALUATED",
    "STAGE_45_DECISION_TYPES",
    "safe_project_artifact_refs",
]
