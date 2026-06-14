"""Stage 45 -- dependency validator tests."""

from __future__ import annotations

from shared.sdk.project_planning.dependency_validator import (
    ERR_CYCLE,
    ERR_DUPLICATE_DEPENDENCY,
    ERR_MISSING_NODE,
    ERR_SELF_DEPENDENCY,
    STATUS_INVALID,
    STATUS_VALID,
    validate_dependencies,
)
from shared.sdk.project_planning.models import (
    ProjectWorkItem,
    TaskGraph,
    WorkItemDependency,
)


def _graph(work_keys, deps):
    return TaskGraph(
        project_type="t",
        template="t",
        work_items=[ProjectWorkItem(work_item_key=k, title=k) for k in work_keys],
        dependencies=[
            WorkItemDependency(work_item_key=a, depends_on_work_item_key=b) for (a, b) in deps
        ],
    )


def test_valid_graph() -> None:
    g = _graph(["A", "B", "C"], [("B", "A"), ("C", "B")])
    assert validate_dependencies(g).status == STATUS_VALID


def test_self_dependency_invalid() -> None:
    g = _graph(["A"], [("A", "A")])
    v = validate_dependencies(g)
    assert v.status == STATUS_INVALID
    assert any(e["type"] == ERR_SELF_DEPENDENCY for e in v.errors)


def test_duplicate_dependency_invalid() -> None:
    g = _graph(["A", "B"], [("A", "B"), ("A", "B")])
    v = validate_dependencies(g)
    assert v.status == STATUS_INVALID
    assert any(e["type"] == ERR_DUPLICATE_DEPENDENCY for e in v.errors)


def test_missing_node_invalid() -> None:
    g = _graph(["A"], [("A", "Z")])
    v = validate_dependencies(g)
    assert v.status == STATUS_INVALID
    assert any(e["type"] == ERR_MISSING_NODE for e in v.errors)


def test_cycle_invalid() -> None:
    g = _graph(["A", "B", "C"], [("A", "B"), ("B", "C"), ("C", "A")])
    v = validate_dependencies(g)
    assert v.status == STATUS_INVALID
    assert any(e["type"] == ERR_CYCLE for e in v.errors)
