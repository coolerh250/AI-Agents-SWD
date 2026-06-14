"""Stage 46 -- design review orchestration.

Loads project context from the project planning store, builds the
discussion + design review deterministically, persists everything, emits
audit + notification events + metrics, and returns a ``DesignReviewOutput``.

Used by BOTH the design-review-agent (stream path) and
``POST /operations/projects/{id}/design-review`` (synchronous path).

Review-only / planning-only: never calls an LLM, never writes a repo,
never opens a PR, never deploys, never dispatches work items.
"""

from __future__ import annotations

import contextlib

from shared.sdk.agent_discussion.audit_events import (
    DECISION_AGENT_DISCUSSION_COMPLETED,
    DECISION_AGENT_DISCUSSION_STARTED,
)
from shared.sdk.agent_discussion.contribution_templates import build_contributions
from shared.sdk.agent_discussion.events import (
    EVENT_DISCUSSION_SESSION_COMPLETED,
    EVENT_DISCUSSION_SESSION_STARTED,
)
from shared.sdk.agent_discussion.models import DiscussionArtifact
from shared.sdk.agent_discussion.session_builder import build_session
from shared.sdk.design_review.audit_events import (
    DECISION_DESIGN_REVIEW_BLOCKED,
    DECISION_DESIGN_REVIEW_COMPLETED,
    DECISION_DESIGN_REVIEW_GO_NO_GO_RECORDED,
    DECISION_DESIGN_REVIEW_STARTED,
    safe_review_artifact_refs,
)
from shared.sdk.design_review.events import (
    EVENT_DESIGN_REVIEW_BLOCKED,
    EVENT_DESIGN_REVIEW_COMPLETED,
    EVENT_DESIGN_REVIEW_GO_NO_GO_RECORDED,
    EVENT_DESIGN_REVIEW_STARTED,
)
from shared.sdk.design_review.models import (
    DesignReviewOutput,
    DesignReviewSession,
    ReviewContext,
)
from shared.sdk.design_review.report_builder import build_review_summary
from shared.sdk.design_review.review_builder import build_review
from shared.sdk.observability.metrics import (
    ACCEPTANCE_COVERAGE_CHECKS_TOTAL,
    AGENT_DISCUSSION_CONTRIBUTIONS_TOTAL,
    AGENT_DISCUSSION_SESSIONS_TOTAL,
    DESIGN_REVIEW_BLOCKING_FINDINGS_TOTAL,
    DESIGN_REVIEW_FINDINGS_TOTAL,
    DESIGN_REVIEW_GATES_EVALUATED_TOTAL,
    DESIGN_REVIEW_GO_NO_GO_TOTAL,
    DESIGN_REVIEW_SESSIONS_TOTAL,
)
from shared.sdk.observability.tracing import start_span

REVIEW_AGENT = "design-review-agent"


async def _audit(*, task_id, decision_type, summary, result, artifact_refs) -> None:
    with contextlib.suppress(Exception):
        from shared.sdk.audit.publisher import publish_audit_event

        await publish_audit_event(
            task_id=task_id,
            agent=REVIEW_AGENT,
            decision_type=decision_type,
            summary=summary,
            result=result,
            artifact_refs=artifact_refs,
        )


async def _notify(task_id, event_type, message) -> None:
    with contextlib.suppress(Exception):
        from shared.sdk.notifications.client import send_notification

        await send_notification(task_id or "unknown", event_type, message)


async def load_review_context(project_id: str, project_store) -> ReviewContext | None:
    """Load a ReviewContext from the project planning store."""
    project = await project_store.get_project(project_id)
    if project is None:
        return None
    brief = await project_store.get_brief(project_id) or {}
    snapshot = await project_store.get_latest_graph_snapshot(project_id)
    template = str(
        (
            project.get("project_type")
            or brief.get("metadata", {}).get("template")
            or "generic_software_project"
        )
    )
    return ReviewContext(
        project_id=project_id,
        template=template,
        brief=brief,
        user_stories=await project_store.list_user_stories(project_id),
        work_items=await project_store.list_work_items(project_id),
        dependencies=await project_store.list_dependencies(project_id),
        acceptance_criteria=await project_store.list_acceptance_criteria(project_id),
        risks=await project_store.list_risks(project_id),
        graph_validation_status=(snapshot or {}).get("validation_status", "valid"),
        graph_snapshot_id=(snapshot or {}).get("id"),
    )


