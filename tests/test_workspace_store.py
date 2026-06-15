"""Stage 47 -- workspace store URL + full controlled run-through (fakes)."""

from __future__ import annotations

import pytest
from workspace_operator_fakes import FakeWorkspaceStore, setup_reviewed_project

from shared.sdk.workspace_operator import (
    WorkspaceExecutionRequest,
    WorkspaceOperatorStore,
    run_workspace_execution,
)


def test_store_uses_default_url() -> None:
    assert WorkspaceOperatorStore().database_url.startswith("postgresql://")


def test_store_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://postgres@y:5432/env-db")
    assert "env-db" in WorkspaceOperatorStore().database_url


async def test_full_workspace_run_persists(tmp_path, monkeypatch) -> None:
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
    assert result.workspace_id
    assert result.generated_files_count >= 8
    assert result.status in ("tests_passed", "summarized", "tests_failed")
    assert result.tests_status in ("passed", "skipped", "failed")
    assert result.production_executed is False
    assert result.github_write_performed is False
    assert result.repo_write_performed is False
    assert result.deployment_performed is False
    assert result.real_llm_used is False

    files = await ws_store.list_workspace_files(result.workspace_id)
    assert any(f["relative_path"] == "app/main.py" for f in files)
    assert ws_store.diffs[result.workspace_id]["created_files_count"] >= 8
    artifacts = await ws_store.list_artifacts(result.workspace_id)
    types = {a["artifact_type"] for a in artifacts}
    assert {
        "implementation_summary",
        "generated_code_manifest",
        "test_result",
        "diff_summary",
    } <= types
    links = await ws_store.list_work_item_links(project_id)
    assert links
    report = await ws_store.get_workspace_report(result.workspace_id)
    assert report["production_executed"] is False
