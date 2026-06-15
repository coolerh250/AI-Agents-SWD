"""Stage 47 -- build workspace-level artifacts (all redacted).

Produces ``implementation_summary``, ``generated_code_manifest``,
``test_result``, and ``diff_summary`` artifacts. Content is metadata only
(paths, hashes, counts, statuses) -- never file content, secrets, or
chain-of-thought.
"""

from __future__ import annotations

from shared.sdk.workspace_operator.models import (
    WorkspaceArtifact,
    WorkspaceDiffSummary,
    WorkspaceFile,
    WorkspaceTestRun,
)
from shared.sdk.workspace_operator.safety import redact

AGENT = "workspace-operator-agent"


def build_generated_code_manifest(manifest: list[WorkspaceFile]) -> WorkspaceArtifact:
    return WorkspaceArtifact(
        artifact_type="generated_code_manifest",
        title="Generated code manifest",
        content={
            "files": [
                {
                    "relative_path": f.relative_path,
                    "file_type": f.file_type,
                    "operation": f.operation,
                    "content_hash": f.content_hash,
                    "size_bytes": f.size_bytes,
                }
                for f in manifest
            ],
            "files_count": len(manifest),
        },
        created_by_agent=AGENT,
    )


def build_test_result_artifact(test_runs: list[WorkspaceTestRun]) -> WorkspaceArtifact:
    return WorkspaceArtifact(
        artifact_type="test_result",
        title="Workspace test + static check result",
        content={
            "runs": [
                {
                    "test_type": r.test_type,
                    "command": r.command,
                    "status": r.status,
                    "exit_code": r.exit_code,
                    "tests_total": r.tests_total,
                    "tests_passed": r.tests_passed,
                    "tests_failed": r.tests_failed,
                    "duration_ms": r.duration_ms,
                    "output_summary": redact(r.output_summary),
                }
                for r in test_runs
            ]
        },
        created_by_agent=AGENT,
    )


def build_diff_summary_artifact(diff: WorkspaceDiffSummary) -> WorkspaceArtifact:
    return WorkspaceArtifact(
        artifact_type="diff_summary",
        title="Workspace diff summary",
        content={
            "changed_files_count": diff.changed_files_count,
            "created_files_count": diff.created_files_count,
            "modified_files_count": diff.modified_files_count,
            "deleted_files_count": diff.deleted_files_count,
            "risk_summary": diff.risk_summary,
            "test_summary": diff.test_summary,
            "diff_summary": diff.diff_summary,
        },
        created_by_agent=AGENT,
    )


def build_implementation_summary(
    *,
    project_id: str,
    workspace_key: str,
    template: str,
    manifest: list[WorkspaceFile],
    tests_status: str | None,
    static_check_status: str | None,
) -> WorkspaceArtifact:
    return WorkspaceArtifact(
        artifact_type="implementation_summary",
        title="FastAPI Todo controlled workspace implementation summary",
        content={
            "project_id": project_id,
            "workspace_key": workspace_key,
            "template": template,
            "generated_files_count": len(manifest),
            "generated_files": [f.relative_path for f in manifest],
            "tests_status": tests_status,
            "static_check_status": static_check_status,
            "controlled_only": True,
            "production_executed": False,
            "github_write_performed": False,
            "repo_write_performed": False,
            "deployment_performed": False,
            "real_llm_used": False,
        },
        created_by_agent=AGENT,
    )


__all__ = [
    "build_generated_code_manifest",
    "build_test_result_artifact",
    "build_diff_summary_artifact",
    "build_implementation_summary",
]
