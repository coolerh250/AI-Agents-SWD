"""Step AT-M3.5 -- the delegation HTTP surface, and the operations it deliberately lacks.

The question the store tests cannot answer: can a caller reach past the scheduler's invariants from
outside? A surface offering "set this unit ready", "assign this principal", "mark this dispatched"
or "rebind this to another revision" would make readiness, capability routing and plan binding
conventions rather than guarantees -- every one of them bypassable by one HTTP call.

The shape assertions here are therefore the point, and they are written to fail if a later slice
adds such a route by accident.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "apps" / "orchestrator" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "apps" / "orchestrator" / "src"))

import plan_delegation_api  # noqa: E402

from tests.plan_delegation_fixtures import (  # noqa: E402
    UNSERVED_PLAN,
    cancel_primary_work_item,
    scenario,
    supersede,
)


def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(plan_delegation_api.router)
    return TestClient(app, raise_server_exceptions=False)


def _routes():
    return sorted(
        (r.path, tuple(sorted(r.methods - {"HEAD", "OPTIONS"})))
        for r in plan_delegation_api.router.routes
    )


# --- surface shape (no database needed) -----------------------------------------------------------


def test_the_surface_is_append_only():
    methods = {m for _, ms in _routes() for m in ms}
    assert methods <= {"GET", "POST"}


def test_there_are_exactly_three_write_routes_and_each_is_a_whole_command():
    writes = [path for path, methods in _routes() if "POST" in methods]
    assert writes == [
        "/plan-delegation/execution-units/{execution_unit_id}/result",
        "/plan-delegation/plan-revisions/{plan_revision_id}/materialize",
        "/plan-delegation/plan-revisions/{plan_revision_id}/schedule",
    ]


def test_no_route_can_reach_past_the_schedulers_invariants():
    """Readiness, ownership and plan binding are guarantees, not conventions. A route for any of
    these would be the way a later slice broke that without noticing."""
    paths = " ".join(path for path, _ in _routes())
    for forbidden in (
        "/ready",
        "/assign",
        "/unassign",
        "/dispatch",
        "/state",
        "/rebind",
        "/cancel",
        "/skip",
        "/force",
    ):
        assert forbidden not in paths, forbidden


def test_materialize_accepts_no_plan_no_steps_and_no_owner():
    fields = set(plan_delegation_api.MaterializeRequest.model_fields)
    assert fields == {"goal_id", "materialized_by"}
    assert plan_delegation_api.MaterializeRequest.model_config["extra"] == "forbid"


def test_a_caller_still_sending_a_plan_is_told_so_rather_than_silently_ignored():
    response = _client().post(
        f"/plan-delegation/plan-revisions/{uuid.uuid4()}/materialize",
        json={
            "goal_id": str(uuid.uuid4()),
            "materialized_by": str(uuid.uuid4()),
            "plan": {"objective": "whatever I like", "steps": []},
        },
    )
    assert response.status_code == 422
    assert "plan" in response.text


def test_a_result_must_present_the_dispatch_correlation_id():
    fields = set(plan_delegation_api.StepResultRequest.model_fields)
    assert "correlation_id" in fields and "reported_by" in fields
    assert plan_delegation_api.StepResultRequest.model_config["extra"] == "forbid"


def test_a_result_body_is_a_reference_never_the_evidence_itself():
    fields = set(plan_delegation_api.StepResultRequest.model_fields)
    for forbidden in ("result", "output", "artifact", "logs", "diff", "stdout"):
        assert forbidden not in fields, forbidden


# --- end to end against a real database ------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_full_command_sequence_works_over_http():
    case = await scenario()
    client = _client()

    created = client.post(
        f"/plan-delegation/plan-revisions/{case['plan_revision_id']}/materialize",
        json={"goal_id": case["goal_id"], "materialized_by": case["author"]},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["created"] is True
    assert body["graph"]["is_current"] is True
    assert len(body["graph"]["units"]) == 3
    assert {(e["step_key"], e["depends_on_step_key"]) for e in body["graph"]["dependencies"]} == {
        ("build", "design"),
        ("verify", "build"),
    }

    # Materializing again is an outcome, not an error.
    again = client.post(
        f"/plan-delegation/plan-revisions/{case['plan_revision_id']}/materialize",
        json={"goal_id": case["goal_id"], "materialized_by": case["author"]},
    )
    assert again.status_code == 200 and again.json()["created"] is False

    scheduled = client.post(
        f"/plan-delegation/plan-revisions/{case['plan_revision_id']}/schedule", json={}
    )
    assert scheduled.status_code == 200
    acted = [r for r in scheduled.json()["results"] if r["outcome"] == "dispatched"]
    assert len(acted) == 1 and acted[0]["step_key"] == "design"

    unit = client.get(f"/plan-delegation/execution-units/{acted[0]['execution_unit_id']}").json()
    assert unit["state"] == "dispatched"
    assert unit["routing_decision_id"]
    assert unit["dispatch"]["plan_revision_id"] == case["plan_revision_id"]

    reported = client.post(
        f"/plan-delegation/execution-units/{acted[0]['execution_unit_id']}/result",
        json={
            "reported_by": unit["dispatch"]["assigned_principal_id"],
            "correlation_id": unit["dispatch"]["correlation_id"],
            "disposition": "succeeded",
            "result_ref": "artifact://design-note",
        },
    )
    assert reported.status_code == 200
    assert [u["step_key"] for u in reported.json()["unblocked"]] == ["build"]


@pytest.mark.asyncio
async def test_a_draft_revision_is_a_409_not_a_500():
    case = await scenario(accept=False)
    response = _client().post(
        f"/plan-delegation/plan-revisions/{case['plan_revision_id']}/materialize",
        json={"goal_id": case["goal_id"], "materialized_by": case["author"]},
    )
    assert response.status_code == 409
    assert "draft" in response.json()["detail"]


@pytest.mark.asyncio
async def test_a_superseded_revision_is_a_409_and_dispatches_nothing():
    case = await scenario()
    client = _client()
    client.post(
        f"/plan-delegation/plan-revisions/{case['plan_revision_id']}/materialize",
        json={"goal_id": case["goal_id"], "materialized_by": case["author"]},
    )
    await supersede(case)

    response = client.post(
        f"/plan-delegation/plan-revisions/{case['plan_revision_id']}/schedule", json={}
    )
    assert response.status_code == 409
    graph = client.get(f"/plan-delegation/plan-revisions/{case['plan_revision_id']}/graph").json()
    assert graph["is_current"] is False
    assert graph["dispatches"] == []


@pytest.mark.asyncio
async def test_a_cancelled_execution_lineage_is_a_409():
    case = await scenario()
    client = _client()
    client.post(
        f"/plan-delegation/plan-revisions/{case['plan_revision_id']}/materialize",
        json={"goal_id": case["goal_id"], "materialized_by": case["author"]},
    )
    await cancel_primary_work_item(case["store"], case["goal_id"])
    response = client.post(
        f"/plan-delegation/plan-revisions/{case['plan_revision_id']}/schedule", json={}
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_a_result_from_the_wrong_correlation_id_is_a_403():
    case = await scenario()
    client = _client()
    client.post(
        f"/plan-delegation/plan-revisions/{case['plan_revision_id']}/materialize",
        json={"goal_id": case["goal_id"], "materialized_by": case["author"]},
    )
    scheduled = client.post(
        f"/plan-delegation/plan-revisions/{case['plan_revision_id']}/schedule", json={}
    ).json()
    unit_id = scheduled["results"][0]["execution_unit_id"]
    unit = client.get(f"/plan-delegation/execution-units/{unit_id}").json()

    response = client.post(
        f"/plan-delegation/execution-units/{unit_id}/result",
        json={
            "reported_by": unit["dispatch"]["assigned_principal_id"],
            "correlation_id": str(uuid.uuid4()),
            "disposition": "succeeded",
        },
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_a_step_nobody_can_take_is_reported_honestly_rather_than_given_to_anyone():
    case = await scenario(plan=UNSERVED_PLAN)
    client = _client()
    client.post(
        f"/plan-delegation/plan-revisions/{case['plan_revision_id']}/materialize",
        json={"goal_id": case["goal_id"], "materialized_by": case["author"]},
    )
    scheduled = client.post(
        f"/plan-delegation/plan-revisions/{case['plan_revision_id']}/schedule", json={}
    ).json()

    assert scheduled["results"][0]["outcome"] == "unassignable"
    assert scheduled["results"][0]["reason"] == "capability_unavailable"

    graph = client.get(f"/plan-delegation/plan-revisions/{case['plan_revision_id']}/graph").json()
    assert graph["dispatches"] == []
    assert graph["units"][0]["assigned_principal_id"] is None
    assert graph["units"][0]["unavailable_reason"] == "capability_unavailable"


@pytest.mark.asyncio
async def test_an_unmaterialized_revision_reads_as_404():
    case = await scenario()
    response = _client().get(f"/plan-delegation/plan-revisions/{case['plan_revision_id']}/graph")
    assert response.status_code == 404


def test_the_read_surface_exposes_no_plan_body_and_no_reasoning():
    """The graph view is identifiers, state and reasons. The plan itself stays where AT-M3.2 put
    it, and the discussion that produced it is not this surface's business."""
    unit = plan_delegation_api._unit_view(
        {
            "execution_unit_id": uuid.uuid4(),
            "plan_revision_id": uuid.uuid4(),
            "step_key": "s",
            "work_item_id": uuid.uuid4(),
            "state": "ready",
            "required_capabilities": ["generate_code"],
            "expected_outputs": [],
            "intended_owner_role": None,
            "unavailable_reason": None,
            "assigned_principal_id": None,
            "assigned_role": None,
            "assigned_agent_key": None,
            "routing_decision_id": None,
            "assigned_at": None,
            "disposition": None,
            "result_ref": None,
            "completed_at": None,
        }
    )
    for forbidden in ("plan", "objective", "description", "messages", "reasoning", "prompt"):
        assert forbidden not in unit, forbidden
