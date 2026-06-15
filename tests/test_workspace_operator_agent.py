"""Stage 47 -- workspace-operator-agent handle() (no Redis, real fs in tmp)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from workspace_operator_fakes import FakeWorkspaceStore, setup_reviewed_project

_REPO = Path(__file__).resolve().parents[1]


def _load_agent_class():
    path = _REPO / "agents" / "workspace-operator-agent" / "src" / "agent.py"
    spec = importlib.util.spec_from_file_location("workspace_operator_agent_mod", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.WorkspaceOperatorAgent


class FakeBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict]] = []

    async def publish_event(self, stream: str, message: dict) -> str:
        self.published.append((stream, message))
        return "1-0"

    async def close(self) -> None:  # pragma: no cover
        pass


@pytest.fixture(autouse=True)
def _stub_network(monkeypatch: pytest.MonkeyPatch):
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr("shared.sdk.audit.publisher.publish_audit_event", _noop)
    monkeypatch.setattr("shared.sdk.notifications.client.send_notification", _noop)


async def _make_agent(tmp_path, monkeypatch):
    root = tmp_path / "aiagents-workspaces"
    root.mkdir()
    monkeypatch.setenv("WORKSPACE_OPERATOR_ALLOWED_ROOTS", str(root))
    cls = _load_agent_class()
    agent = cls(event_bus=FakeBus())
    project_id, project_store, review_store = await setup_reviewed_project()
    agent._project_store = project_store
    agent._review_store = review_store
    agent._workspace_store = FakeWorkspaceStore()
    return agent, project_id


async def test_agent_runs_controlled_workspace(tmp_path, monkeypatch) -> None:
    agent, project_id = await _make_agent(tmp_path, monkeypatch)
    result = await agent.handle({"task_id": "t-1", "project_id": project_id})
    assert result["result"] in ("tests_passed", "summarized", "tests_failed")
    assert result["event_type"] == "workspace.execution_completed"
    assert result["artifact_refs"]["production_executed"] is False
    assert result["artifact_refs"]["github_write_performed"] is False
    streams = [s for s, _m in agent.bus.published]
    assert "stream.workspace_events" in streams
    for _stream, msg in agent.bus.published:
        assert msg.get("production_executed") is False
        assert msg.get("repo_write_performed") is False
        assert msg.get("deployment_performed") is False
        assert msg.get("real_llm_used") is False


async def test_agent_missing_project_id_failed(tmp_path, monkeypatch) -> None:
    agent, _ = await _make_agent(tmp_path, monkeypatch)
    result = await agent.handle({"task_id": "t-2"})
    assert result["result"] == "failed"
    assert result["event_type"] == "workspace.execution_failed"
