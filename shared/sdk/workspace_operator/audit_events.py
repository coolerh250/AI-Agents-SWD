"""Stage 47 -- workspace operator audit decision_type constants + safe refs."""

from __future__ import annotations

DECISION_WORKSPACE_EXECUTION_STARTED = "workspace_execution_started"
DECISION_WORKSPACE_CREATED = "workspace_created"
DECISION_WORKSPACE_FILES_GENERATED = "workspace_files_generated"
DECISION_WORKSPACE_TESTS_COMPLETED = "workspace_tests_completed"
DECISION_WORKSPACE_STATIC_CHECKS_COMPLETED = "workspace_static_checks_completed"
DECISION_WORKSPACE_DIFF_SUMMARIZED = "workspace_diff_summarized"
DECISION_WORKSPACE_EXECUTION_COMPLETED = "workspace_execution_completed"
DECISION_WORKSPACE_EXECUTION_FAILED = "workspace_execution_failed"

WORKSPACE_DECISION_TYPES: tuple[str, ...] = (
    DECISION_WORKSPACE_EXECUTION_STARTED,
    DECISION_WORKSPACE_CREATED,
    DECISION_WORKSPACE_FILES_GENERATED,
    DECISION_WORKSPACE_TESTS_COMPLETED,
    DECISION_WORKSPACE_STATIC_CHECKS_COMPLETED,
    DECISION_WORKSPACE_DIFF_SUMMARIZED,
    DECISION_WORKSPACE_EXECUTION_COMPLETED,
    DECISION_WORKSPACE_EXECUTION_FAILED,
)


def safe_workspace_artifact_refs(
    *,
    project_id: str,
    workspace_id: str | None = None,
    workspace_key: str | None = None,
    status: str | None = None,
    generated_files_count: int | None = None,
    tests_status: str | None = None,
    static_check_status: str | None = None,
    diff_summary_id: str | None = None,
    work_item_links_count: int | None = None,
) -> dict:
    """Build an audit ``artifact_refs`` block that carries only opaque ids,
    counts, and status strings -- never file content, secrets, or
    chain-of-thought."""
    refs: dict = {
        "project_id": project_id,
        "controlled_only": True,
        "planning_only": True,
        "production_executed": False,
        "github_write_performed": False,
        "repo_write_performed": False,
        "deployment_performed": False,
        "real_llm_used": False,
    }
    if workspace_id is not None:
        refs["workspace_id"] = workspace_id
    if workspace_key is not None:
        refs["workspace_key"] = workspace_key
    if status is not None:
        refs["status"] = status
    if generated_files_count is not None:
        refs["generated_files_count"] = int(generated_files_count)
    if tests_status is not None:
        refs["tests_status"] = tests_status
    if static_check_status is not None:
        refs["static_check_status"] = static_check_status
    if diff_summary_id is not None:
        refs["diff_summary_id"] = diff_summary_id
    if work_item_links_count is not None:
        refs["work_item_links_count"] = int(work_item_links_count)
    return refs


__all__ = [
    "DECISION_WORKSPACE_EXECUTION_STARTED",
    "DECISION_WORKSPACE_CREATED",
    "DECISION_WORKSPACE_FILES_GENERATED",
    "DECISION_WORKSPACE_TESTS_COMPLETED",
    "DECISION_WORKSPACE_STATIC_CHECKS_COMPLETED",
    "DECISION_WORKSPACE_DIFF_SUMMARIZED",
    "DECISION_WORKSPACE_EXECUTION_COMPLETED",
    "DECISION_WORKSPACE_EXECUTION_FAILED",
    "WORKSPACE_DECISION_TYPES",
    "safe_workspace_artifact_refs",
]
