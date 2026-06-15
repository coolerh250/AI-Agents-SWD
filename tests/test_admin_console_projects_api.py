"""Stage 50 -- admin console projects aggregate API."""

from __future__ import annotations

import admin_console_api
import pytest
from admin_console_helpers import wire_admin_console


@pytest.fixture(autouse=True)
def _stub_network(monkeypatch):
    async def _noop(*a, **k):
        return None

    monkeypatch.setattr("shared.sdk.audit.publisher.publish_audit_event", _noop)
    monkeypatch.setattr("shared.sdk.notifications.client.send_notification", _noop)


async def test_projects_list(tmp_path, monkeypatch) -> None:
    result, _ = await wire_admin_console(tmp_path, monkeypatch)
    d = await admin_console_api.projects()
    assert d["count"] >= 1
    p = d["projects"][0]
    assert "project_id" in p
    assert p["human_acceptance_status"] == "pending"
    assert p["latest_delivery_package_status"] == "ready_for_review"


async def test_project_detail(tmp_path, monkeypatch) -> None:
    result, _ = await wire_admin_console(tmp_path, monkeypatch)
    project_id = result.project_id
    d = await admin_console_api.project_detail(project_id)
    assert d["project"]["id"] == project_id
    assert d["rollup"]["readiness_status"] == "ready_for_operator_review"


async def test_project_detail_404(tmp_path, monkeypatch) -> None:
    await wire_admin_console(tmp_path, monkeypatch)
    import fastapi

    with pytest.raises(fastapi.HTTPException):
        await admin_console_api.project_detail("00000000-0000-0000-0000-000000000000")
