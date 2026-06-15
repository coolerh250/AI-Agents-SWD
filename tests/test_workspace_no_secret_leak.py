"""Stage 47 -- no secret leak in generated files / artifacts / report."""

from __future__ import annotations

import json

from workspace_operator_fakes import FakeWorkspaceStore, setup_reviewed_project

from shared.sdk.workspace_operator import WorkspaceExecutionRequest, run_workspace_execution
from shared.sdk.workspace_operator.fastapi_todo_generator import build_fastapi_todo_files
from shared.sdk.workspace_operator.safety import contains_secret, redact

_LEAK = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"


def test_contains_secret_detects_known_patterns() -> None:
    assert contains_secret(_LEAK) is True
    assert contains_secret("sk-ABCDEFGHIJKLMNOPQRSTUVWX") is True
    assert contains_secret("just normal text") is False


def test_redact_removes_secret() -> None:
    out = redact(f"token={_LEAK}")
    assert "ghp_" not in out
    assert "[REDACTED]" in out


def test_generated_files_have_no_secrets() -> None:
    for content in build_fastapi_todo_files().values():
        assert contains_secret(content) is False


async def test_run_artifacts_and_report_have_no_secrets(tmp_path, monkeypatch) -> None:
    root = tmp_path / "aiagents-workspaces"
    root.mkdir()
    monkeypatch.setenv("WORKSPACE_OPERATOR_ALLOWED_ROOTS", str(root))
    project_id, project_store, review_store = await setup_reviewed_project()
    ws_store = FakeWorkspaceStore()
    result = await run_workspace_execution(
        request=WorkspaceExecutionRequest(project_id=project_id),
        project_store=project_store,
        review_store=review_store,
        workspace_store=ws_store,
        base_root=str(root),
        emit_events=False,
    )
    blob = json.dumps(await ws_store.get_workspace_report(result.workspace_id))
    assert contains_secret(blob) is False
    for art in ws_store.artifacts[result.workspace_id]:
        assert contains_secret(json.dumps(art.get("content") or {})) is False
