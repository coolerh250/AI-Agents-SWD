"""Stage 50 -- admin console safety summary + /operations/safety fields."""

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


async def test_safety_summary(tmp_path, monkeypatch) -> None:
    await wire_admin_console(tmp_path, monkeypatch)
    d = await admin_console_api.safety_summary()
    assert d["result"] == "safe"
    assert d["production_executed_true_count"] == 0
    assert d["admin_console_read_only"] is True
    assert d["admin_console_operator_actions_enabled"] is False
    assert d["admin_console_write_api_enabled"] is False
    assert d["admin_console_secret_redaction_enabled"] is True
    assert d["delivery_package_operator_actions_enabled"] is False
    assert d["latest_human_acceptance_status"] == "pending"


def test_admin_console_safety_flags() -> None:
    flags = admin_console_api.admin_console_safety_flags()
    assert flags["admin_console_enabled"] is True
    assert flags["admin_console_read_only"] is True
    assert flags["admin_console_operator_actions_enabled"] is False
    assert flags["admin_console_write_api_enabled"] is False
    assert flags["admin_console_secret_redaction_enabled"] is True
