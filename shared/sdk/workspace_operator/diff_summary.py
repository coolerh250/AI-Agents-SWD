"""Stage 47 -- build a workspace diff summary from the file manifest.

Compares the generated workspace against an empty base (everything is
``created`` for a fresh ``generated_project``). Produces counts plus a compact
per-file list (path + type + hash + size) -- never full file diffs in the DB.
"""

from __future__ import annotations

from shared.sdk.workspace_operator.models import WorkspaceDiffSummary, WorkspaceFile


def build_diff_summary(
    manifest: list[WorkspaceFile], *, test_summary: str | None = None
) -> WorkspaceDiffSummary:
    created = [f for f in manifest if f.operation == "created"]
    modified = [f for f in manifest if f.operation == "modified"]
    deleted = [f for f in manifest if f.operation == "deleted"]
    changed = created + modified + deleted
    files = [
        {
            "relative_path": f.relative_path,
            "operation": f.operation,
            "file_type": f.file_type,
            "content_hash": f.content_hash,
            "size_bytes": f.size_bytes,
        }
        for f in sorted(manifest, key=lambda x: x.relative_path)
    ]
    return WorkspaceDiffSummary(
        changed_files_count=len(changed),
        created_files_count=len(created),
        modified_files_count=len(modified),
        deleted_files_count=len(deleted),
        diff_summary={"files": files, "base": "empty_workspace"},
        risk_summary="Generated controlled workspace; no repo write, no deploy, no PR.",
        test_summary=test_summary,
    )


__all__ = ["build_diff_summary"]
