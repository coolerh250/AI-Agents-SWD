"""Stage 52 -- delivery package REQUEST CHANGES flow."""

from __future__ import annotations

import operator_actions_helpers as h


async def test_request_changes_reviewer_allowed(monkeypatch) -> None:
    api, store, _pkg, set_current = h.wire(monkeypatch, roles={"reviewer-x": ["reviewer"]})
    set_current("reviewer-x")
    req = h.logged_in_request(
        "reviewer-x", body={"reason": "fix docs"}, idempotency_key="idem-reqchg01"
    )
    created = await api._review_request(
        req, "pkg-2", "delivery_package.request_changes", {"reason": "fix docs"}
    )
    assert created["status"] == "confirmation_required"
    done = await api.execute_action(
        created["action_id"],
        h.logged_in_request("reviewer-x"),
        {"confirmation_nonce": created["confirmation_nonce"]},
    )
    assert done["status"] == "completed"
    d = store.decisions[-1]
    assert d["review_status"] == "changes_requested"
    assert d["human_acceptance_status"] == "pending"
    assert d["package_status"] == "ready_for_review"


async def test_missing_confirmation_rejected(monkeypatch) -> None:
    api, store, _pkg, set_current = h.wire(monkeypatch)
    set_current("operator-test")
    req = h.logged_in_request(
        "operator-test", body={"reason": "x"}, idempotency_key="idem-noconf01"
    )
    created = await api._review_request(
        req, "pkg-2", "delivery_package.request_changes", {"reason": "x"}
    )
    done = await api.execute_action(created["action_id"], h.logged_in_request("operator-test"), {})
    assert done.get("status") != "completed"
    assert done.get("reason") in ("confirmation_invalid", "confirmation_missing")
