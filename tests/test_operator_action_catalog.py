"""Stage 52 -- action catalog: enabled set + disabled set."""

from __future__ import annotations

from shared.sdk.operator_actions.action_catalog import (
    DISABLED_ACTION_TYPES,
    ENABLED_ACTIONS,
    catalog_view,
    get_action_entry,
    is_enabled,
    is_known,
)


def test_only_five_enabled() -> None:
    assert set(ENABLED_ACTIONS) == {
        "operator_review.add_note",
        "delivery_package.request_changes",
        "delivery_package.accept",
        "delivery_package.reject",
        "verification.rerun",
    }


def test_accept_reject_require_confirmation() -> None:
    for a in (
        "delivery_package.accept",
        "delivery_package.reject",
        "delivery_package.request_changes",
        "verification.rerun",
    ):
        assert ENABLED_ACTIONS[a].requires_confirmation is True


def test_note_low_risk_no_confirmation() -> None:
    e = ENABLED_ACTIONS["operator_review.add_note"]
    assert e.requires_confirmation is False
    assert e.risk_level == "low"


def test_disabled_actions_not_executable() -> None:
    for a in DISABLED_ACTION_TYPES:
        assert is_known(a) is True
        assert is_enabled(a) is False
        assert get_action_entry(a).execution_enabled is False


def test_high_risk_actions_present_disabled() -> None:
    for a in (
        "deployment.execute",
        "github.create_pr",
        "github.merge_pr",
        "workflow.pause",
        "workflow.resume",
        "work_item.update_status",
        "backup.production_run",
        "policy.update",
        "budget.update",
    ):
        assert a in DISABLED_ACTION_TYPES


def test_catalog_view_shape() -> None:
    v = catalog_view()
    assert len(v["enabled"]) == 5
    assert len(v["disabled"]) == len(DISABLED_ACTION_TYPES)
