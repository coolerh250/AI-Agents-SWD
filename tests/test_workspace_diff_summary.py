"""Stage 47 -- workspace diff summary counts."""

from __future__ import annotations

from shared.sdk.workspace_operator.diff_summary import build_diff_summary
from shared.sdk.workspace_operator.fastapi_todo_generator import build_fastapi_todo_files
from shared.sdk.workspace_operator.file_manifest import build_manifest


def test_diff_summary_counts_generated_files() -> None:
    files = build_fastapi_todo_files()
    manifest = build_manifest(files)
    diff = build_diff_summary(manifest, test_summary="pytest=passed")
    assert diff.created_files_count == len(manifest)
    assert diff.changed_files_count == len(manifest)
    assert diff.modified_files_count == 0
    assert diff.deleted_files_count == 0
    assert diff.diff_summary["base"] == "empty_workspace"
    assert len(diff.diff_summary["files"]) == len(manifest)
    assert diff.test_summary == "pytest=passed"


def test_manifest_has_hash_and_size() -> None:
    manifest = build_manifest(build_fastapi_todo_files())
    for f in manifest:
        assert f.content_hash and len(f.content_hash) == 64
        assert f.size_bytes is not None and f.size_bytes >= 0
        assert f.operation == "created"
