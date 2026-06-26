"""Step 57 -- work-item lifecycle state machine."""

from __future__ import annotations

from shared.sdk.work_items import lifecycle


def test_states_present() -> None:
    required = {
        "created",
        "triaged",
        "ready_for_dispatch",
        "dispatched",
        "in_progress",
        "waiting_approval",
        "blocked",
        "completed",
        "cancelled",
        "failed",
        "archived",
    }
    assert required <= set(lifecycle.states())


def test_legal_and_illegal_transitions() -> None:
    assert lifecycle.can_transition("created", "triaged")
    assert not lifecycle.can_transition("created", "dispatched")
    assert lifecycle.can_transition("in_progress", "completed")
    assert not lifecycle.can_transition("completed", "in_progress")
    assert lifecycle.can_transition("failed", "ready_for_dispatch")


def test_production_effect_routes_to_waiting_approval() -> None:
    assert lifecycle.next_state_for_dispatch(production_effect=True) == "waiting_approval"
    assert lifecycle.next_state_for_dispatch(production_effect=False) == "dispatched"


def test_terminal_states() -> None:
    assert lifecycle.is_terminal("completed")
    assert lifecycle.is_terminal("archived")
    assert not lifecycle.is_terminal("in_progress")
