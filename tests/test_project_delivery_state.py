"""Step 57 -- project delivery-state rollup."""

from __future__ import annotations

from shared.sdk.projects import compute_delivery_state


def _wi(state: str, work_type: str = "task") -> dict:
    return {"lifecycle_state": state, "work_type": work_type}


def test_rollup() -> None:
    assert compute_delivery_state([]) == "not_started"
    assert compute_delivery_state([_wi("blocked")]) == "blocked"
    assert compute_delivery_state([_wi("waiting_approval")]) == "operator_review"
    assert compute_delivery_state([_wi("in_progress", "qa")]) == "qa_active"
    assert compute_delivery_state([_wi("in_progress", "implementation")]) == "implementation_active"
    assert compute_delivery_state([_wi("completed")]) == "completed_nonproduction"


def test_blocked_precedence() -> None:
    assert compute_delivery_state([_wi("blocked"), _wi("waiting_approval")]) == "blocked"
