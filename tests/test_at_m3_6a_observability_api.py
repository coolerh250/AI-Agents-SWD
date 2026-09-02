"""Step AT-M3.6A -- the HTTP surface, its shape, and the operations it deliberately lacks.

The store and service tests answer "is the answer true". This file answers a different question:
can a caller reach past the read boundary from outside? A surface that offered "retry this step",
"cancel this graph", "approve this", "replan" or "materialize" would turn AT-M3.5's guarantees into
conventions -- every one of them bypassable by one HTTP call from a page that was only supposed to
render a screen.

So the shape assertions here ARE the point, and they are written to fail if a later slice adds such
a route by accident: the router is asserted to expose GET and nothing else, and no path under it is
allowed to name a mutation. The other half of the file checks the two things a wrong read model
would get wrong on a real screen -- a superseded plan rendered as current, and a staged
control-plane message rendered as running work.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "apps" / "orchestrator" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "apps" / "orchestrator" / "src"))

import autonomy_observability_api  # noqa: E402

from tests.autonomy_observability_fixtures import (  # noqa: E402
    UNSERVED_PLAN,
    DirectAuditClient,
    cancel_lineage,
    complete_step,
    goal_only,
    read_store_or_skip,
    scheduled,
    supersede_with,
    units_by_step,
    with_accepted_plan,
)


def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(autonomy_observability_api.router)
    return TestClient(app)


# --- shape: the surface is read-only by construction ------------------------------------------------


def test_the_router_exposes_get_and_nothing_else():
    """Not a convention. A write route on this router would be a second authority over AT-M3.5."""
    for route in autonomy_observability_api.router.routes:
        assert set(route.methods) <= {"GET", "HEAD"}, (route.path, route.methods)


def test_no_route_names_an_operation_this_slice_is_not_allowed_to_perform():
    forbidden = (
        "materialize",
        "schedule",
        "dispatch/",
        "assign",
        "complete",
        "result",
        "retry",
        "replay",
        "cancel",
        "abort",
        "approve",
        "reject",
        "replan",
        "publish",
    )
    for route in autonomy_observability_api.router.routes:
        for word in forbidden:
            assert word not in route.path, (route.path, word)


def test_the_surface_is_mounted_inside_the_existing_operations_read_domain():
    """One primary read domain. A second root would be two representations of one runtime."""
    assert autonomy_observability_api.router.prefix == "/operations/autonomy"
    for route in autonomy_observability_api.router.routes:
        assert route.path.startswith("/operations/autonomy/")


def test_the_module_imports_no_write_capable_client():
    """No event bus, no audit client, no scheduler -- absent from the import graph, not just unused."""
    source = (
        ROOT / "apps" / "orchestrator" / "src" / "autonomy_observability_api.py"
    ).read_text(encoding="utf-8")
    for forbidden in (
        "RedisStreamEventBus",
        "AuditClient",
        "PlanDelegationService",
        "DiscussionService",
        "PlanningDecisionService",
    ):
        assert forbidden not in source, forbidden


def test_a_mutating_verb_on_a_read_route_is_refused_by_the_router():
    client = _client()
    path = f"/operations/autonomy/goals/{uuid.uuid4()}"
    for method in ("post", "put", "patch", "delete"):
        assert getattr(client, method)(path).status_code == 405, method


# --- behaviour --------------------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_goal_overview_validates_against_its_declared_response_model():
    """A raw row dict is not the contract. The declared model is, and FastAPI enforces it."""
    case = await scheduled()
    response = _client().get(f"/operations/autonomy/goals/{case['goal_id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["goal"]["goal_id"] == case["goal_id"]
    assert body["autonomy_phase"]["phase"] == "DISPATCHED"
    assert body["autonomy_phase"]["is_derived"] is True
    assert body["read_model"]["source_of_truth"] == "postgresql"
    assert body["read_model"]["redis_consulted"] is False
    assert body["progress"]["execution_mode"] == "internal_control_plane_simulation"
    unit = next(u for u in body["current_units"] if u["step_key"] == "design")
    assert unit["dispatch_state"] == "DISPATCHED_TO_CONTROL_STREAM"


@pytest.mark.asyncio
async def test_every_partial_state_is_a_200_and_never_a_500():
    """A team that has not got anywhere yet is a legitimate answer, not a server fault."""
    await read_store_or_skip()
    client = _client()

    planless = await goal_only()
    assert client.get(f"/operations/autonomy/goals/{planless['goal_id']}").status_code == 200

    unmaterialized = await with_accepted_plan()
    body = client.get(f"/operations/autonomy/goals/{unmaterialized['goal_id']}").json()
    assert body["current_execution_graph"] is None
    assert body["autonomy_phase"]["phase"] == "PLAN_ACCEPTED"

    unassigned = await scheduled(plan=UNSERVED_PLAN)
    body = client.get(f"/operations/autonomy/goals/{unassigned['goal_id']}").json()
    assert body["autonomy_phase"]["phase"] == "WAITING_FOR_CAPABILITY"

    cancelled = await scheduled()
    await cancel_lineage(cancelled)
    body = client.get(f"/operations/autonomy/goals/{cancelled['goal_id']}").json()
    assert body["autonomy_phase"]["phase"] == "CANCELLED"


@pytest.mark.asyncio
async def test_an_unknown_identifier_is_404_and_a_malformed_one_is_422():
    await read_store_or_skip()
    client = _client()
    unknown = uuid.uuid4()
    assert client.get(f"/operations/autonomy/goals/{unknown}").status_code == 404
    assert (
        client.get(f"/operations/autonomy/plan-revisions/{unknown}/execution-graph").status_code
        == 404
    )
    assert client.get(f"/operations/autonomy/execution-units/{unknown}").status_code == 404
    # Not a 500: a malformed identifier is a caller error with a name.
    assert client.get("/operations/autonomy/goals/not-a-uuid").status_code == 422


@pytest.mark.asyncio
async def test_a_superseded_graph_is_served_and_labelled_rather_than_hidden_or_relabelled():
    case = await scheduled()
    await complete_step(case, "design")
    historical = case["plan_revision_id"]
    successor = await supersede_with(case)
    client = _client()

    body = client.get(
        f"/operations/autonomy/plan-revisions/{historical}/execution-graph"
    ).json()
    assert body["is_current"] is False
    assert body["lineage_status"] == "HISTORICAL_SUPERSEDED"
    assert body["superseded_by_revision_id"] == successor

    # And the Goal's own view does not fold that history into the current plan.
    overview = client.get(f"/operations/autonomy/goals/{case['goal_id']}").json()
    assert overview["current_plan_revision"]["plan_revision_id"] == successor
    assert overview["progress"]["total_units"] == 0
    assert [h["plan_revision_id"] for h in overview["historical_execution_graphs"]] == [historical]


@pytest.mark.asyncio
async def test_the_execution_unit_route_explains_the_routing_without_any_model_reasoning():
    case = await scheduled()
    unit_id = str((await units_by_step(case))["design"]["execution_unit_id"])

    body = _client().get(f"/operations/autonomy/execution-units/{unit_id}").json()

    routing = body["routing"]
    assert routing["outcome"] == "selected"
    assert routing["requested_capability"] == "review_design"
    assert routing["candidates_considered"]
    assert all("principal_id" in c and "eligible" in c for c in routing["candidates_considered"])
    assert body["lineage"]["lineage_status"] == "CURRENT"
    assert body["work_item_id"]
    # The plan's role hint is reported as a preference and said to be one.
    assert routing["preferred_role_is_a_filter"] is False


@pytest.mark.asyncio
async def test_the_reasoning_route_returns_metadata_and_says_what_it_withholds():
    case = await with_accepted_plan()
    body = _client().get(
        f"/operations/autonomy/discussions/{case['discussion_id']}/reasoning"
    ).json()

    assert body["total"] >= 3
    assert "no prompt" in body["disclosure"]
    for invocation in body["invocations"]:
        assert invocation["artifact_body_exposed"] is False
        assert "artifact" not in invocation
        assert invocation["provider_mode"] in ("mock", "disabled")


@pytest.mark.asyncio
async def test_the_timeline_route_is_bounded_and_ordered():
    audit = DirectAuditClient()
    case = await scheduled(audit=audit)
    client = _client()

    body = client.get(f"/operations/autonomy/goals/{case['goal_id']}/timeline?limit=3").json()
    assert len(body["entries"]) == 3 and body["has_more"] is True
    assert body["ordering"] == "created_at ASC, audit_id ASC"
    timestamps = [e["occurred_at"] for e in body["entries"]]
    assert timestamps == sorted(timestamps)

    # The bound is enforced by the route, not trusted from the caller.
    assert (
        client.get(f"/operations/autonomy/goals/{case['goal_id']}/timeline?limit=9999").status_code
        == 422
    )


@pytest.mark.asyncio
async def test_no_response_carries_a_secret_a_credential_or_a_dsn():
    audit = DirectAuditClient()
    case = await scheduled(audit=audit)
    client = _client()
    unit_id = str((await units_by_step(case))["design"]["execution_unit_id"])

    bodies = [
        client.get(f"/operations/autonomy/goals/{case['goal_id']}").text,
        client.get(f"/operations/autonomy/goals/{case['goal_id']}/plan-revisions").text,
        client.get(
            f"/operations/autonomy/plan-revisions/{case['plan_revision_id']}/execution-graph"
        ).text,
        client.get(f"/operations/autonomy/execution-units/{unit_id}").text,
        client.get(f"/operations/autonomy/goals/{case['goal_id']}/timeline").text,
        client.get(f"/operations/autonomy/discussions/{case['discussion_id']}/reasoning").text,
    ]
    for body in bodies:
        lowered = body.lower()
        for forbidden in (
            "postgresql://",
            "password",
            "secret",
            "api_key",
            "apikey",
            "authorization",
            "bearer ",
            "credential",
            "private_key",
            # `attempt_token` is AT-M3.4's lease-ownership value. It is not a credential a caller
            # may act on and it has no business on a read surface; `input_tokens` is a COUNT, which
            # is why the bare word "token" is not what is screened for here.
            "attempt_token",
            "access_token",
            "auth_token",
            "api_token",
        ):
            assert forbidden not in lowered, forbidden
