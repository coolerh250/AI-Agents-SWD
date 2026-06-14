"""Stage 45 -- project planning orchestration.

Ties together brief_builder -> task_graph -> dependency_validator ->
store, emits audit + notification events + metrics, and returns a
``PlannerOutput``. Used by BOTH the project-planner-agent (stream path)
and ``POST /operations/projects/plan`` (synchronous path).

Planning-only: never calls an LLM, never writes GitHub, never deploys.
``production_executed`` is always False.
"""

from __future__ import annotations

import contextlib

from shared.sdk.observability.metrics import (
    PROJECT_ACCEPTANCE_CRITERIA_CREATED_TOTAL,
    PROJECT_PLANNING_FAILURES_TOTAL,
    PROJECT_PLANNING_RUNS_TOTAL,
    PROJECT_TASK_GRAPH_EDGES_TOTAL,
    PROJECT_TASK_GRAPH_NODES_TOTAL,
    PROJECT_TASK_GRAPH_VALIDATION_FAILURES_TOTAL,
    PROJECT_WORK_ITEMS_CREATED_TOTAL,
)
from shared.sdk.observability.tracing import start_span
from shared.sdk.project_planning.audit_events import (
    DECISION_PROJECT_BRIEF_CREATED,
    DECISION_PROJECT_PLANNING_COMPLETED,
    DECISION_PROJECT_PLANNING_FAILED,
    DECISION_PROJECT_PLANNING_STARTED,
    DECISION_PROJECT_TASK_GRAPH_CREATED,
    DECISION_PROJECT_TASK_GRAPH_VALIDATED,
    safe_project_artifact_refs,
)
from shared.sdk.project_planning.brief_builder import build_brief, detect_template
from shared.sdk.project_planning.dependency_validator import (
    STATUS_VALID,
    validate_dependencies,
)
from shared.sdk.project_planning.events import (
    EVENT_PROJECT_CLARIFICATION_REQUIRED,
    EVENT_PROJECT_GRAPH_VALIDATED,
    EVENT_PROJECT_PLANNING_COMPLETED,
    EVENT_PROJECT_PLANNING_STARTED,
)
from shared.sdk.project_planning.models import (
    PlannerInput,
    PlannerOutput,
    ProjectArtifact,
    ProjectCreate,
)
from shared.sdk.project_planning.story_builder import build_user_stories
from shared.sdk.project_planning.task_graph import (
    build_task_graph,
    graph_hash,
    graph_nodes_edges,
)

PLANNER_AGENT = "project-planner-agent"


async def _audit(
    *,
    task_id: str | None,
    decision_type: str,
    summary: str,
    result: str,
    artifact_refs: dict,
) -> None:
    with contextlib.suppress(Exception):
        from shared.sdk.audit.publisher import publish_audit_event

        await publish_audit_event(
            task_id=task_id,
            agent=PLANNER_AGENT,
            decision_type=decision_type,
            summary=summary,
            result=result,
            artifact_refs=artifact_refs,
        )


async def _notify(task_id: str | None, event_type: str, message: str) -> None:
    with contextlib.suppress(Exception):
        from shared.sdk.notifications.client import send_notification

        await send_notification(task_id or "unknown", event_type, message)


async def plan_project(
    planner_input: PlannerInput,
    store,
    *,
    emit_events: bool = True,
    planning_only: bool = True,
    dispatch_policy_default: str = "planning_only",
) -> PlannerOutput:
    """Plan a project and persist its full graph. Returns a PlannerOutput."""
    template = detect_template(planner_input.request_text)
    project_type = planner_input.project_type or template
    with start_span(
        "project_planning.run",
        **{
            "service.name": PLANNER_AGENT,
            "task_id": planner_input.task_id or "",
            "project_type": project_type,
        },
    ):
        if emit_events:
            await _audit(
                task_id=planner_input.task_id,
                decision_type=DECISION_PROJECT_PLANNING_STARTED,
                summary=f"project planning started (type={project_type})",
                result="started",
                artifact_refs={"project_type": project_type, "production_executed": False},
            )
            await _notify(
                planner_input.task_id,
                EVENT_PROJECT_PLANNING_STARTED,
                f"project planning started (type={project_type})",
            )

        try:
            return await _plan_inner(
                planner_input,
                store,
                project_type=project_type,
                emit_events=emit_events,
                dispatch_policy_default=dispatch_policy_default,
            )
        except Exception as exc:
            PROJECT_PLANNING_FAILURES_TOTAL.labels(project_type=project_type).inc()
            PROJECT_PLANNING_RUNS_TOTAL.labels(project_type=project_type, status="failed").inc()
            if emit_events:
                await _audit(
                    task_id=planner_input.task_id,
                    decision_type=DECISION_PROJECT_PLANNING_FAILED,
                    summary=f"project planning failed: {exc}",
                    result="failed",
                    artifact_refs={"project_type": project_type, "production_executed": False},
                )
            raise


