"""Stage 45 -- task graph builder tests (FastAPI Todo template)."""

from __future__ import annotations

from shared.sdk.project_planning.brief_builder import build_brief
from shared.sdk.project_planning.task_graph import (
    build_task_graph,
    graph_hash,
    graph_nodes_edges,
)

FASTAPI_REQUEST = (
    "Create a FastAPI Todo Service with CRUD, SQLite, pytest, README, and API examples."
)


def _graph():
    brief = build_brief(FASTAPI_REQUEST)
    return build_task_graph(brief, project_type="fastapi_todo_service")


def test_fastapi_todo_graph_minimums() -> None:
    g = _graph()
    assert len(g.work_items) >= 8
    assert len(g.dependencies) >= 5
    assert len(g.acceptance_criteria) >= 8
    assert len(g.milestones) >= 7
    assert len(g.risks) >= 1


def test_work_item_keys_present() -> None:
    g = _graph()
    keys = {w.work_item_key for w in g.work_items}
    for expected in ("REQ-001", "ARCH-001", "BE-002", "DB-001", "QA-001", "DOC-001", "DEL-001"):
        assert expected in keys


def test_dependencies_reference_existing_nodes() -> None:
    g = _graph()
    keys = {w.work_item_key for w in g.work_items}
    for dep in g.dependencies:
        assert dep.work_item_key in keys
        assert dep.depends_on_work_item_key in keys


def test_nodes_edges_and_hash_deterministic() -> None:
    g = _graph()
    nodes, edges = graph_nodes_edges(g)
    assert len(nodes) == len(g.work_items)
    assert len(edges) == len(g.dependencies)
    assert graph_hash(g) == graph_hash(_graph())


def test_every_work_item_has_assigned_role() -> None:
    g = _graph()
    assert all(w.assigned_agent_role for w in g.work_items)
