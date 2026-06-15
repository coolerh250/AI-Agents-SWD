"""Stage 47 -- workspace path safety (allowlist, traversal, symlink, .git)."""

from __future__ import annotations

import os

import pytest

from shared.sdk.workspace_operator.path_safety import (
    REPO_ROOT,
    WorkspacePathError,
    is_disallowed_relpath,
    safe_join,
    validate_workspace_root,
)


@pytest.fixture()
def root(tmp_path, monkeypatch):
    base = tmp_path / "aiagents-workspaces"
    base.mkdir()
    monkeypatch.setenv("WORKSPACE_OPERATOR_ALLOWED_ROOTS", str(base))
    ws = base / "ws-1"
    ws.mkdir()
    return str(ws)


def test_accepts_path_under_allowlisted_root(root) -> None:
    assert validate_workspace_root(root) == os.path.realpath(root)


def test_rejects_filesystem_root() -> None:
    with pytest.raises(WorkspacePathError):
        validate_workspace_root(os.sep)


def test_rejects_repo_root(monkeypatch) -> None:
    monkeypatch.setenv("WORKSPACE_OPERATOR_ALLOWED_ROOTS", REPO_ROOT)
    with pytest.raises(WorkspacePathError):
        validate_workspace_root(REPO_ROOT)


def test_rejects_root_outside_allowlist(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WORKSPACE_OPERATOR_ALLOWED_ROOTS", str(tmp_path / "allowed"))
    with pytest.raises(WorkspacePathError):
        validate_workspace_root(str(tmp_path / "elsewhere" / "ws"))


def test_rejects_empty_root() -> None:
    with pytest.raises(WorkspacePathError):
        validate_workspace_root("")


@pytest.mark.parametrize(
    "rel",
    [
        "../escape.py",
        "a/../../escape.py",
        "/etc/passwd",
        ".git/config",
        "app/.git/x",
        ".env",
        "secrets/key.txt",
        "id_rsa",
        "deploy.key",
        "cert.pem",
    ],
)
def test_disallowed_relpaths(rel) -> None:
    assert is_disallowed_relpath(rel) is True


@pytest.mark.parametrize("rel", ["app/main.py", "tests/test_todos.py", "README.md"])
def test_allowed_relpaths(rel) -> None:
    assert is_disallowed_relpath(rel) is False


def test_safe_join_blocks_traversal(root) -> None:
    with pytest.raises(WorkspacePathError):
        safe_join(root, "../../escape.py")


def test_safe_join_blocks_symlink_escape(root, tmp_path) -> None:
    # a symlink inside the workspace pointing outside must not allow escape.
    outside = tmp_path / "outside"
    outside.mkdir()
    link = os.path.join(root, "link")
    try:
        os.symlink(str(outside), link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported on this platform")
    with pytest.raises(WorkspacePathError):
        safe_join(root, "link/escape.py")


def test_safe_join_allows_normal_file(root) -> None:
    target = safe_join(root, "app/main.py")
    assert target.endswith(os.path.join("app", "main.py"))
