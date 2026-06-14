"""Stage 45 -- Project Planner & Task Graph Orchestration SDK."""

from __future__ import annotations

from shared.sdk.project_planning.acceptance import build_acceptance_criteria
from shared.sdk.project_planning.assignment_policy import (
    EXISTING_AGENT_ROLES,
    FUTURE_AGENT_ROLES,
    assign_agent_role,
    is_future_role,
    is_runnable_role,
    resolve_dispatch_policy,
)
from shared.sdk.project_planning.audit_events import (
    STAGE_45_DECISION_TYPES,
    safe_project_artifact_refs,
)
from shared.sdk.project_planning.brief_builder import (
    TEMPLATE_FASTAPI_TODO,
    TEMPLATE_GENERIC,
    build_brief,
    detect_template,
)
from shared.sdk.project_planning.delivery_readiness import (
    DeliveryReadiness,
    evaluate_delivery_readiness,
)
from shared.sdk.project_planning.dependency_validator import (
    GraphValidation,
    validate_dependencies,
)
from shared.sdk.project_planning.events import (
    PROJECT_NOTIFICATION_EVENTS,
    STREAM_PROJECT_EVENTS,
    STREAM_PROJECT_PLANNING,
    STREAM_PROJECT_WORK_ITEMS,
)
from shared.sdk.project_planning.models import (
    AcceptanceCriterion,
    PlannerInput,
    PlannerOutput,
    ProjectBrief,
    ProjectCreate,
    ProjectMilestone,
    ProjectRisk,
    ProjectWorkItem,
    TaskGraph,
    UserStory,
    WorkItemDependency,
)
from shared.sdk.project_planning.planner import PLANNER_AGENT, plan_project
from shared.sdk.project_planning.routing import (
    PROJECT_REQUEST_TYPES,
    planning_only_enabled,
    project_planner_enabled,
    should_route_to_project_planner,
    work_item_dispatch_enabled,
)
from shared.sdk.project_planning.story_builder import build_user_stories
from shared.sdk.project_planning.store import ProjectPlanningStore
from shared.sdk.project_planning.task_graph import (
    build_task_graph,
    graph_hash,
    graph_nodes_edges,
)

__all__ = [
    "AcceptanceCriterion",
    "PlannerInput",
    "PlannerOutput",
    "ProjectBrief",
    "ProjectCreate",
    "ProjectMilestone",
    "ProjectRisk",
    "ProjectWorkItem",
    "TaskGraph",
    "UserStory",
    "WorkItemDependency",
    "ProjectPlanningStore",
    "plan_project",
    "PLANNER_AGENT",
    "build_brief",
    "detect_template",
    "TEMPLATE_FASTAPI_TODO",
    "TEMPLATE_GENERIC",
    "build_user_stories",
    "build_acceptance_criteria",
    "build_task_graph",
    "graph_hash",
    "graph_nodes_edges",
    "validate_dependencies",
    "GraphValidation",
    "assign_agent_role",
    "resolve_dispatch_policy",
    "is_runnable_role",
    "is_future_role",
    "EXISTING_AGENT_ROLES",
    "FUTURE_AGENT_ROLES",
    "evaluate_delivery_readiness",
    "DeliveryReadiness",
    "should_route_to_project_planner",
    "project_planner_enabled",
    "planning_only_enabled",
    "work_item_dispatch_enabled",
    "PROJECT_REQUEST_TYPES",
    "STREAM_PROJECT_PLANNING",
    "STREAM_PROJECT_EVENTS",
    "STREAM_PROJECT_WORK_ITEMS",
    "PROJECT_NOTIFICATION_EVENTS",
    "STAGE_45_DECISION_TYPES",
    "safe_project_artifact_refs",
]
