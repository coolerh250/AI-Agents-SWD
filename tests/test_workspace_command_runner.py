"""Stage 47 -- allowlisted command runner."""

from __future__ import annotations

import os

import pytest

from shared.sdk.workspace_operator.command_runner import (
    CommandPolicyError,
    run_module,
)


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "aiagents-workspaces"
    ws = root / "ws-1"
    ws.mkdir(parents=True)
    monkeypatch.setenv("WORKSPACE_OPERATOR_ALLOWED_ROOTS", str(root))
    with open(os.path.join(str(ws), "ok.py"), "w") as fh:
        fh.write("VALUE = 1\n")
    return str(ws)


def test_rejects_non_allowlisted_module(workspace) -> None:
    with pytest.raises(CommandPolicyError):
        run_module("os", ["-c", "x"], cwd=workspace)


def test_rejects_cwd_outside_allowlist(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WORKSPACE_OPERATOR_ALLOWED_ROOTS", str(tmp_path / "allowed"))
    with pytest.raises(Exception):
        run_module("compileall", ["-q", "."], cwd=str(tmp_path / "elsewhere"))


def test_compileall_runs_in_workspace(workspace) -> None:
    result = run_module("compileall", ["-q", "."], cwd=workspace)
    assert result.exit_code == 0
    assert result.timed_out is False
    assert result.command_str.startswith("python -m compileall")


def test_compileall_reports_syntax_error(workspace) -> None:
    with open(os.path.join(workspace, "bad.py"), "w") as fh:
        fh.write("def broken(:\n")
    result = run_module("compileall", ["-q", "."], cwd=workspace)
    assert result.exit_code != 0
