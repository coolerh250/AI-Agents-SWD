"""Stage 47 -- controlled workspace filesystem safety.

Pure path policy: no I/O side effects beyond ``os.path.realpath`` resolution.
Enforces an allowlisted workspace root, blocks path traversal / symlink
escape, and refuses writes to ``.git``, ``.env``, and secret-like files.

The repo root is NEVER an allowed workspace root, and ``/`` is never allowed.
"""

from __future__ import annotations

import os

# shared/sdk/workspace_operator/path_safety.py -> repo root is parents[3].
REPO_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

DEFAULT_WORKSPACE_ROOTS: tuple[str, ...] = (
    "/tmp/aiagents-workspaces",
    os.path.join(REPO_ROOT, ".generated-workspaces"),
)

# Relative path segments / suffixes that must never be written.
_DISALLOWED_SEGMENTS = (".git", ".env", "secrets", ".ssh")
_DISALLOWED_SUFFIXES = (".key", ".pem", ".p12", ".secret")
_DISALLOWED_NAMES = ("credentials.json", "id_rsa", ".npmrc", ".pypirc", ".netrc")


class WorkspacePathError(ValueError):
    """Raised when a workspace root or file path violates the safety policy."""


def allowed_roots(env: dict | None = None) -> list[str]:
    """Resolved absolute allowlist roots (env override or defaults)."""
    source = env if env is not None else os.environ
    raw = (source.get("WORKSPACE_OPERATOR_ALLOWED_ROOTS", "") or "").strip()
    roots = (
        [r.strip() for r in raw.split(",") if r.strip()] if raw else list(DEFAULT_WORKSPACE_ROOTS)
    )
    return [os.path.realpath(r) for r in roots]


def _under(child: str, parent: str) -> bool:
    parent = parent.rstrip(os.sep)
    return child == parent or child.startswith(parent + os.sep)


def validate_workspace_root(root: str, *, env: dict | None = None) -> str:
    """Validate a workspace root path; return its realpath or raise.

    A valid root is: non-empty, not ``/``, not the repo root, and strictly
    UNDER one of the allowlisted roots (it may equal an allowlist root too).
    """
    if not root or not str(root).strip():
        raise WorkspacePathError("workspace_root must not be empty")
    candidate = os.path.realpath(str(root))
    if candidate == os.path.realpath(os.sep):
        raise WorkspacePathError("workspace_root must not be the filesystem root")
    if candidate == REPO_ROOT:
        raise WorkspacePathError("workspace_root must not be the repo root")
    if _under(REPO_ROOT, candidate):
        raise WorkspacePathError("workspace_root must not contain the repo root")
    roots = allowed_roots(env)
    if not any(_under(candidate, r) for r in roots):
        raise WorkspacePathError(f"workspace_root {candidate!r} is not under an allowlisted root")
    return candidate


def is_disallowed_relpath(relative_path: str) -> bool:
    """True if a workspace-relative path targets a forbidden location."""
    rel = str(relative_path or "").replace("\\", "/").strip()
    if not rel:
        return True
    if rel.startswith("/") or rel.startswith("~"):
        return True
    parts = [p for p in rel.split("/") if p not in ("", ".")]
    if any(p == ".." for p in parts):
        return True
    lowered = [p.lower() for p in parts]
    if any(seg in lowered for seg in _DISALLOWED_SEGMENTS):
        return True
    name = lowered[-1] if lowered else ""
    if name in _DISALLOWED_NAMES:
        return True
    if any(name.endswith(suf) for suf in _DISALLOWED_SUFFIXES):
        return True
    return False


def safe_join(workspace_root: str, relative_path: str, *, env: dict | None = None) -> str:
    """Join + validate; return the absolute path or raise WorkspacePathError.

    ``workspace_root`` must already be a validated root. The result must stay
    strictly under the root after symlink resolution, and the relative path
    must not target a disallowed location.
    """
    root = validate_workspace_root(workspace_root, env=env)
    if is_disallowed_relpath(relative_path):
        raise WorkspacePathError(f"disallowed relative path: {relative_path!r}")
    target = os.path.realpath(os.path.join(root, relative_path))
    if not _under(target, root):
        raise WorkspacePathError(f"path escapes workspace root: {relative_path!r} -> {target!r}")
    return target


__all__ = [
    "WorkspacePathError",
    "REPO_ROOT",
    "DEFAULT_WORKSPACE_ROOTS",
    "allowed_roots",
    "validate_workspace_root",
    "is_disallowed_relpath",
    "safe_join",
]
