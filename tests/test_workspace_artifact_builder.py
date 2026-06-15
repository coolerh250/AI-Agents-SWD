"""Stage 47 -- workspace artifact builders (redacted, metadata only)."""

from __future__ import annotations

from shared.sdk.workspace_operator.artifact_builder import (
    build_diff_summary_artifact,
    build_generated_code_manifest,
    build_implementation_summary,
    build_test_result_artifact,
)
from shared.sdk.workspace_operator.diff_summary import build_diff_summary
from shared.sdk.workspace_operator.fastapi_todo_generator import build_fastapi_todo_files
from shared.sdk.workspace_operator.file_manifest import build_manifest
from shared.sdk.workspace_operator.models import WorkspaceTestRun


def test_implementation_summary_is_controlled_only() -> None:
    manifest = build_manifest(build_fastapi_todo_files())
    art = build_implementation_summary(
        project_id="p1",
        workspace_key="ws-1",
        template="fastapi_todo_service",
        manifest=manifest,
        tests_status="passed",
        static_check_status="passed",
    )
    assert art.artifact_type == "implementation_summary"
    assert art.content["production_executed"] is False
    assert art.content["github_write_performed"] is False
    assert art.content["repo_write_performed"] is False
    assert art.content["generated_files_count"] == len(manifest)


def test_manifest_and_diff_artifacts() -> None:
    manifest = build_manifest(build_fastapi_todo_files())
    man_art = build_generated_code_manifest(manifest)
    assert man_art.content["files_count"] == len(manifest)
    diff = build_diff_summary(manifest)
    diff_art = build_diff_summary_artifact(diff)
    assert diff_art.content["created_files_count"] == len(manifest)


def test_test_result_artifact_redacts_output() -> None:
    run = WorkspaceTestRun(
        test_type="pytest",
        command="python -m pytest -q",
        status="passed",
        output_summary="leaked token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
    )
    art = build_test_result_artifact([run])
    summary = art.content["runs"][0]["output_summary"]
    assert "ghp_" not in summary
    assert "[REDACTED]" in summary
