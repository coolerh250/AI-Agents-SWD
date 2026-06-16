"""Stage 52 -- delivery package operator ACCEPT flow (human review only)."""

from __future__ import annotations

import operator_actions_helpers as h


async def test_accept_requires_confirmation_then_completes(monkeypatch) -> None:
    api, store, _pkg, set_current = h.wire(monkeypatch)
    set_current("operator-test")
    req = h.logged_in_request(
        "operator-test", body={"reason": "accept it"}, idempotency_key="idem-accept01"
    )
    created = await api._review_request(
        req, "pkg-1", "delivery_package.accept", {"reason": "accept it"}
    )
    assert created["status"] == "confirmation_required"
    assert created["confirmation_required"] is True
    nonce = created["confirmation_nonce"]
    action_id = created["action_id"]

    exec_req = h.logged_in_request("operator-test")
    done = await api.execute_action(action_id, exec_req, {"confirmation_nonce": nonce})
    assert done["status"] == "completed"
    assert done["production_executed"] is False
    assert done["github_write_performed"] is False
    assert done["deployment_performed"] is False
    # decision applied: human acceptance accepted, no downstream
    assert store.decisions[-1]["human_acceptance_status"] == "accepted"
    assert store.decisions[-1]["package_status"] == "accepted"


async def test_accept_blocked_for_reviewer(monkeypatch) -> None:
    api, store, _pkg, set_current = h.wire(monkeypatch, roles={"reviewer-x": ["reviewer"]})
    set_current("reviewer-x")
    req = h.logged_in_request("reviewer-x", body={"reason": "x"}, idempotency_key="idem-rev00001")
    created = await api._review_request(req, "pkg-1", "delivery_package.accept", {"reason": "x"})
    assert created["status"] == "policy_blocked"


async def test_accept_blocked_when_gate_not_ready(monkeypatch) -> None:
    api, store, _pkg, set_current = h.wire(monkeypatch, blocking=2)
    set_current("operator-test")
    req = h.logged_in_request(
        "operator-test", body={"reason": "x"}, idempotency_key="idem-block001"
    )
    created = await api._review_request(req, "pkg-1", "delivery_package.accept", {"reason": "x"})
    nonce = created["confirmation_nonce"]
    exec_req = h.logged_in_request("operator-test")
    done = await api.execute_action(created["action_id"], exec_req, {"confirmation_nonce": nonce})
    assert done["status"] == "failed"  # blocking findings -> effect raises
