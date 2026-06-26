"""Step 57 -- multi-project safety fields (from committed policy)."""

from __future__ import annotations

from shared.sdk.work_items.safety import multi_project_safety_fields


def test_enabled_capability_flags() -> None:
    f = multi_project_safety_fields()
    assert f["multi_project_enabled"] is True
    assert f["multi_project_write_api_enabled"] is True
    assert f["work_item_dispatch_enabled"] is True
    assert f["work_item_delivery_package_linkage_enabled"] is True
    assert f["work_item_project_audit_enabled"] is True


def test_dangerous_flags_off() -> None:
    f = multi_project_safety_fields()
    for key in (
        "work_item_dispatch_external_side_effect_enabled",
        "work_item_dispatch_github_write_enabled",
        "work_item_dispatch_argocd_sync_enabled",
        "work_item_dispatch_production_action_enabled",
        "work_item_notification_external_send_enabled",
        "multi_project_production_ready",
    ):
        assert f[key] is False
