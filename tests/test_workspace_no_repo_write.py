"""Stage 47 -- the operator never writes the repo root."""

from __future__ import annotations

import os

import pytest
from workspace_operator_fakes import FakeWorkspaceStore, setup_reviewed_project

from shared.sdk.workspace_operator import WorkspaceExecutionRequest, run_workspace_execution
from shared.sdk.workspace_operator.path_safety import REPO_ROOT, WorkspacePathError
from shared.sdk.workspace_operator.workspace_manager import WorkspaceManager


def test_repo_root_is_never_a_valid_workspace_root() -> None:
    with pytest.raises((WorkspacePathError, ValueError)):
        WorkspaceManager(REPO_ROOT)


async def test_run_writes_only_under_allowlisted_root(tmp_path, monkeypatch) -> None:
    root = tmp_path / "aiagents-workspaces"
    root.mkdir()
    monkeypatch.setenv("WORKSPACE_OPERATOR_ALLOWED_ROOTS", str(root))
    project_id, project_store, review_store = await setup_reviewed_project()
    result = await run_workspace_execution(
        request=WorkspaceExecutionRequest(project_id=project_id),
        project_store=project_store,
        review_store=review_store,
        workspace_store=FakeWorkspaceStore(),
        base_root=str(root),
        emit_events=False,
    )
    ws_root = os.path.realpath(result.workspace_root)
    assert ws_root.startswith(os.path.realpath(str(root)) + os.sep)
    assert not ws_root.startswith(REPO_ROOT + os.sep)
    # the generated app actually lives under the controlled root, not the repo.
    assert os.path.isfile(os.path.join(ws_root, "app", "main.py"))
    assert result.repo_write_performed is False


def test_generated_workspace_path_is_gitignored() -> None:
    gitignore = os.path.join(REPO_ROOT, ".gitignore")
    with open(gitignore, encoding="utf-8") as fh:
        body = fh.read()
    assert ".generated-workspaces/" in body
    assert ".workspaces/" in body  # Stage 28 root also ignored
