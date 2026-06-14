"""Stage 45 -- deterministic task-graph builder.

Turns a project brief into a work-item graph (milestones, work items,
dependencies) plus acceptance criteria and risks. Template-driven; no
LLM. The first shipped template is ``fastapi_todo_service``.
"""

from __future__ import annotations

import hashlib
import json

from shared.sdk.project_planning.acceptance import build_acceptance_criteria
from shared.sdk.project_planning.assignment_policy import (
    assign_agent_role,
    resolve_dispatch_policy,
)
from shared.sdk.project_planning.brief_builder import (
    TEMPLATE_FASTAPI_TODO,
    TEMPLATE_GENERIC,
)
from shared.sdk.project_planning.models import (
    ProjectBrief,
    ProjectMilestone,
    ProjectWorkItem,
    TaskGraph,
    WorkItemDependency,
)
from shared.sdk.project_planning.risk_model import build_risks

# milestone_key, title
_FASTAPI_TODO_MILESTONES = [
    ("MS-1", "Requirement confirmation"),
    ("MS-2", "API/data design"),
    ("MS-3", "Backend implementation"),
    ("MS-4", "Test implementation"),
    ("MS-5", "Documentation"),
    ("MS-6", "QA validation"),
    ("MS-7", "Delivery package"),
]

# work_item_key, title, work_type, milestone_key
_FASTAPI_TODO_WORK_ITEMS = [
    ("REQ-001", "Clarify and freeze scope", "requirement", "MS-1"),
    ("ARCH-001", "Define API contract and data model", "architecture", "MS-2"),
    ("BE-001", "Implement FastAPI app structure", "backend", "MS-3"),
    ("BE-002", "Implement Todo CRUD endpoints", "backend", "MS-3"),
    ("DB-001", "Implement SQLite persistence", "database", "MS-3"),
    ("QA-001", "Create pytest unit/integration tests", "qa", "MS-4"),
    ("DOC-001", "Write README and API examples", "documentation", "MS-5"),
    ("QA-002", "Run tests and verify acceptance criteria", "qa", "MS-6"),
    ("DEL-001", "Prepare delivery summary", "release", "MS-7"),
]

# work_item_key, depends_on_work_item_key, dependency_type
_FASTAPI_TODO_DEPENDENCIES = [
    ("ARCH-001", "REQ-001", "requires_output"),
    ("BE-001", "ARCH-001", "requires_output"),
    ("BE-002", "ARCH-001", "requires_output"),
    ("BE-002", "BE-001", "blocks"),
    ("DB-001", "ARCH-001", "requires_output"),
    ("QA-001", "BE-002", "requires_output"),
    ("QA-001", "DB-001", "requires_output"),
    ("DOC-001", "BE-002", "informs"),
    ("QA-002", "QA-001", "requires_output"),
    ("QA-002", "DOC-001", "review_after"),
    ("DEL-001", "QA-002", "requires_output"),
]


def _work_item(
    key: str,
    title: str,
    work_type: str,
    milestone_key: str,
    *,
    dispatch_policy_default: str,
) -> ProjectWorkItem:
    role = assign_agent_role(work_type)
    risk = "low"
    priority = "high" if work_type in ("requirement", "architecture", "qa") else "medium"
    return ProjectWorkItem(
        work_item_key=key,
        title=title,
        work_type=work_type,
        assigned_agent_role=role,
        status="pending",
        priority=priority,
        risk_level=risk,
        dispatch_policy=resolve_dispatch_policy(
            work_type, risk, default_policy=dispatch_policy_default
        ),
        milestone_key=milestone_key,
    )


def build_task_graph(
    brief: ProjectBrief,
    *,
    project_type: str | None = None,
    dispatch_policy_default: str = "planning_only",
) -> TaskGraph:
    """Build a deterministic task graph from a brief."""
    template = str(brief.metadata.get("template") or TEMPLATE_GENERIC)
    if template == TEMPLATE_FASTAPI_TODO:
        milestones = [
            ProjectMilestone(milestone_key=k, title=t, order_index=i)
            for i, (k, t) in enumerate(_FASTAPI_TODO_MILESTONES)
        ]
        work_items = [
            _work_item(k, t, wt, ms, dispatch_policy_default=dispatch_policy_default)
            for (k, t, wt, ms) in _FASTAPI_TODO_WORK_ITEMS
        ]
        dependencies = [
            WorkItemDependency(work_item_key=wi, depends_on_work_item_key=dep, dependency_type=dt)
            for (wi, dep, dt) in _FASTAPI_TODO_DEPENDENCIES
        ]
    else:
        milestones = [
            ProjectMilestone(milestone_key="MS-1", title="Requirement confirmation", order_index=0),
            ProjectMilestone(milestone_key="MS-2", title="Implementation", order_index=1),
            ProjectMilestone(milestone_key="MS-3", title="Validation", order_index=2),
        ]
        work_items = [
            _work_item(
                "REQ-001",
                "Clarify and freeze scope",
                "requirement",
                "MS-1",
                dispatch_policy_default=dispatch_policy_default,
            ),
            _work_item(
                "IMPL-001",
                "Implement the requested capability",
                "backend",
                "MS-2",
                dispatch_policy_default=dispatch_policy_default,
            ),
            _work_item(
                "QA-001",
                "Test the implementation",
                "qa",
                "MS-3",
                dispatch_policy_default=dispatch_policy_default,
            ),
            _work_item(
                "DOC-001",
                "Document the result",
                "documentation",
                "MS-2",
                dispatch_policy_default=dispatch_policy_default,
            ),
        ]
        dependencies = [
            WorkItemDependency(
                work_item_key="IMPL-001",
                depends_on_work_item_key="REQ-001",
                dependency_type="requires_output",
            ),
            WorkItemDependency(
                work_item_key="QA-001",
                depends_on_work_item_key="IMPL-001",
                dependency_type="requires_output",
            ),
            WorkItemDependency(
                work_item_key="DOC-001",
                depends_on_work_item_key="IMPL-001",
                dependency_type="informs",
            ),
        ]

    acceptance = build_acceptance_criteria(brief, template=template)
    risks = build_risks(brief, template=template)
    return TaskGraph(
        project_type=project_type or template,
        template=template,
        milestones=milestones,
        work_items=work_items,
        dependencies=dependencies,
        acceptance_criteria=acceptance,
        risks=risks,
    )


def graph_nodes_edges(graph: TaskGraph) -> tuple[list[dict], list[dict]]:
    """Render the graph as JSON-able nodes/edges for a snapshot."""
    nodes = [
        {
            "key": wi.work_item_key,
            "title": wi.title,
            "work_type": wi.work_type,
            "assigned_agent_role": wi.assigned_agent_role,
            "milestone_key": wi.milestone_key,
            "dispatch_policy": wi.dispatch_policy,
        }
        for wi in graph.work_items
    ]
    edges = [
        {
            "from": dep.work_item_key,
            "to": dep.depends_on_work_item_key,
            "dependency_type": dep.dependency_type,
        }
        for dep in graph.dependencies
    ]
    return nodes, edges


def graph_hash(graph: TaskGraph) -> str:
    """Deterministic hash of the graph nodes + edges."""
    nodes, edges = graph_nodes_edges(graph)
    canonical = json.dumps({"nodes": nodes, "edges": edges}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "build_task_graph",
    "graph_nodes_edges",
    "graph_hash",
]