async def _plan_inner(
    planner_input: PlannerInput,
    store,
    *,
    project_type: str,
    emit_events: bool,
    dispatch_policy_default: str,
) -> PlannerOutput:
    with start_span("project_planning.build_brief"):
        brief = build_brief(
            planner_input.request_text,
            requirement_summary=planner_input.requirement_summary,
        )

    title = (planner_input.request_text or "Untitled project").strip()[:120]

    # --- clarification path -------------------------------------------------
    if brief.requires_clarification:
        project = await store.create_project(
            ProjectCreate(
                title=title,
                summary=planner_input.requirement_summary or "",
                source_task_id=planner_input.task_id,
                request_source=planner_input.source,
                requester=planner_input.requester,
                project_type=project_type,
                status="draft",
                autonomy_level=planner_input.autonomy_level,
                risk_level="low",
            )
        )
        project_id = project["id"]
        brief_id = await store.create_project_brief(project_id, brief)
        await store.create_artifacts(
            project_id,
            [
                ProjectArtifact(
                    artifact_type="clarification_needed",
                    title="Clarification required before planning",
                    content={"reason": "request_too_vague"},
                )
            ],
        )
        PROJECT_PLANNING_RUNS_TOTAL.labels(
            project_type=project_type, status="requires_clarification"
        ).inc()
        if emit_events:
            await _audit(
                task_id=planner_input.task_id,
                decision_type=DECISION_PROJECT_PLANNING_FAILED,
                summary="project planning requires clarification",
                result="requires_clarification",
                artifact_refs=safe_project_artifact_refs(
                    project_id=project_id,
                    brief_id=brief_id,
                    requires_clarification=True,
                    template=project_type,
                ),
            )
            await _notify(
                planner_input.task_id,
                EVENT_PROJECT_CLARIFICATION_REQUIRED,
                f"project {project_id} requires clarification",
            )
        return PlannerOutput(
            project_id=project_id,
            brief_id=brief_id,
            work_items_count=0,
            validation_status="warning",
            requires_clarification=True,
            planning_only=True,
            production_executed=False,
            status="draft",
            template=project_type,
        )

    # --- full planning path -------------------------------------------------
    project = await store.create_project(
        ProjectCreate(
            title=title,
            summary=brief.goal,
            source_task_id=planner_input.task_id,
            request_source=planner_input.source,
            requester=planner_input.requester,
            project_type=project_type,
            status="planning",
            autonomy_level=planner_input.autonomy_level,
            risk_level="low",
        )
    )
    project_id = project["id"]

    brief_id = await store.create_project_brief(project_id, brief)
    if emit_events:
        await _audit(
            task_id=planner_input.task_id,
            decision_type=DECISION_PROJECT_BRIEF_CREATED,
            summary="project brief created",
            result="created",
            artifact_refs=safe_project_artifact_refs(
                project_id=project_id, brief_id=brief_id, template=project_type
            ),
        )

    stories = build_user_stories(brief, template=brief.metadata.get("template", project_type))
    await store.create_user_stories(project_id, stories)

    with start_span("project_planning.build_task_graph"):
        graph = build_task_graph(
            brief,
            project_type=project_type,
            dispatch_policy_default=dispatch_policy_default,
        )

    with start_span("project_planning.validate_dependencies"):
        validation = validate_dependencies(graph)
    if validation.status != STATUS_VALID:
        PROJECT_TASK_GRAPH_VALIDATION_FAILURES_TOTAL.labels(
            validation_status=validation.status
        ).inc()

    # persist milestones -> work items -> dependencies -> acceptance -> risks
    with start_span("project_planning.persist_graph"):
        milestone_ids = await store.create_milestones(project_id, graph.milestones)
        work_item_ids = await store.create_work_items(
            project_id, graph.work_items, milestone_ids=milestone_ids
        )
        deps_count = await store.create_dependencies(
            project_id, graph.dependencies, work_item_ids=work_item_ids
        )
        ac_count = await store.create_acceptance_criteria(
            project_id, graph.acceptance_criteria, work_item_ids=work_item_ids
        )
        risks_count = await store.create_risks(project_id, graph.risks)

        nodes, edges = graph_nodes_edges(graph)
        snapshot_id = await store.create_graph_snapshot(
            project_id,
            version=1,
            graph_hash=graph_hash(graph),
            nodes=nodes,
            edges=edges,
            validation_status=validation.status,
            validation_errors=validation.to_list(),
            metadata={"template": graph.template},
        )

    # task_graph artifact reference
    await store.create_artifacts(
        project_id,
        [
            ProjectArtifact(
                artifact_type="project_brief",
                title="Project brief",
                content=None,
                metadata={"brief_id": brief_id},
            ),
            ProjectArtifact(
                artifact_type="task_graph",
                title="Task graph snapshot",
                content=None,
                metadata={"graph_snapshot_id": snapshot_id},
            ),
        ],
    )

    PROJECT_TASK_GRAPH_NODES_TOTAL.labels(project_type=project_type).inc(len(graph.work_items))
    PROJECT_TASK_GRAPH_EDGES_TOTAL.labels(project_type=project_type).inc(deps_count)
    PROJECT_WORK_ITEMS_CREATED_TOTAL.labels(project_type=project_type).inc(len(graph.work_items))
    PROJECT_ACCEPTANCE_CRITERIA_CREATED_TOTAL.labels(project_type=project_type).inc(ac_count)

    final_status = "planned"
    await store.update_project_status(project_id, final_status)

    if emit_events:
        await _audit(
            task_id=planner_input.task_id,
            decision_type=DECISION_PROJECT_TASK_GRAPH_CREATED,
            summary="project task graph created",
            result="created",
            artifact_refs=safe_project_artifact_refs(
                project_id=project_id,
                graph_snapshot_id=snapshot_id,
                work_items_count=len(graph.work_items),
                dependencies_count=deps_count,
                acceptance_criteria_count=ac_count,
                template=project_type,
            ),
        )
        await _audit(
            task_id=planner_input.task_id,
            decision_type=DECISION_PROJECT_TASK_GRAPH_VALIDATED,
            summary=f"project task graph validated: {validation.status}",
            result=validation.status,
            artifact_refs=safe_project_artifact_refs(
                project_id=project_id,
                graph_snapshot_id=snapshot_id,
                validation_status=validation.status,
            ),
        )
        await _notify(
            planner_input.task_id,
            EVENT_PROJECT_GRAPH_VALIDATED,
            f"project {project_id} graph validated: {validation.status}",
        )
        await _audit(
            task_id=planner_input.task_id,
            decision_type=DECISION_PROJECT_PLANNING_COMPLETED,
            summary="project planning completed (planning-only)",
            result="completed",
            artifact_refs=safe_project_artifact_refs(
                project_id=project_id,
                graph_snapshot_id=snapshot_id,
                brief_id=brief_id,
                validation_status=validation.status,
                work_items_count=len(graph.work_items),
                dependencies_count=deps_count,
                acceptance_criteria_count=ac_count,
                template=project_type,
            ),
        )
        await _notify(
            planner_input.task_id,
            EVENT_PROJECT_PLANNING_COMPLETED,
            f"project {project_id} planning completed ({len(graph.work_items)} work items)",
        )

    PROJECT_PLANNING_RUNS_TOTAL.labels(project_type=project_type, status="completed").inc()

    return PlannerOutput(
        project_id=project_id,
        brief_id=brief_id,
        graph_snapshot_id=snapshot_id,
        work_items_count=len(graph.work_items),
        dependencies_count=deps_count,
        acceptance_criteria_count=ac_count,
        risks_count=risks_count,
        milestones_count=len(graph.milestones),
        user_stories_count=len(stories),
        validation_status=validation.status,
        requires_clarification=False,
        planning_only=True,
        production_executed=False,
        status=final_status,
        template=project_type,
    )


__all__ = ["plan_project", "PLANNER_AGENT"]
