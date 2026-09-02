"""Step AT-M3.6A -- proof, not assurance, that reading changes nothing.

"It only reads" is the easiest claim in this repository to believe and the easiest to break. A
lazily-materialized cache, a "record that this was viewed" audit line, a scheduler call slipped into
a next-work projection, a retry of a failed reasoning attempt on the way past -- every one of those
starts as a small convenience inside a GET, and every one of them makes the read surface a writer.

So this file measures instead of asserting intent. It snapshots row counts AND content hashes of
every canonical table the surface touches, hammers each high-value endpoint, and snapshots again.
The expected delta is exactly zero rows and exactly zero content change.

Content hashing matters as much as counting: an UPDATE to ``plan_execution_units.updated_at``, a
stamped ``published_at`` or a rewritten ``audit_ref`` moves nothing in a COUNT and is still a
mutation of canonical state.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from shared.sdk.autonomy_observability.service import AutonomyObservabilityService
from shared.sdk.plan_delegation.store import PlanDelegationStore

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "apps" / "orchestrator" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "apps" / "orchestrator" / "src"))

import autonomy_observability_api  # noqa: E402

from tests.autonomy_observability_fixtures import (  # noqa: E402
    CANONICAL_TABLES,
    DirectAuditClient,
    complete_step,
    read_store_or_skip,
    scheduled,
    supersede_with,
    units_by_step,
)

#: Tables whose rows carry a mutable column a careless read could touch, hashed by content rather
#: than counted. The AT-M3.5 write-once triggers would REFUSE most of these edits, which is exactly
#: why the test must be able to see an attempt that got through anywhere else.
_HASHED = {
    "plan_execution_units": (
        "SELECT execution_unit_id, state, unavailable_reason, assigned_principal_id, "
        "routing_decision_id, assigned_at, disposition, result_ref, completed_at, updated_at "
        "FROM plan_execution_units ORDER BY execution_unit_id"
    ),
    "plan_execution_dispatches": (
        "SELECT execution_unit_id, published_at, audit_ref, correlation_id "
        "FROM plan_execution_dispatches ORDER BY execution_unit_id"
    ),
    "plan_execution_graphs": (
        "SELECT plan_execution_graph_id, step_count, audit_ref "
        "FROM plan_execution_graphs ORDER BY plan_execution_graph_id"
    ),
    "plan_revisions": (
        "SELECT plan_revision_id, status, audit_ref FROM plan_revisions ORDER BY plan_revision_id"
    ),
    "reasoning_invocations": (
        "SELECT invocation_id, status, attempt, completed_at, audit_ref, outcome_ref "
        "FROM reasoning_invocations ORDER BY invocation_id"
    ),
    "discussion_sessions": (
        "SELECT discussion_id, state, stop_reason, current_round, turns_taken, messages_posted, "
        "invocations_started, updated_at FROM discussion_sessions ORDER BY discussion_id"
    ),
    "project_work_items": (
        "SELECT id, status, lifecycle_state, updated_at FROM project_work_items ORDER BY id"
    ),
}


async def _snapshot() -> dict[str, object]:
    """Row counts for every canonical table, plus content digests for the mutable ones."""
    conn = await PlanDelegationStore()._connect()
    try:
        snapshot: dict[str, object] = {}
        for table in CANONICAL_TABLES:
            snapshot[f"count:{table}"] = int(await conn.fetchval(f"SELECT count(*) FROM {table}"))
        for table, query in _HASHED.items():
            snapshot[f"digest:{table}"] = await conn.fetchval(
                f"SELECT md5(coalesce(string_agg(t.*::text, '|'), '')) FROM ({query}) t"
            )
        return snapshot
    finally:
        await conn.close()


def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(autonomy_observability_api.router)
    return TestClient(app)


def _diff(before: dict[str, object], after: dict[str, object]) -> dict[str, tuple]:
    return {k: (before[k], after[k]) for k in before if before[k] != after[k]}


@pytest.mark.asyncio
async def test_repeated_reads_of_every_endpoint_mutate_nothing():
    """The whole surface, hit repeatedly, against a lineage rich enough for every code path."""
    audit = DirectAuditClient()
    case = await scheduled(audit=audit)
    await complete_step(case, "design")
    unit_id = str((await units_by_step(case))["build"]["execution_unit_id"])
    client = _client()

    paths = [
        f"/operations/autonomy/goals/{case['goal_id']}",
        f"/operations/autonomy/goals/{case['goal_id']}/plan-revisions",
        f"/operations/autonomy/goals/{case['goal_id']}/timeline",
        f"/operations/autonomy/plan-revisions/{case['plan_revision_id']}/execution-graph",
        f"/operations/autonomy/execution-units/{unit_id}",
        f"/operations/autonomy/discussions/{case['discussion_id']}/reasoning",
    ]

    before = await _snapshot()
    for _ in range(3):
        for path in paths:
            assert client.get(path).status_code == 200, path
    after = await _snapshot()

    assert _diff(before, after) == {}


@pytest.mark.asyncio
async def test_reading_a_state_that_still_owes_work_does_not_perform_that_work():
    """The sharpest case: a graph with ready units and an unfinished DAG, read over and over.

    A read model that "helpfully" advanced anything would show up here as a dispatch row, a state
    transition or a published_at that reading created. The next-work projection names exactly what
    a scheduler pass would do next, and naming it must not do it.
    """
    case = await scheduled()
    await complete_step(case, "design")
    service = AutonomyObservabilityService()

    before = await _snapshot()
    for _ in range(5):
        overview = await service.goal_overview(case["goal_id"])
        assert overview["next_work"]["ready_units"], "the projection must have work to name"
        await service.execution_graph(case["plan_revision_id"])
    after = await _snapshot()

    assert _diff(before, after) == {}
    # And the work it named is still waiting, not done.
    final = await service.goal_overview(case["goal_id"])
    assert [u["step_key"] for u in final["next_work"]["ready_units"]] == ["build"]


@pytest.mark.asyncio
async def test_reading_a_stale_lineage_neither_rebinds_it_nor_completes_it():
    """A superseded revision with unfinished work is where a "reconciler" would want to intervene."""
    case = await scheduled()
    await complete_step(case, "design")
    historical = case["plan_revision_id"]
    await supersede_with(case)
    service = AutonomyObservabilityService()

    before = await _snapshot()
    for _ in range(3):
        await service.execution_graph(historical)
        await service.goal_overview(case["goal_id"])
        await service.plan_revision_history(case["goal_id"])
    after = await _snapshot()

    assert _diff(before, after) == {}


@pytest.mark.asyncio
async def test_reading_never_writes_a_business_audit_event():
    """Viewing a page is not a decision. An audit chain that records reads stops being a record."""
    audit = DirectAuditClient()
    case = await scheduled(audit=audit)
    client = _client()

    conn = await PlanDelegationStore()._connect()
    try:
        before = int(await conn.fetchval("SELECT count(*) FROM audit_logs"))
    finally:
        await conn.close()

    for _ in range(4):
        client.get(f"/operations/autonomy/goals/{case['goal_id']}")
        client.get(f"/operations/autonomy/goals/{case['goal_id']}/timeline")

    conn = await PlanDelegationStore()._connect()
    try:
        after = int(await conn.fetchval("SELECT count(*) FROM audit_logs"))
    finally:
        await conn.close()
    assert after == before


@pytest.mark.asyncio
async def test_the_read_path_never_opens_a_redis_connection():
    """Redis is not a source of product truth here, and it is not on the read path at all.

    Asserted by breaking it: any attempt to construct the event bus during a read raises. A read
    that silently degraded when the broker was down would still be reading Redis.
    """
    await read_store_or_skip()
    import shared.sdk.event_bus.redis_streams as redis_streams

    case = await scheduled()
    original = redis_streams.RedisStreamEventBus

    class Refuses:
        def __init__(self, *a, **kw):
            raise AssertionError("AT-M3.6A read path constructed a Redis event bus")

    redis_streams.RedisStreamEventBus = Refuses  # type: ignore[misc]
    try:
        service = AutonomyObservabilityService()
        overview = await service.goal_overview(case["goal_id"])
        await service.execution_graph(case["plan_revision_id"])
        await service.goal_timeline(case["goal_id"])
    finally:
        redis_streams.RedisStreamEventBus = original  # type: ignore[misc]

    # The dispatch it reports was published, and PostgreSQL is what said so.
    unit = next(u for u in overview["current_units"] if u["step_key"] == "design")
    assert unit["dispatch_state"] == "DISPATCHED_TO_CONTROL_STREAM"
    assert overview["read_model"]["redis_consulted"] is False


def test_the_read_modules_contain_no_write_statement_at_all():
    """The store's contract is "every statement is a SELECT". This checks the statements.

    Parsed rather than grepped, and docstrings are excluded deliberately: these modules DISCUSS the
    writes they do not perform, at length, and a text scan would flag their own explanation of why
    they perform none. What is scanned is every string literal that is not a docstring -- which in
    an asyncpg store is exactly the set of SQL it can execute -- matched on word boundaries, so a
    field named ``turns_truncated`` is not mistaken for a TRUNCATE.
    """
    import ast
    import re

    write_statement = re.compile(
        r"(INSERT\s+INTO|UPDATE\s+\w|DELETE\s+FROM|FOR\s+(NO\s+KEY\s+)?UPDATE|FOR\s+SHARE"
        r"|CREATE\s+(TABLE|INDEX)|ALTER\s+TABLE|DROP\s+(TABLE|INDEX)|TRUNCATE|NEXTVAL"
        r"|PG_ADVISORY\w*)",
        re.IGNORECASE,
    )

    for module in ("store.py", "service.py", "models.py", "contracts.py"):
        source = (ROOT / "shared" / "sdk" / "autonomy_observability" / module).read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        docstrings = set()
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)
                ):
                    docstrings.add(id(body[0].value))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
            ):
                found = write_statement.search(node.value)
                assert not found, (module, found.group(0), node.value[:120])

    # And the only asyncpg calls the store makes are the reading ones. `execute` is how a write
    # would be issued without the SQL ever appearing as a literal here.
    store_tree = ast.parse(
        (ROOT / "shared" / "sdk" / "autonomy_observability" / "store.py").read_text(
            encoding="utf-8"
        )
    )
    calls = {
        node.func.attr
        for node in ast.walk(store_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "execute" not in calls
    assert "executemany" not in calls
    assert "copy_records_to_table" not in calls
    assert {"fetch", "fetchrow", "fetchval"} & calls