async def run_design_review(
    *,
    project_id: str,
    project_store,
    discussion_store,
    review_store,
    review_type: str = "full_pre_execution",
    planning_only: bool = True,
    work_item_dispatch_enabled: bool = False,
    requested_by_agent: str = REVIEW_AGENT,
    source_task_id: str | None = None,
    emit_events: bool = True,
) -> DesignReviewOutput:
    """Run a full design review for a project and persist the result."""
    with start_span(
        "design_review.run",
        **{"service.name": REVIEW_AGENT, "project_id": project_id, "review_type": review_type},
    ):
        ctx = await load_review_context(project_id, project_store)
        if ctx is None:
            raise ValueError(f"project not found: {project_id}")

        if emit_events:
            await _audit(
                task_id=source_task_id,
                decision_type=DECISION_DESIGN_REVIEW_STARTED,
                summary=f"design review started for project {project_id}",
                result="started",
                artifact_refs=safe_review_artifact_refs(project_id=project_id),
            )
            await _notify(
                source_task_id,
                EVENT_DESIGN_REVIEW_STARTED,
                f"design review started for project {project_id}",
            )

        # --- discussion -----------------------------------------------------
        with start_span("agent_discussion.start_session"):
            session, participants = build_session(
                project_id=project_id,
                session_type="project_design_review",
                source_task_id=source_task_id,
                created_by_agent=requested_by_agent,
            )
            discussion_session_id = await discussion_store.create_discussion_session(session)
            await discussion_store.add_participants(discussion_session_id, participants)
        if emit_events:
            await _audit(
                task_id=source_task_id,
                decision_type=DECISION_AGENT_DISCUSSION_STARTED,
                summary=f"agent discussion started ({len(participants)} participants)",
                result="started",
                artifact_refs=safe_review_artifact_refs(
                    project_id=project_id, discussion_session_id=discussion_session_id
                ),
            )
            await _notify(
                source_task_id,
                EVENT_DISCUSSION_SESSION_STARTED,
                f"discussion started for project {project_id}",
            )
        AGENT_DISCUSSION_SESSIONS_TOTAL.labels(status="in_progress").inc()

        with start_span("agent_discussion.generate_contributions"):
            contributions = build_contributions(
                template=ctx.template,
                brief=ctx.brief,
                work_items=ctx.work_items,
                acceptance_criteria=ctx.acceptance_criteria,
                risks=ctx.risks,
                validation_status=ctx.graph_validation_status,
            )
            await discussion_store.add_contributions(
                discussion_session_id, contributions, project_id=project_id
            )
        AGENT_DISCUSSION_CONTRIBUTIONS_TOTAL.labels(review_type=review_type).inc(len(contributions))

        # --- review ---------------------------------------------------------
        review_session = DesignReviewSession(
            project_id=project_id,
            review_type=review_type,
            status="pending",
            decision="planning_only",
            graph_snapshot_id=ctx.graph_snapshot_id,
            discussion_session_id=discussion_session_id,
        )
        review_session_id = await review_store.create_design_review_session(review_session)

        with start_span("design_review.evaluate_gates"):
            result = build_review(
                ctx,
                planning_only=planning_only,
                work_item_dispatch_enabled=work_item_dispatch_enabled,
            )

        with start_span("design_review.persist_summary"):
            await review_store.add_findings(review_session_id, project_id, result.findings)
            await review_store.add_decisions(review_session_id, project_id, result.decisions)
            await review_store.upsert_review_gates(project_id, review_session_id, result.gates)
            await review_store.finalize_review_session(
                review_session_id, status=result.status, decision=result.decision
            )
            summary_artifact = build_review_summary(
                project_id=project_id, review_session_id=review_session_id, result=result
            )
            await discussion_store.add_discussion_artifact(
                discussion_session_id,
                DiscussionArtifact(
                    artifact_type="design_review_summary",
                    title="Design review summary",
                    content=summary_artifact,
                    created_by_agent=REVIEW_AGENT,
                ),
                project_id=project_id,
            )
            await discussion_store.complete_session(discussion_session_id, "completed")

        # --- metrics --------------------------------------------------------
        for f in result.findings:
            DESIGN_REVIEW_FINDINGS_TOTAL.labels(severity=f.severity).inc()
            if f.severity in ("high", "critical") and f.status == "open":
                DESIGN_REVIEW_BLOCKING_FINDINGS_TOTAL.labels(severity=f.severity).inc()
        for g in result.gates:
            DESIGN_REVIEW_GATES_EVALUATED_TOTAL.labels(status=g.status).inc()
        DESIGN_REVIEW_SESSIONS_TOTAL.labels(review_type=review_type, status=result.status).inc()
        DESIGN_REVIEW_GO_NO_GO_TOTAL.labels(decision=result.decision).inc()
        ACCEPTANCE_COVERAGE_CHECKS_TOTAL.labels(
            status="ok" if result.coverage.required else "no_required"
        ).inc()

        # --- audit + notify -------------------------------------------------
        if emit_events:
            refs = safe_review_artifact_refs(
                project_id=project_id,
                review_session_id=review_session_id,
                discussion_session_id=discussion_session_id,
                decision=result.decision,
                findings_count=len(result.findings),
                blocking_findings_count=result.summary.blocking_findings_count,
                gates_count=len(result.gates),
            )
            await _audit(
                task_id=source_task_id,
                decision_type=DECISION_AGENT_DISCUSSION_COMPLETED,
                summary=f"agent discussion completed ({len(contributions)} contributions)",
                result="completed",
                artifact_refs=refs,
            )
            await _notify(
                source_task_id,
                EVENT_DISCUSSION_SESSION_COMPLETED,
                f"discussion completed for project {project_id}",
            )
            completed_decision = (
                DECISION_DESIGN_REVIEW_BLOCKED
                if result.status == "blocked"
                else DECISION_DESIGN_REVIEW_COMPLETED
            )
            await _audit(
                task_id=source_task_id,
                decision_type=completed_decision,
                summary=f"design review {result.status} (decision={result.decision})",
                result=result.status,
                artifact_refs=refs,
            )
            await _audit(
                task_id=source_task_id,
                decision_type=DECISION_DESIGN_REVIEW_GO_NO_GO_RECORDED,
                summary=f"go/no-go decision: {result.decision}",
                result=result.decision,
                artifact_refs=refs,
            )
            completed_event = (
                EVENT_DESIGN_REVIEW_BLOCKED
                if result.status == "blocked"
                else EVENT_DESIGN_REVIEW_COMPLETED
            )
            await _notify(
                source_task_id,
                completed_event,
                f"design review {result.status} for project {project_id}",
            )
            await _notify(
                source_task_id,
                EVENT_DESIGN_REVIEW_GO_NO_GO_RECORDED,
                f"go/no-go: {result.decision} for project {project_id}",
            )

        blocking = result.summary.blocking_findings_count
        return DesignReviewOutput(
            project_id=project_id,
            discussion_session_id=discussion_session_id,
            review_session_id=review_session_id,
            review_type=review_type,
            status=result.status,
            decision=result.decision,
            participants_count=len(participants),
            contributions_count=len(contributions),
            gates_count=len(result.gates),
            findings_count=len(result.findings),
            blocking_findings_count=blocking,
            decisions_count=len(result.decisions),
            go_no_go_decision=result.decision,
            planning_only=planning_only,
            work_item_dispatch_enabled=work_item_dispatch_enabled,
            production_executed=False,
        )


__all__ = ["run_design_review", "load_review_context", "REVIEW_AGENT"]
