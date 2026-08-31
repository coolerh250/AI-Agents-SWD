"""Step AT-M3.4 -- the planning decision HTTP surface, and the routes it deliberately lacks.

The question this file answers that the store tests cannot: can a caller reach any of the three
writes independently? Exposing "create a proposal", "record a decision" and "accept a revision" as
separate public operations would make every invalid partial state reachable from outside, so the
public boundary is one command and the rest is reading.
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
from tests.test_at_m3_4_planning_decision import NEXT_PLAN, _converged  # noqa: E402


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
    """No public way to create a proposal, record a decision, or accept a plan on its own."""
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


def test_the_command_is_closed_and_requires_a_structured_plan():
    with pytest.raises(Exception):
        planning_decision_api.FinalizeDecisionRequest(
            goal_id="g", discussion_id="d", decided_by="p", plan=NEXT_PLAN, force=True
        )
    with pytest.raises(Exception):
        planning_decision_api.FinalizeDecisionRequest(
            goal_id="g", discussion_id="d", decided_by="p", plan="just do it"
        )
    with pytest.raises(Exception):
        # An unknown plan field is refused rather than silently dropped.
        planning_decision_api.FinalizeDecisionRequest(
            goal_id="g",
            discussion_id="d",
            decided_by="p",
            plan={"objective": "o", "steps": [], "notes": "x"},
        )


# --- live behaviour --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_api_records_one_decision_and_replays_it_on_retry():
    scenario = await _scenario()
    session = await _converged(scenario)
    client = _client()
    body = {
        "goal_id": scenario["goal_id"],
        "discussion_id": str(session["discussion_id"]),
        "decided_by": scenario["opened_by"],
        "plan": NEXT_PLAN,
    }

    created = client.post("/planning-decisions", json=body)
    assert created.status_code == 200, created.text
    first = created.json()
    assert first["created"] is True
    assert first["planning_decision"]["outcome"] == "plan_accepted"
    assert first["plan_revision"]["status"] == "accepted"
    assert (
        first["team_decision"]["resulting_plan_revision_id"]
        == (first["plan_revision"]["plan_revision_id"])
    )
    assert first["plan_revision"]["diff"]["objective_changed"] is True

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
    assert evidence["proposals"]
    assert all(p["discussion_intent"] for p in evidence["proposals"])


@pytest.mark.asyncio
async def test_an_unconverged_discussion_is_a_409_not_a_500():
    scenario = await _scenario()
    from shared.sdk.agent_deliberation.service import DiscussionService

    from tests.test_at_m3_3_deliberation_store import ContestingProvider, _start

    session = await _start(scenario, provider=ContestingProvider())
    await DiscussionService(provider=ContestingProvider()).run(str(session["discussion_id"]))

    response = _client().post(
        "/planning-decisions",
        json={
            "goal_id": scenario["goal_id"],
            "discussion_id": str(session["discussion_id"]),
            "decided_by": scenario["opened_by"],
            "plan": NEXT_PLAN,
        },
    )
    assert response.status_code == 409
    assert response.status_code != 500
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
        json={
            "goal_id": scenario["goal_id"],
            "discussion_id": str(session["discussion_id"]),
            "decided_by": scenario["opened_by"],
            "plan": NEXT_PLAN,
        },
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
