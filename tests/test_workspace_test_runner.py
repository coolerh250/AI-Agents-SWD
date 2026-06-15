"""Stage 47 -- pytest runner against a generated workspace."""

from __future__ import annotations

import pytest

from shared.sdk.workspace_operator.fastapi_todo_generator import build_fastapi_todo_files
from shared.sdk.workspace_operator.test_runner import run_pytest
from shared.sdk.workspace_operator.workspace_manager import WorkspaceManager


@pytest.fixture()
def generated_workspace(tmp_path, monkeypatch):
    root = tmp_path / "aiagents-workspaces"
    root.mkdir()
    monkeypatch.setenv("WORKSPACE_OPERATOR_ALLOWED_ROOTS", str(root))
    mgr = WorkspaceManager(str(root))
    ws_root = mgr.prepare("ws-test")
    mgr.write_files(ws_root, build_fastapi_todo_files())
    return ws_root


def test_pytest_passes_or_skips_with_reason(generated_workspace) -> None:
    run = run_pytest(generated_workspace)
    assert run.test_type == "pytest"
    assert run.status in ("passed", "skipped")
    if run.status == "skipped":
        assert "dependency" in (run.output_summary or "").lower() or run.metadata.get(
            "missing_dependencies"
        )
    else:
        assert run.tests_passed and run.tests_passed >= 7
        assert (run.tests_failed or 0) == 0


def test_missing_dependency_classified_skipped(generated_workspace, monkeypatch) -> None:
    import shared.sdk.workspace_operator.test_runner as tr

    monkeypatch.setattr(tr, "_missing_modules", lambda mods: ["httpx"])
    run = run_pytest(generated_workspace)
    assert run.status == "skipped"
    assert run.metadata["skip_reason"] == "dependency_unavailable"
