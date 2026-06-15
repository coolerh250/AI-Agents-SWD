"""Stage 47 -- WorkspaceManager prepare/write/list/cleanup + safety."""

from __future__ import annotations

import os

import pytest

from shared.sdk.workspace_operator.fastapi_todo_generator import build_fastapi_todo_files
from shared.sdk.workspace_operator.path_safety import WorkspacePathError
from shared.sdk.workspace_operator.workspace_manager import WorkspaceManager


@pytest.fixture()
def base(tmp_path, monkeypatch):
    root = tmp_path / "aiagents-workspaces"
    root.mkdir()
    monkeypatch.setenv("WORKSPACE_OPERATOR_ALLOWED_ROOTS", str(root))
    return str(root)


def test_prepare_write_list_cleanup(base) -> None:
    mgr = WorkspaceManager(base)
    ws_root = mgr.prepare("ws-1")
    assert os.path.isdir(ws_root)
    files = build_fastapi_todo_files()
    mgr.write_files(ws_root, files)
    listed = mgr.list_files(ws_root)
    assert "app/main.py" in listed
    assert "tests/test_todos.py" in listed
    # files actually exist on disk
    assert os.path.isfile(os.path.join(ws_root, "app", "main.py"))
    assert mgr.cleanup(ws_root) is True
    assert not os.path.isdir(ws_root)


def test_prepare_is_clean(base) -> None:
    mgr = WorkspaceManager(base)
    ws_root = mgr.prepare("ws-2")
    with open(os.path.join(ws_root, "stale.txt"), "w") as fh:
        fh.write("old")
    ws_root2 = mgr.prepare("ws-2")
    assert not os.path.exists(os.path.join(ws_root2, "stale.txt"))


def test_base_root_must_be_allowlisted(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WORKSPACE_OPERATOR_ALLOWED_ROOTS", str(tmp_path / "allowed"))
    with pytest.raises(ValueError):
        WorkspaceManager(str(tmp_path / "not-allowed"))


def test_write_rejects_traversal(base) -> None:
    mgr = WorkspaceManager(base)
    ws_root = mgr.prepare("ws-3")
    with pytest.raises(WorkspacePathError):
        mgr.write_files(ws_root, {"../escape.py": "x"})


def test_write_rejects_git_and_secret_files(base) -> None:
    mgr = WorkspaceManager(base)
    ws_root = mgr.prepare("ws-4")
    with pytest.raises(WorkspacePathError):
        mgr.write_files(ws_root, {".git/config": "x"})
    with pytest.raises(WorkspacePathError):
        mgr.write_files(ws_root, {"deploy.key": "x"})


def test_invalid_workspace_key(base) -> None:
    mgr = WorkspaceManager(base)
    with pytest.raises(ValueError):
        mgr.workspace_root_for("../evil")
