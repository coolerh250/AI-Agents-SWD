"""Stage 47 -- workspace operations API (monkeypatched fake stores)."""

from __future__ import annotations

import pytest
import workspace_api
from workspace_operator_fakes import FakeWorkspaceStore, setup_reviewed_project


@pytest.fixture(autouse=True)
def _stub_network(monkeypatch):
    async def _noop(*a, **k):
        return None

    monkeypatch.setattr("shared.sdk.audit.publisher.publish_audit_event", _noop)
    monkeypatch.setattr("shared.sdk.notifications.client.send_notification", _noop)


async def _wire(tmp_path, monkeypatch):
    root = tmp_path / "aiagents-workspaces"
    root.mkdir()
    monkeypatch.setenv("WORKSPACE_OPERATOR_ALLOWED_ROOTS", str(root))
    project_id, project_store, review_store = await setup_reviewed_project()
    ws_store = FakeWorkspaceStore()
    monkeypatch.setattr(workspace_api, "_project_store", lambda: project_store)
    monkeypatch.setattr(workspace_api, "_review_store", lambda: review_store)
    monkeypatch.setattr(workspace_api, "_workspace_store", lambda: ws_store)
    return project_id


async def test_execute_and_read_endpoints(tmp_path, monkeypatch) -> None:
    project_id = await _wire(tmp_path, monkeypatch)
    res = await workspace_api.execute_workspace(project_id, {})
    assert res["production_executed"] is False
    assert res["github_write_performed"] is False
    assert res["repo_write_performed"] is False
    assert res["deployment_performed"] is False
    assert res["real_llm_used"] is False
    assert res["generated_files_count"] >= 8
    workspace_id = res["workspace_id"]

    ws = await workspace_api.get_workspace(workspace_id)
    assert ws["workspace_id"] == workspace_id

    files = await workspace_api.get_workspace_files(workspace_id)
    assert files["count"] >= 8

    runs = await workspace_api.get_workspace_test_runs(workspace_id)
    assert runs["count"] >= 1

    diff = await workspace_api.get_workspace_diff_summary(workspace_id)
    assert diff["created_files_count"] >= 8

    artifacts = await workspace_api.get_workspace_artifacts(workspace_id)
    assert artifacts["count"] >= 4

    report = await workspace_api.get_workspace_report(workspace_id)
    assert report["production_executed"] is False

    links = await workspace_api.get_work_item_execution_links(project_id)
    assert links["count"] >= 1

    summary = await workspace_api.get_workspace_summary(project_id)
    assert summary["latest_workspace_id"] == workspace_id
    assert summary["production_executed"] is False


async def test_unknown_project_404(tmp_path, monkeypatch) -> None:
    from fastapi import HTTPException

    await _wire(tmp_path, monkeypatch)
    with pytest.raises(HTTPException) as exc:
        await workspace_api.execute_workspace("does-not-exist", {})
    assert exc.value.status_code == 404
