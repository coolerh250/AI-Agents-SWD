"""Step 57 -- work-item SDK (lifecycle + dispatcher + events) integration logic."""

from __future__ import annotations

from shared.sdk.work_items import dispatcher, events, lifecycle


def test_validate_transition_raises_on_illegal() -> None:
    import pytest

    lifecycle.validate_transition("created", "triaged")  # ok
    with pytest.raises(ValueError):
        lifecycle.validate_transition("created", "completed")


def test_build_dispatch_event_payload() -> None:
    ev = dispatcher.build_dispatch_event(
        project_id="p1",
        project_key="PRJ-X",
        work_item_id="w1",
        work_item_key="WI-0001",
        dispatch_key="DSP-1",
        work_type="implementation",
        correlation_id="w1",
        production_effect=False,
    )
    assert ev["target_agent"] == "development-agent"
    assert ev["correlation_id"] == "w1"
    assert ev["production_effect"] is False


def test_audit_metadata_redacts_and_marks_non_production() -> None:
    meta = events.build_audit_metadata(
        event_type="work_item_dispatched",
        actor="a",
        role="operator",
        reason="r",
        project_id="p",
        work_item_id="w",
        correlation_id="c",
        extra={"token": "secret", "ok_field": 1},
    )
    assert "token" not in meta
    assert meta["ok_field"] == 1
    assert meta["production_executed"] is False
