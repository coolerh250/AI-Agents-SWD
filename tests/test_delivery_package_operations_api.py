"""Stage 49 -- delivery package operations API (monkeypatched fake stores)."""

from __future__ import annotations

import delivery_package_api
import pytest
from delivery_package_fakes import FakeDeliveryPackageStore
from mini_delivery_fakes import run_fake_pilot


@pytest.fixture(autouse=True)
def _stub_network(monkeypatch):
    async def _noop(*a, **k):
        return None

    monkeypatch.setattr("shared.sdk.audit.publisher.publish_audit_event", _noop)
    monkeypatch.setattr("shared.sdk.notifications.client.send_notification", _noop)


async def _wire_with_pilot(tmp_path, monkeypatch):
    pilot_result, stores = await run_fake_pilot(tmp_path, monkeypatch)
    stores["package"] = FakeDeliveryPackageStore()
    monkeypatch.setattr(delivery_package_api, "_pilot_store", lambda: stores["pilot"])
    monkeypatch.setattr(delivery_package_api, "_project_store", lambda: stores["project"])
    monkeypatch.setattr(delivery_package_api, "_review_store", lambda: stores["review"])
    monkeypatch.setattr(delivery_package_api, "_workspace_store", lambda: stores["workspace"])
    monkeypatch.setattr(delivery_package_api, "_package_store", lambda: stores["package"])
    return pilot_result, stores


async def test_build_and_read_endpoints(tmp_path, monkeypatch) -> None:
    pilot_result, stores = await _wire_with_pilot(tmp_path, monkeypatch)
    res = await delivery_package_api.build_delivery_package(pilot_result.pilot_id, {})
    assert res["package_status"] == "ready_for_review"
    assert res["human_acceptance_status"] == "pending"
    assert res["production_executed"] is False
    assert res["pr_created"] is False
    assert res["deployment_performed"] is False
    assert res["real_llm_used"] is False
    assert res["external_delivery_performed"] is False
    package_id = res["package_id"]
    project_id = res["project_id"]

    sections = await delivery_package_api.get_package_sections(package_id)
    assert sections["count"] == 14
    assert sections["missing_count"] == 0

    artifacts = await delivery_package_api.get_package_artifacts(package_id)
    assert artifacts["count"] >= 7

    report = await delivery_package_api.get_package_report(package_id)
    assert report["report_type"] == "delivery_package_report"
    assert report["human_acceptance_status"] == "pending"

    gate = await delivery_package_api.get_acceptance_gate(package_id)
    assert gate["status"] in ("passed", "passed_with_findings")
    assert gate["decision"] in ("ready_for_operator_review", "controlled_only_complete")
    assert gate["human_review_status"] == "pending"
    assert gate["blocking_findings_count"] == 0

    checks = await delivery_package_api.get_acceptance_checks(package_id)
    assert checks["count"] >= 15
    assert checks["failed"] == 0

    checklist = await delivery_package_api.get_acceptance_checklist(package_id)
    assert checklist["items"]

    readiness = await delivery_package_api.get_package_readiness(package_id)
    assert readiness["readiness_status"] == "ready_for_operator_review"
    assert readiness["human_acceptance_pending"] is True

    handoffs = await delivery_package_api.get_package_handoffs(package_id)
    assert handoffs["count"] == 3

    review = await delivery_package_api.get_operator_review(package_id)
    assert review["review_status"] == "pending"

    latest = await delivery_package_api.latest_project_package(project_id)
    assert latest["id"] == package_id
