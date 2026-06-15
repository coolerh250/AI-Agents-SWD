"""Stage 47 -- build a workspace file manifest from generated content.

Pure: turns ``{relative_path: content}`` into ``WorkspaceFile`` metadata
(hash, byte size, type, one-line summary). No file content is stored -- only
a sha256 hash and a short summary.
"""

from __future__ import annotations

import hashlib

from shared.sdk.workspace_operator.fastapi_todo_generator import file_type_for
from shared.sdk.workspace_operator.models import WorkspaceFile


def _summary(relative_path: str, content: str) -> str:
    lines = content.count("\n") + (0 if content.endswith("\n") or not content else 1)
    return f"{relative_path}: {lines} lines"


def build_manifest(files: dict[str, str], *, operation: str = "created") -> list[WorkspaceFile]:
    """Build a deterministic, sorted list of ``WorkspaceFile`` from content."""
    manifest: list[WorkspaceFile] = []
    for rel in sorted(files):
        content = files[rel]
        data = content.encode("utf-8")
        manifest.append(
            WorkspaceFile(
                relative_path=rel,
                file_type=file_type_for(rel),
                operation=operation,
                content_hash=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data),
                summary=_summary(rel, content),
            )
        )
    return manifest


__all__ = ["build_manifest"]
