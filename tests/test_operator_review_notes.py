"""Stage 52 -- add review note (low risk, no confirmation) + auth guards."""

from __future__ import annotations

import operator_actions_helpers as h


async def test_add_note_completes(monkeypatch) -> None:
    api, store, _pkg, set_current = h.wire(monkeypatch, roles={"reviewer-x": ["reviewer"]})
    set_current("reviewer-x")
    req = h.logged_in_request(
        "reviewer-x", body={"reason": "looks good"}, idempotency_key="idem-note0001"
    )
    res = await api._review_request(
        req, "pkg-3", "operator_review.add_note", {"reason": "looks good"}
    )
    assert res["status"] == "completed"
    assert store.notes and store.notes[-1]["summary"] == "looks good"


async def test_missing_reason_rejected(monkeypatch) -> None:
    api, store, _pkg, set_current = h.wire(monkeypatch)
    set_current("operator-test")
    req = h.logged_in_request("operator-test", body={"reason": ""}, idempotency_key="idem-noreas01")
    res = await api._review_request(req, "pkg-3", "operator_review.add_note", {"reason": ""})
    assert res["reason"] == "reason_required"


async def test_missing_csrf_rejected(monkeypatch) -> None:
    api, store, _pkg, set_current = h.wire(monkeypatch)
    set_current("operator-test")
    req = h.logged_in_request(
        "operator-test", body={"reason": "x"}, idempotency_key="idem-nocsrf01", with_csrf=False
    )
    res = await api._review_request(req, "pkg-3", "operator_review.add_note", {"reason": "x"})
    assert res["status"] == "policy_blocked"
    assert res["reason"] == "csrf_invalid"


async def test_idempotent_replay(monkeypatch) -> None:
    api, store, _pkg, set_current = h.wire(monkeypatch)
    set_current("operator-test")
    await api._review_request(
        h.logged_in_request("operator-test", body={"reason": "n"}, idempotency_key="idem-dup00001"),
        "pkg-3",
        "operator_review.add_note",
        {"reason": "n"},
    )
    r2 = await api._review_request(
        h.logged_in_request("operator-test", body={"reason": "n"}, idempotency_key="idem-dup00001"),
        "pkg-3",
        "operator_review.add_note",
        {"reason": "n"},
    )
    assert r2.get("idempotent_replay") is True
    assert len(store.notes) == 1
