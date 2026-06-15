"""Stage 50 -- admin console overview / latest-delivery-state aggregate API."""

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


async def test_overview(tmp_path, monkeypatch) -> None:
    await wire_admin_console(tmp_path, monkeypatch)
    d = await admin_console_api.overview()
    assert d["delivery_packages_count"] >= 1
    assert d["ready_for_review_packages_count"] >= 1
    assert d["latest_delivery_package_status"] == "ready_for_review"
    assert d["latest_acceptance_gate_decision"] == "ready_for_operator_review"
    assert d["latest_human_acceptance_status"] == "pending"
    assert d["safety_result"] == "safe"
    assert d["production_executed_true_count"] == 0
    assert d["latest_full_regression_status"] == "passed_with_documented_gaps"
    assert d["admin_console"]["admin_console_read_only"] is True
    assert d["admin_console"]["admin_console_operator_actions_enabled"] is False


async def test_latest_delivery_state(tmp_path, monkeypatch) -> None:
    await wire_admin_console(tmp_path, monkeypatch)
    d = await admin_console_api.latest_delivery_state()
    assert d["production_executed"] is False
    assert d["human_acceptance_status"] == "pending"
    assert d["latest_delivery_package"]["status"] == "ready_for_review"
    assert d["acceptance_gate"]["decision"] == "ready_for_operator_review"
    assert d["readiness_snapshot"]["readiness_status"] == "ready_for_operator_review"


async def test_regression_summary(tmp_path, monkeypatch) -> None:
    await wire_admin_console(tmp_path, monkeypatch)
    d = await admin_console_api.regression_summary()
    assert d["latest_full_regression_status"] == "passed_with_documented_gaps"
