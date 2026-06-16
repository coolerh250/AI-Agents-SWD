"""Stage 52 -- delivery package operator REJECT flow."""

from __future__ import annotations

import operator_actions_helpers as h


async def test_reject_completes_no_downstream(monkeypatch) -> None:
    api, store, _pkg, set_current = h.wire(monkeypatch)
    set_current("operator-test")
    req = h.logged_in_request(
        "operator-test", body={"reason": "reject"}, idempotency_key="idem-reject01"
    )
    created = await api._review_request(
        req, "pkg-9", "delivery_package.reject", {"reason": "reject"}
    )
    assert created["status"] == "confirmation_required"
    done = await api.execute_action(
        created["action_id"],
        h.logged_in_request("operator-test"),
        {"confirmation_nonce": created["confirmation_nonce"]},
    )
    assert done["status"] == "completed"
    assert store.decisions[-1]["human_acceptance_status"] == "rejected"
    assert store.decisions[-1]["package_status"] == "rejected"
    assert done["production_executed"] is False


async def test_reject_blocked_for_viewer(monkeypatch) -> None:
    api, store, _pkg, set_current = h.wire(monkeypatch, roles={"viewer-x": ["viewer"]})
    set_current("viewer-x")
    req = h.logged_in_request("viewer-x", body={"reason": "x"}, idempotency_key="idem-vrej0001")
    created = await api._review_request(req, "pkg-9", "delivery_package.reject", {"reason": "x"})
    assert created["status"] == "policy_blocked"
