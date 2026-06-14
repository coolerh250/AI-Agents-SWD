"""Stage 45 -- task-graph dependency validator.

Pure, deterministic graph validation. Detects:

* self dependency
* duplicate dependency
* dependency referencing a missing node
* cycles
* unreachable terminal work items (warning)

Returns a ``GraphValidation`` with ``status`` in valid/invalid/warning
and a list of structured errors.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shared.sdk.project_planning.models import TaskGraph, WorkItemDependency

STATUS_VALID = "valid"
STATUS_INVALID = "invalid"
STATUS_WARNING = "warning"

ERR_SELF_DEPENDENCY = "self_dependency"
ERR_DUPLICATE_DEPENDENCY = "duplicate_dependency"
ERR_MISSING_NODE = "missing_node"
ERR_CYCLE = "cycle"
WARN_UNREACHABLE_TERMINAL = "unreachable_terminal"


@dataclass
class GraphValidation:
    status: str
    errors: list[dict] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.status == STATUS_VALID

    def to_list(self) -> list[dict]:
        return list(self.errors)


def _node_keys(graph: TaskGraph) -> set[str]:
    return {wi.work_item_key for wi in graph.work_items}


def _find_cycle(
    adjacency: dict[str, list[str]],
) -> list[str] | None:
    """Return one cycle path if the directed graph has a cycle, else None."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {node: WHITE for node in adjacency}
    parent: dict[str, str | None] = {}

    def visit(start: str) -> list[str] | None:
        stack = [(start, iter(adjacency.get(start, [])))]
        color[start] = GRAY
        parent[start] = None
        while stack:
            node, it = stack[-1]
            advanced = False
            for nxt in it:
                if nxt not in color:
                    continue
                if color[nxt] == WHITE:
                    color[nxt] = GRAY
                    parent[nxt] = node
                    stack.append((nxt, iter(adjacency.get(nxt, []))))
                    advanced = True
                    break
                if color[nxt] == GRAY:
                    # back-edge -> reconstruct the cycle
                    path = [nxt, node]
                    cur = parent.get(node)
                    while cur is not None and cur != nxt:
                        path.append(cur)
                        cur = parent.get(cur)
                    path.reverse()
                    return path
            if not advanced:
                color[node] = BLACK
                stack.pop()
        return None

    for node in adjacency:
        if color[node] == WHITE:
            found = visit(node)
            if found:
                return found
    return None


def validate_dependencies(graph: TaskGraph) -> GraphValidation:
    nodes = _node_keys(graph)
    errors: list[dict] = []
    seen_pairs: set[tuple[str, str]] = set()
    # adjacency for cycle detection: work_item -> depends_on
    adjacency: dict[str, list[str]] = {key: [] for key in nodes}

    for dep in graph.dependencies:
        a = dep.work_item_key
        b = dep.depends_on_work_item_key
        if a == b:
            errors.append({"type": ERR_SELF_DEPENDENCY, "work_item_key": a})
            continue
        if a not in nodes:
            errors.append({"type": ERR_MISSING_NODE, "work_item_key": a})
            continue
        if b not in nodes:
            errors.append({"type": ERR_MISSING_NODE, "work_item_key": b})
            continue
        pair = (a, b)
        if pair in seen_pairs:
            errors.append({"type": ERR_DUPLICATE_DEPENDENCY, "work_item_key": a, "depends_on": b})
            continue
        seen_pairs.add(pair)
        adjacency[a].append(b)

    # Cycle detection only when references are structurally sound so far.
    structural = [e for e in errors if e["type"] in (ERR_SELF_DEPENDENCY, ERR_MISSING_NODE)]
    if not structural:
        cycle = _find_cycle(adjacency)
        if cycle:
            errors.append({"type": ERR_CYCLE, "path": cycle})

    has_hard_error = any(
        e["type"] in (ERR_SELF_DEPENDENCY, ERR_DUPLICATE_DEPENDENCY, ERR_MISSING_NODE, ERR_CYCLE)
        for e in errors
    )
    if has_hard_error:
        return GraphValidation(status=STATUS_INVALID, errors=errors)

    # Reachability warning: every node should be connected to the graph
    # (either depends on something or is depended upon) when there are deps.
    if graph.dependencies:
        connected: set[str] = set()
        for a, b in seen_pairs:
            connected.add(a)
            connected.add(b)
        isolated = sorted(nodes - connected)
        if isolated:
            errors.append({"type": WARN_UNREACHABLE_TERMINAL, "work_item_keys": isolated})
            return GraphValidation(status=STATUS_WARNING, errors=errors)

    return GraphValidation(status=STATUS_VALID, errors=errors)


def make_dependency(work_item_key: str, depends_on: str, dependency_type: str = "blocks"):
    """Small helper used by tests to construct a dependency."""
    return WorkItemDependency(
        work_item_key=work_item_key,
        depends_on_work_item_key=depends_on,
        dependency_type=dependency_type,
    )


__all__ = [
    "GraphValidation",
    "validate_dependencies",
    "make_dependency",
    "STATUS_VALID",
    "STATUS_INVALID",
    "STATUS_WARNING",
    "ERR_SELF_DEPENDENCY",
    "ERR_DUPLICATE_DEPENDENCY",
    "ERR_MISSING_NODE",
    "ERR_CYCLE",
    "WARN_UNREACHABLE_TERMINAL",
]
