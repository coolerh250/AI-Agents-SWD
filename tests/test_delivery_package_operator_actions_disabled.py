"""Stage 49 -- operator accept/reject/request-changes disabled by default."""

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


async def _build(tmp_path, monkeypatch):
    pilot_result, stores = await run_fake_pilot(tmp_path, monkeypatch)
    stores["package"] = FakeDeliveryPackageStore()
    monkeypatch.setattr(delivery_package_api, "_pilot_store", lambda: stores["pilot"])
    monkeypatch.setattr(delivery_package_api, "_project_store", lambda: stores["project"])
    monkeypatch.setattr(delivery_package_api, "_review_store", lambda: stores["review"])
    monkeypatch.setattr(delivery_package_api, "_workspace_store", lambda: stores["workspace"])
    monkeypatch.setattr(delivery_package_api, "_package_store", lambda: stores["package"])
    res = await delivery_package_api.build_delivery_package(pilot_result.pilot_id, {})
    return res["package_id"], stores


async def test_operator_actions_disabled_by_default(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("ENABLE_DELIVERY_PACKAGE_OPERATOR_ACTIONS", raising=False)
    package_id, _ = await _build(tmp_path, monkeypatch)

    for fn in (
        delivery_package_api.operator_accept,
        delivery_package_api.operator_reject,
        delivery_package_api.operator_request_changes,
    ):
        out = await fn(package_id, {})
        assert out["status"] == "action_disabled"
        assert out["policy"] == "policy_blocked"
        assert out["human_acceptance_status"] == "pending"
        assert out["production_executed"] is False

    # The package's human acceptance must remain pending -- never auto-accepted.
    review = await delivery_package_api.get_operator_review(package_id)
    assert review["review_status"] == "pending"
