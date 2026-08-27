"""Step AT-M3.3 -- the discussion HTTP surface, and the routes it deliberately does not have.

Two questions this file answers that the store tests cannot: what a caller can reach over HTTP,
and what an expected conflict looks like from the outside. The surface must stay append-only and
must not leak an M3.4 capability -- a discussion that could accept its own outcome would be a
team authorising itself.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "apps" / "orchestrator" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "apps" / "orchestrator" / "src"))

import discussion_api  # noqa: E402

from tests.test_at_m3_3_deliberation_store import (  # noqa: E402
    CAPS,
    ContestingProvider,
    _scenario,
    _service,
)


def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(discussion_api.router)
    return TestClient(app, raise_server_exceptions=False)


def _routes():
    return sorted(
        (r.path, tuple(sorted(r.methods - {"HEAD", "OPTIONS"})))
        for r in discussion_api.router.routes
    )


# --- surface shape ---------------------------------------------------------------------------


def test_the_surface_is_append_only():
    methods = {m for _, ms in _routes() for m in ms}
    assert methods <= {"GET", "POST"}
    assert "PUT" not in methods and "PATCH" not in methods and "DELETE" not in methods


def test_no_m34_decision_route_is_exposed():
    paths = [p for p, _ in _routes()]
    for forbidden in ("accept", "reject", "decision", "decide", "approve", "dispatch"):
        assert not any(forbidden in path for path in paths), forbidden


def test_no_route_can_edit_a_team_message():
    paths = [p for p, _ in _routes()]
    assert "/discussions/{discussion_id}/messages" in paths
    message_routes = [(p, ms) for p, ms in _routes() if p.endswith("/messages") or "message" in p]
    assert all(ms == ("GET",) for _, ms in message_routes)


def test_the_expected_route_set_is_minimal():
    assert _routes() == [
        ("/discussions", ("POST",)),
        ("/discussions/{discussion_id}", ("GET",)),
        ("/discussions/{discussion_id}/advance", ("POST",)),
        ("/discussions/{discussion_id}/messages", ("GET",)),
        ("/discussions/{discussion_id}/participants", ("GET",)),
        ("/discussions/{discussion_id}/state", ("GET",)),
    ]


def test_the_start_request_is_closed():
    with pytest.raises(Exception):
        discussion_api.StartDiscussionRequest(
            project_id="p",
            goal_id="g",
            opened_by="o",
            topic="t",
            required_capabilities=["plan_project"],
            unbounded=True,
        )


def test_a_start_request_must_name_at_least_one_capability():
    with pytest.raises(Exception):
        discussion_api.StartDiscussionRequest(
            project_id="p", goal_id="g", opened_by="o", topic="t", required_capabilities=[]
        )


# --- live behaviour --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_api_opens_reads_advances_and_reports_a_terminal_state():
    scenario = await _scenario()
    client = _client()

    created = client.post(
        "/discussions",
        json={
            "project_id": scenario["project_id"],
            "goal_id": scenario["goal_id"],
            "opened_by": scenario["opened_by"],
            "topic": "what is the smallest slice that satisfies the goal?",
            "required_capabilities": list(CAPS),
            "max_rounds": 1,
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    discussion_id = body["discussion_id"]
    assert body["state"] == "open" and body["stop_reason"] is None
    assert body["is_terminal"] is False
    assert body["bounds"]["max_rounds"] == 1

    # A repeated POST is the same discussion, not a second one.
    again = client.post(
        "/discussions",
        json={
            "project_id": scenario["project_id"],
            "goal_id": scenario["goal_id"],
            "opened_by": scenario["opened_by"],
            "topic": "what is the smallest slice that satisfies the goal?",
            "required_capabilities": list(CAPS),
            "max_rounds": 1,
        },
    )
    assert again.json()["discussion_id"] == discussion_id

    participants = client.get(f"/discussions/{discussion_id}/participants").json()
    assert participants["count"] == 3
    assert all(p["matched_capabilities"] for p in participants["participants"])

    for _ in range(6):
        step = client.post(f"/discussions/{discussion_id}/advance")
        assert step.status_code == 200, step.text
        if step.json()["discussion"]["is_terminal"]:
            break

    state = client.get(f"/discussions/{discussion_id}/state").json()
    assert state["is_terminal"] is True
    # Under the shipped mock provider, one round of unresolved critique is exhaustion.
    assert state["state"] == "exhausted"
    assert state["stop_reason"] == "round_limit_reached"
    assert state["result_message_id"] is None

    messages = client.get(f"/discussions/{discussion_id}/messages").json()
    assert messages["count"] >= 2
    assert {m["message_type"] for m in messages["messages"]} <= {"proposal", "challenge", "message"}
    assert len(messages["turns"]) == messages["count"]


@pytest.mark.asyncio
async def test_advancing_a_terminal_discussion_is_a_200_not_an_error():
    scenario = await _scenario()
    session = await _service(ContestingProvider()).start_discussion(
        project_id=scenario["project_id"],
        goal_id=scenario["goal_id"],
        topic="t",
        opened_by=scenario["opened_by"],
        required_capabilities=CAPS,
    )
    await _service().cancel(session["discussion_id"])

    client = _client()
    step = client.post(f"/discussions/{session['discussion_id']}/advance")
    assert step.status_code == 200
    assert step.json()["advanced"] is False
    assert step.json()["discussion"]["stop_reason"] == "cancelled"


@pytest.mark.asyncio
async def test_an_unknown_discussion_is_a_404_on_every_read_route():
    client = _client()
    missing = str(uuid.uuid4())
    for path in ("", "/state", "/participants", "/messages"):
        assert client.get(f"/discussions/{missing}{path}").status_code == 404
    assert client.post(f"/discussions/{missing}/advance").status_code == 404


@pytest.mark.asyncio
async def test_a_goal_from_another_project_is_a_409_not_a_500():
    scenario = await _scenario()
    other = await _scenario()
    response = _client().post(
        "/discussions",
        json={
            "project_id": scenario["project_id"],
            "goal_id": other["goal_id"],
            "opened_by": scenario["opened_by"],
            "topic": "t",
            "required_capabilities": list(CAPS),
        },
    )
    assert response.status_code == 409
    assert response.status_code != 500


@pytest.mark.asyncio
async def test_an_uncoverable_capability_returns_a_durable_failed_discussion():
    scenario = await _scenario(agent_keys=("qa-agent", "design-review-agent"))
    response = _client().post(
        "/discussions",
        json={
            "project_id": scenario["project_id"],
            "goal_id": scenario["goal_id"],
            "opened_by": scenario["opened_by"],
            "topic": "t",
            "required_capabilities": ["verify_quality", "review_design", "generate_code"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "failed"
    assert body["stop_reason"] == "insufficient_capability_coverage"
    # The failure is queryable rather than merely returned.
    assert _client().get(f"/discussions/{body['discussion_id']}/state").json()["state"] == "failed"
