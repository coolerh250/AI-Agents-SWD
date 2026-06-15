"""Stage 48 -- mini delivery operations API (monkeypatched fake stores)."""

from __future__ import annotations

import mini_delivery_api
import pytest
from design_review_fakes import FakeDesignReviewStore, FakeDiscussionStore
from mini_delivery_fakes import FakeMiniDeliveryPilotStore
from project_planning_fakes import FakeProjectStore
from workspace_operator_fakes import FakeWorkspaceStore


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
    stores = {
        "project": FakeProjectStore(),
        "discussion": FakeDiscussionStore(),
        "review": FakeDesignReviewStore(),
        "workspace": FakeWorkspaceStore(),
        "pilot": FakeMiniDeliveryPilotStore(),
    }
    monkeypatch.setattr(mini_delivery_api, "_project_store", lambda: stores["project"])
    monkeypatch.setattr(mini_delivery_api, "_discussion_store", lambda: stores["discussion"])
    monkeypatch.setattr(mini_delivery_api, "_review_store", lambda: stores["review"])
    monkeypatch.setattr(mini_delivery_api, "_workspace_store", lambda: stores["workspace"])
    monkeypatch.setattr(mini_delivery_api, "_pilot_store", lambda: stores["pilot"])
    return stores


async def test_run_and_read_endpoints(tmp_path, monkeypatch) -> None:
    await _wire(tmp_path, monkeypatch)
    res = await mini_delivery_api.run_pilot({})
    assert res["production_executed"] is False
    assert res["pr_created"] is False
    assert res["deployment_performed"] is False
    assert res["real_llm_used"] is False
    assert res["pilot_status"] in ("completed", "report_ready")
    pilot_id = res["pilot_id"]
    project_id = res["project_id"]

    steps = await mini_delivery_api.get_pilot_steps(pilot_id)
    assert steps["count"] >= 8

    acc = await mini_delivery_api.get_pilot_acceptance(pilot_id)
    assert acc["summary"]["total"] >= 8
    assert acc["summary"]["failed"] == 0

    qa = await mini_delivery_api.get_pilot_qa(pilot_id)
    assert qa["status"] in ("passed", "passed_with_findings")

    safety = await mini_delivery_api.get_pilot_safety(pilot_id)
    assert safety["status"] == "safe"

    report = await mini_delivery_api.get_pilot_delivery_report(pilot_id)
    assert report["executive_summary"]
    assert report["project_summary"] and report["safety_summary"]

    timeline = await mini_delivery_api.get_pilot_timeline(pilot_id)
    assert timeline["production_executed"] is False

    artifacts = await mini_delivery_api.get_pilot_artifacts(pilot_id)
    assert artifacts["count"] >= 4

    latest = await mini_delivery_api.latest_project_pilot(project_id)
    assert latest["id"] == pilot_id
