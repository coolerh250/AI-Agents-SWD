"""Stage 45 -- project operations API tests (FakeStore, no DB)."""

from __future__ import annotations

import pytest

import project_api
from project_planning_fakes import FakeProjectStore


@pytest.fixture(autouse=True)
def _wire(monkeypatch: pytest.MonkeyPatch):
    store = FakeProjectStore()
    monkeypatch.setattr(project_api, "_store", lambda: store)

    async def _noop_audit(**kwargs):
        return None

    async def _noop_notify(*args, **kwargs):
        return None

    monkeypatch.setattr("shared.sdk.audit.publisher.publish_audit_event", _noop_audit)
    monkeypatch.setattr("shared.sdk.notifications.client.send_notification", _noop_notify)
    return store


async def _plan() -> str:
    out = await project_api.plan_project_endpoint(
        project_api.PlanRequest(
            request_text="Create a FastAPI Todo Service with CRUD, SQLite, pytest, README"
        )
    )
    assert out["production_executed"] is False
    assert out["planning_only"] is True
    return out["project_id"]


async def test_plan_then_read_graph() -> None:
    pid = await _plan()
    project = await project_api.get_project(pid)
    assert project["status"] == "planned"
    brief = await project_api.get_project_brief(pid)
    assert brief["scope"]
    items = await project_api.get_project_work_items(pid)
    assert items["count"] >= 8
    deps = await project_api.get_project_dependencies(pid)
    assert deps["count"] >= 5
    graph = await project_api.get_project_graph(pid)
    assert graph["validation_status"] == "valid"
    progress = await project_api.get_project_progress(pid)
    assert progress["work_items_total"] >= 8


async def test_plan_requires_request_text() -> None:
    with pytest.raises(Exception):
        await project_api.plan_project_endpoint(project_api.PlanRequest(request_text=""))


async def test_delivery_readiness_false_before_work_done() -> None:
    pid = await _plan()
    readiness = await project_api.get_project_delivery_readiness(pid)
    assert readiness["ready"] is False


async def test_response_has_no_secret_fields() -> None:
    pid = await _plan()
    graph = await project_api.get_project_graph(pid)
    blob = str(graph).upper()
    assert "TOKEN" not in blob
    assert "API_KEY" not in blob
    assert "CHAIN_OF_THOUGHT" not in blob


async def test_unknown_project_404() -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await project_api.get_project("00000000-0000-0000-0000-000000000000")
    assert exc.value.status_code == 404
