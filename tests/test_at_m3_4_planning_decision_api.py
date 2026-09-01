"""Step AT-M3.4 -- the planning decision HTTP surface, and the inputs it deliberately lacks.

Two questions this file answers that the store tests cannot.

Can a caller reach any of the writes independently? Exposing "author a plan", "record a decision"
and "accept a revision" as separate public operations would make every invalid partial state
reachable from outside, so the public boundary is one command and the rest is reading.

Can a caller still say WHICH plan, or WHO decided? AT-M3.4 Validation 1 showed what happened when
it could. Both fields are gone, and because the request model forbids extras, an old client that
still sends them gets a 422 naming the field rather than a silent acceptance that leaves it
believing it chose the plan.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "apps" / "orchestrator" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "apps" / "orchestrator" / "src"))

import planning_decision_api  # noqa: E402

from shared.sdk.agent_planning.store import PlanningStore  # noqa: E402

from tests.test_at_m3_3_deliberation_store import PLAN, _scenario  # noqa: E402
from tests.test_at_m3_4_planning_decision import _converged, _planless_scenario  # noqa: E402


def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(planning_decision_api.router)
    return TestClient(app, raise_server_exceptions=False)


def _routes():
    return sorted(
        (r.path, tuple(sorted(r.methods - {"HEAD", "OPTIONS"})))
        for r in planning_decision_api.router.routes
    )


# --- surface shape ---------------------------------------------------------------------------


def test_the_surface_is_append_only():
    methods = {m for _, ms in _routes() for m in ms}
    assert methods <= {"GET", "POST"}
    assert "PUT" not in methods and "PATCH" not in methods and "DELETE" not in methods


def test_there_is_exactly_one_write_route():
    writes = [(p, ms) for p, ms in _routes() if "POST" in ms]
    assert writes == [("/planning-decisions", ("POST",))]


def test_no_low_level_route_can_reach_a_partial_state():
    """No public way to author a plan, record a decision, or accept one on its own."""
    paths = [p for p, _ in _routes()]
    for forbidden in ("proposal", "challenge", "accept", "reject", "revision/accept", "decide"):
        assert not any(forbidden in path for path in paths), forbidden


def test_no_m35_dispatch_or_execution_route_is_exposed():
    paths = [p for p, _ in _routes()]
    for forbidden in ("dispatch", "work-item", "workitem", "route", "execute", "run", "deploy"):
        assert not any(forbidden in path for path in paths), forbidden


def test_the_expected_route_set_is_minimal():
    assert _routes() == [
        ("/planning-decisions", ("POST",)),
        ("/planning-decisions/by-discussion/{discussion_id}", ("GET",)),
        ("/planning-decisions/{planning_decision_id}", ("GET",)),
        ("/planning-decisions/{planning_decision_id}/evidence", ("GET",)),
    ]


def test_the_command_accepts_two_identifiers_and_refuses_everything_else():
    """The Validation 1 substitution vector, closed at the schema."""
    assert set(planning_decision_api.FinalizeDecisionRequest.model_fields) == {
        "goal_id",
        "discussion_id",
    }
    ok = planning_decision_api.FinalizeDecisionRequest(goal_id="g", discussion_id="d")
    assert ok.goal_id == "g"

    for rejected in (
        {"plan": {"objective": "o", "steps": []}},
        {"decided_by": "someone"},
        {"created_by": "someone"},
        {"candidate_plan_message_id": str(uuid.uuid4())},
        {"outcome": "no_change"},
        {"force": True},
    ):
        with pytest.raises(Exception):
            planning_decision_api.FinalizeDecisionRequest(
                goal_id="g", discussion_id="d", **rejected
            )


@pytest.mark.asyncio
async def test_a_request_that_still_carries_a_plan_or_an_author_is_a_422():
    scenario = await _scenario()
    session = await _converged(scenario)
    client = _client()
    body = {"goal_id": scenario["goal_id"], "discussion_id": str(session["discussion_id"])}

    for extra in ({"plan": {"objective": "o", "steps": []}}, {"decided_by": scenario["opened_by"]}):
        response = client.post("/planning-decisions", json={**body, **extra})
        assert response.status_code == 422, (extra, response.text)
        assert list(extra)[0] in response.text


# --- live behaviour --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_api_records_one_decision_and_replays_it_on_retry():
    scenario = await _scenario()
    session = await _converged(scenario)
    client = _client()
    body = {"goal_id": scenario["goal_id"], "discussion_id": str(session["discussion_id"])}

    created = client.post("/planning-decisions", json=body)
    assert created.status_code == 200, created.text
    first = created.json()
    assert first["created"] is True
    assert first["outcome"] == "plan_accepted"
    assert first["plan_revision"]["status"] == "accepted"
    assert first["candidate_plan_message_id"]
    assert (
        first["planning_decision"]["candidate_plan_message_id"]
        == first["candidate_plan_message_id"]
    )
    assert (
        first["team_decision"]["resulting_plan_revision_id"]
        == (first["plan_revision"]["plan_revision_id"])
    )

    again = client.post("/planning-decisions", json=body).json()
    assert again["created"] is False
    assert (
        again["planning_decision"]["planning_decision_id"]
        == first["planning_decision"]["planning_decision_id"]
    )

    decision_id = first["planning_decision"]["planning_decision_id"]
    read = client.get(f"/planning-decisions/{decision_id}").json()
    assert read["planning_decision"]["planning_decision_id"] == decision_id
    by_discussion = client.get(
        f"/planning-decisions/by-discussion/{session['discussion_id']}"
    ).json()
    assert by_discussion["planning_decision"]["planning_decision_id"] == decision_id

    evidence = client.get(f"/planning-decisions/{decision_id}/evidence").json()
    assert evidence["candidate_plan"]["message_id"] == first["candidate_plan_message_id"]
    assert evidence["candidate_plan"]["plan"] == first["plan_revision"]["plan"]
    assert evidence["proposals"]
    assert all(p["discussion_intent"] for p in evidence["proposals"])
    # No prompt, completion or reasoning trace is exposed -- only the structured artifact.
    body_text = client.get(f"/planning-decisions/{decision_id}/evidence").text
    for marker in ("raw_prompt", "completion", "chain_of_thought", "scratchpad"):
        assert marker not in body_text


@pytest.mark.asyncio
async def test_a_no_change_decision_reports_a_null_revision_rather_than_inventing_one():
    scenario = await _planless_scenario()
    client = _client()
    first = await _converged(scenario, key=f"root-{uuid.uuid4().hex}")
    root = client.post(
        "/planning-decisions",
        json={"goal_id": scenario["goal_id"], "discussion_id": str(first["discussion_id"])},
    ).json()
    assert root["outcome"] == "plan_accepted"

    second = await _converged(scenario, key=f"again-{uuid.uuid4().hex}")
    result = client.post(
        "/planning-decisions",
        json={"goal_id": scenario["goal_id"], "discussion_id": str(second["discussion_id"])},
    )
    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload["outcome"] == "no_change"
    assert payload["plan_revision"] is None
    assert payload["planning_decision"]["resulting_plan_revision_id"] is None
    assert payload["team_decision"]["resulting_plan_revision_id"] is None
    assert payload["planning_decision"]["candidate_plan_message_id"]


@pytest.mark.asyncio
async def test_an_unconverged_discussion_is_a_409_not_a_500():
    scenario = await _scenario()
    from shared.sdk.agent_deliberation.service import DiscussionService

    from tests.test_at_m3_3_deliberation_store import ContestingProvider, _start

    session = await _start(scenario, provider=ContestingProvider())
    await DiscussionService(provider=ContestingProvider()).run(str(session["discussion_id"]))

    response = _client().post(
        "/planning-decisions",
        json={"goal_id": scenario["goal_id"], "discussion_id": str(session["discussion_id"])},
    )
    assert response.status_code == 409
    assert "not admissible" in response.json()["detail"]


@pytest.mark.asyncio
async def test_a_stale_discussion_is_a_409_and_is_not_rebound():
    scenario = await _scenario()
    session = await _converged(scenario)
    await PlanningStore().create_successor_revision(
        {
            "goal_id": scenario["goal_id"],
            "expected_current_revision_id": scenario["plan_revision_id"],
            "created_by": scenario["opened_by"],
            "reason": "scope_correction",
            "plan": PLAN,
        }
    )
    response = _client().post(
        "/planning-decisions",
        json={"goal_id": scenario["goal_id"], "discussion_id": str(session["discussion_id"])},
    )
    assert response.status_code == 409
    assert "currency" in response.json()["detail"]


@pytest.mark.asyncio
async def test_an_unknown_planning_decision_is_a_404_on_every_read_route():
    client = _client()
    missing = str(uuid.uuid4())
    assert client.get(f"/planning-decisions/{missing}").status_code == 404
    assert client.get(f"/planning-decisions/{missing}/evidence").status_code == 404
    assert client.get(f"/planning-decisions/by-discussion/{missing}").status_code == 404
