"""Stage 47 -- controlled workspace filesystem manager.

Creates a clean per-execution workspace directory UNDER an allowlisted root,
writes generated files through ``path_safety.safe_join`` (so traversal /
symlink escape / ``.git`` / secret-file writes are impossible), lists the
result, and optionally cleans up. It NEVER writes the repo root.
"""

from __future__ import annotations

import os
import shutil

from shared.sdk.workspace_operator.path_safety import (
    allowed_roots,
    safe_join,
    validate_workspace_root,
)


class WorkspaceManager:
    def __init__(self, base_root: str | None = None, *, env: dict | None = None) -> None:
        self.env = env
        roots = allowed_roots(env)
        self.base_root = os.path.realpath(base_root) if base_root else roots[0]
        # base_root must itself be an allowlisted root (or under one).
        if not any(self.base_root == r or self.base_root.startswith(r + os.sep) for r in roots):
            raise ValueError(f"base_root {self.base_root!r} not under an allowlisted root")

    def workspace_root_for(self, workspace_key: str) -> str:
        """Compute (and validate) the per-workspace directory path."""
        if (
            not workspace_key
            or "/" in workspace_key
            or "\\" in workspace_key
            or ".." in workspace_key
        ):
            raise ValueError(f"invalid workspace_key: {workspace_key!r}")
        root = os.path.join(self.base_root, workspace_key)
        return validate_workspace_root(root, env=self.env)

    def prepare(self, workspace_key: str) -> str:
        """Create a clean workspace directory; return its absolute path."""
        os.makedirs(self.base_root, exist_ok=True)
        root = self.workspace_root_for(workspace_key)
        if os.path.exists(root):
            # Only ever remove a path that validated as under an allowed root.
            shutil.rmtree(root)
        os.makedirs(root)
        return root

    def write_files(self, workspace_root: str, files: dict[str, str]) -> list[str]:
        """Write ``{relative_path: content}`` into the workspace safely."""
        validate_workspace_root(workspace_root, env=self.env)
        written: list[str] = []
        for rel in sorted(files):
            target = safe_join(workspace_root, rel, env=self.env)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(files[rel])
            written.append(rel)
        return written

    def list_files(self, workspace_root: str) -> list[str]:
        """List workspace files as sorted POSIX-style relative paths."""
        root = validate_workspace_root(workspace_root, env=self.env)
        out: list[str] = []
        for dirpath, _dirs, filenames in os.walk(root):
            for name in filenames:
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, root).replace("\\", "/")
                if "__pycache__" in rel or rel.endswith(".pyc"):
                    continue
                out.append(rel)
        return sorted(out)

    def cleanup(self, workspace_root: str) -> bool:
        """Remove a workspace directory (only if under an allowlisted root)."""
        root = validate_workspace_root(workspace_root, env=self.env)
        if os.path.isdir(root):
            shutil.rmtree(root)
            return True
        return False


__all__ = ["WorkspaceManager"]
