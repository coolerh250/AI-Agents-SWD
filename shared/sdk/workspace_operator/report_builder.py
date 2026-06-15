"""Stage 47 -- workspace execution report builder (redacted, controlled-only)."""

from __future__ import annotations

from shared.sdk.workspace_operator.models import (
    WorkItemExecutionLink,
    WorkspaceDiffSummary,
    WorkspaceExecutionResult,
    WorkspaceFile,
    WorkspaceTestRun,
)


def _next_action(result: WorkspaceExecutionResult) -> str:
    if result.status == "tests_passed":
        return "Operator review of the generated workspace; proceed to Step 46 delivery pilot."
    if result.status == "tests_failed":
        return "Operator review of failing tests; no auto-fix this stage."
    if result.status == "failed":
        return f"Blocked: {result.blocked_reason or 'precondition not met'}."
    return "Operator review of the generated workspace."


def build_workspace_report(
    *,
    result: WorkspaceExecutionResult,
    manifest: list[WorkspaceFile] | None = None,
    test_runs: list[WorkspaceTestRun] | None = None,
    diff: WorkspaceDiffSummary | None = None,
    links: list[WorkItemExecutionLink] | None = None,
) -> dict:
    """Build the operator-facing execution report. Booleans + counts + ids only."""
    manifest = manifest or []
    test_runs = test_runs or []
    links = links or []
    return {
        "workspace_id": result.workspace_id,
        "workspace_key": result.workspace_key,
        "workspace_root": result.workspace_root,
        "project_id": result.project_id,
        "status": result.status,
        "blocked_reason": result.blocked_reason,
        "generated_files": [f.relative_path for f in manifest],
        "generated_files_count": result.generated_files_count,
        "tests": [
            {
                "test_type": r.test_type,
                "status": r.status,
                "tests_passed": r.tests_passed,
                "tests_failed": r.tests_failed,
            }
            for r in test_runs
        ],
        "tests_status": result.tests_status,
        "static_check_status": result.static_check_status,
        "diff_summary": (
            {
                "changed_files_count": diff.changed_files_count,
                "created_files_count": diff.created_files_count,
                "modified_files_count": diff.modified_files_count,
                "deleted_files_count": diff.deleted_files_count,
            }
            if diff is not None
            else None
        ),
        "work_item_execution_map": [
            {"work_item_key": link.work_item_key, "execution_status": link.execution_status}
            for link in links
        ],
        "safety_result": {
            "controlled_only": result.controlled_only,
            "production_executed": result.production_executed,
            "github_write_performed": result.github_write_performed,
            "repo_write_performed": result.repo_write_performed,
            "deployment_performed": result.deployment_performed,
            "real_llm_used": result.real_llm_used,
        },
        "next_recommended_action": _next_action(result),
        "production_executed": False,
    }


__all__ = ["build_workspace_report"]
