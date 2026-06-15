"""Stage 47 -- static check runner (compileall always; ruff optional)."""

from __future__ import annotations

import pytest

from shared.sdk.workspace_operator.fastapi_todo_generator import build_fastapi_todo_files
from shared.sdk.workspace_operator.static_check_runner import (
    overall_static_status,
    run_compileall,
    run_static_checks,
)
from shared.sdk.workspace_operator.workspace_manager import WorkspaceManager


@pytest.fixture()
def generated_workspace(tmp_path, monkeypatch):
    root = tmp_path / "aiagents-workspaces"
    root.mkdir()
    monkeypatch.setenv("WORKSPACE_OPERATOR_ALLOWED_ROOTS", str(root))
    mgr = WorkspaceManager(str(root))
    ws_root = mgr.prepare("ws-static")
    mgr.write_files(ws_root, build_fastapi_todo_files())
    return ws_root


def test_compileall_passes_on_generated_code(generated_workspace) -> None:
    run = run_compileall(generated_workspace)
    assert run.test_type == "compileall"
    assert run.status == "passed"


def test_static_checks_returns_ruff_and_compileall(generated_workspace) -> None:
    runs = run_static_checks(generated_workspace)
    types = {r.test_type for r in runs}
    assert "compileall" in types
    assert "ruff" in types
    ruff = next(r for r in runs if r.test_type == "ruff")
    assert ruff.status in ("passed", "skipped", "failed")
    assert overall_static_status(runs) in ("passed", "skipped", "failed")
