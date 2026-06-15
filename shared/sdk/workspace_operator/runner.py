"""Stage 47 -- controlled workspace execution orchestration.

Loads project + design-review context, checks the controlled-execution
preconditions, creates a controlled workspace UNDER an allowlisted root,
generates a deterministic FastAPI Todo project, runs pytest + static checks,
collects a diff summary, builds artifacts, maps work-item execution links,
and persists everything. Emits audit + notification events + metrics.

Used by BOTH the workspace-operator-agent (stream path) and
``POST /operations/projects/{id}/workspace/execute`` (synchronous path).

Controlled-only / review-only: no repo main write, no GitHub PR, no merge, no
deploy, no real LLM. ``production_executed`` is always False.
"""

from __future__ import annotations

import contextlib
import uuid

from shared.sdk.observability.metrics import (
    WORKSPACE_DIFF_SUMMARIES_TOTAL,
    WORKSPACE_EXECUTION_FAILURES_TOTAL,
    WORKSPACE_EXECUTION_RUNS_TOTAL,
    WORKSPACE_FILES_GENERATED_TOTAL,
    WORKSPACE_SAFETY_BLOCKS_TOTAL,
    WORKSPACE_STATIC_CHECKS_TOTAL,
    WORKSPACE_TESTS_FAILED_TOTAL,
    WORKSPACE_TESTS_PASSED_TOTAL,
    WORKSPACE_TESTS_RUNS_TOTAL,
)
from shared.sdk.observability.tracing import start_span
from shared.sdk.workspace_operator.artifact_builder import (
    build_diff_summary_artifact,
    build_generated_code_manifest,
    build_implementation_summary,
    build_test_result_artifact,
)
from shared.sdk.workspace_operator.audit_events import (
    DECISION_WORKSPACE_CREATED,
    DECISION_WORKSPACE_DIFF_SUMMARIZED,
    DECISION_WORKSPACE_EXECUTION_COMPLETED,
    DECISION_WORKSPACE_EXECUTION_FAILED,
    DECISION_WORKSPACE_EXECUTION_STARTED,
    DECISION_WORKSPACE_FILES_GENERATED,
    DECISION_WORKSPACE_STATIC_CHECKS_COMPLETED,
    DECISION_WORKSPACE_TESTS_COMPLETED,
    safe_workspace_artifact_refs,
)
from shared.sdk.workspace_operator.diff_summary import build_diff_summary
from shared.sdk.workspace_operator.events import (
    EVENT_WORKSPACE_EXECUTION_COMPLETED,
    EVENT_WORKSPACE_EXECUTION_FAILED,
    EVENT_WORKSPACE_EXECUTION_STARTED,
    EVENT_WORKSPACE_GENERATION_COMPLETED,
    EVENT_WORKSPACE_TESTS_COMPLETED,
)
from shared.sdk.workspace_operator.fastapi_todo_generator import build_fastapi_todo_files
from shared.sdk.workspace_operator.file_manifest import build_manifest
from shared.sdk.workspace_operator.models import (
    CodeWorkspace,
    WorkspaceExecutionRequest,
    WorkspaceExecutionResult,
    WorkspaceOperation,
)
from shared.sdk.workspace_operator.static_check_runner import (
    overall_static_status,
    run_static_checks,
)
from shared.sdk.workspace_operator.test_runner import run_pytest
from shared.sdk.workspace_operator.work_item_mapper import map_work_items
from shared.sdk.workspace_operator.workspace_manager import WorkspaceManager

OPERATOR_AGENT = "workspace-operator-agent"
_ALLOWED_DECISIONS = ("planning_only", "go_with_findings", "go")


async def _audit(*, task_id, decision_type, summary, result, artifact_refs) -> None:
    with contextlib.suppress(Exception):
        from shared.sdk.audit.publisher import publish_audit_event

        await publish_audit_event(
            task_id=task_id,
            agent=OPERATOR_AGENT,
            decision_type=decision_type,
            summary=summary,
            result=result,
            artifact_refs=artifact_refs,
        )


async def _notify(task_id, event_type, message) -> None:
    with contextlib.suppress(Exception):
        from shared.sdk.notifications.client import send_notification

        await send_notification(task_id or "unknown", event_type, message)


async def check_preconditions(
    *, project_id: str, project_store, review_store
) -> tuple[bool, str | None, dict]:
    """Return (ok, blocked_reason, context) for controlled workspace execution."""
    project = await project_store.get_project(project_id)
    if project is None:
        return False, "project_not_found", {}
    snapshot = await project_store.get_latest_graph_snapshot(project_id)
    validation_status = (snapshot or {}).get("validation_status", "valid")
    if validation_status != "valid":
        return False, "project_graph_invalid", {}
    review = await review_store.get_latest_review(project_id)
    if review is None:
        return False, "design_review_missing", {}
    if review.get("decision") not in _ALLOWED_DECISIONS:
        return False, f"design_review_decision_not_allowed:{review.get('decision')}", {}
    findings = await review_store.list_findings(review["id"])
    blocking = [
        f
        for f in findings
        if f.get("severity") in ("high", "critical") and f.get("status") == "open"
    ]
    if blocking:
        return False, "blocking_findings_present", {}
    if any(f.get("severity") == "critical" and f.get("status") == "open" for f in findings):
        return False, "critical_findings_present", {}
    gates = await review_store.list_gates(project_id)
    pre = next((g for g in gates if g.get("gate_type") == "pre_execution_gate"), None)
    if pre is not None and pre.get("status") in ("failed", "blocked"):
        return False, "pre_execution_gate_failed", {}
    ctx = {
        "project": project,
        "review": review,
        "template": str(project.get("project_type") or "fastapi_todo_service"),
        "graph_snapshot_id": (snapshot or {}).get("id"),
    }
    return True, None, ctx


async def run_workspace_execution(
    *,
    request: WorkspaceExecutionRequest,
    project_store,
    review_store,
    workspace_store,
    workspace_manager: WorkspaceManager | None = None,
    base_root: str | None = None,
    emit_events: bool = True,
    env: dict | None = None,
) -> WorkspaceExecutionResult:
    """Run one controlled workspace execution and persist the result."""
    project_id = request.project_id
    task_id = request.source_task_id
    with start_span(
        "workspace.execute",
        **{"service.name": OPERATOR_AGENT, "project_id": project_id},
    ):
        if emit_events:
            await _audit(
                task_id=task_id,
                decision_type=DECISION_WORKSPACE_EXECUTION_STARTED,
                summary=f"controlled workspace execution started for project {project_id}",
                result="started",
                artifact_refs=safe_workspace_artifact_refs(project_id=project_id),
            )
            await _notify(
                task_id,
                EVENT_WORKSPACE_EXECUTION_STARTED,
                f"workspace execution started for project {project_id}",
            )

        ok, reason, ctx = await check_preconditions(
            project_id=project_id, project_store=project_store, review_store=review_store
        )
        if not ok:
            WORKSPACE_SAFETY_BLOCKS_TOTAL.labels(reason=(reason or "unknown")[:60]).inc()
            WORKSPACE_EXECUTION_FAILURES_TOTAL.labels(status="failed").inc()
            if emit_events:
                await _audit(
                    task_id=task_id,
                    decision_type=DECISION_WORKSPACE_EXECUTION_FAILED,
                    summary=f"workspace execution blocked: {reason}",
                    result="failed",
                    artifact_refs=safe_workspace_artifact_refs(
                        project_id=project_id, status="failed"
                    ),
                )
                await _notify(
                    task_id,
                    EVENT_WORKSPACE_EXECUTION_FAILED,
                    f"workspace execution blocked for project {project_id}: {reason}",
                )
            return WorkspaceExecutionResult(
                project_id=project_id, status="failed", blocked_reason=reason
            )

        template = ctx["template"]
        manager = workspace_manager or WorkspaceManager(base_root, env=env)
        workspace_key = f"ws-{project_id[:8]}-{uuid.uuid4().hex[:8]}"

        # --- create workspace record ---------------------------------------
        workspace_root = manager.workspace_root_for(workspace_key)
        ws_model = CodeWorkspace(
            workspace_key=workspace_key,
            workspace_type=request.workspace_type,
            workspace_root=workspace_root,
            status="created",
            generation_mode="deterministic_template",
            project_id=project_id,
            design_review_session_id=request.design_review_session_id or ctx["review"].get("id"),
            source_task_id=task_id,
            created_by_agent=request.requested_by_agent,
        )
        workspace_id = await workspace_store.create_workspace(ws_model)
        if emit_events:
            await _audit(
                task_id=task_id,
                decision_type=DECISION_WORKSPACE_CREATED,
                summary=f"controlled workspace created ({workspace_key})",
                result="created",
                artifact_refs=safe_workspace_artifact_refs(
                    project_id=project_id, workspace_id=workspace_id, workspace_key=workspace_key
                ),
            )

        # --- prepare + generate --------------------------------------------
        with start_span("workspace.prepare"):
            manager.prepare(workspace_key)
            await workspace_store.record_operation(
                workspace_id,
                WorkspaceOperation(operation_type="prepare_workspace", status="completed"),
                project_id=project_id,
            )
        await workspace_store.update_workspace_status(workspace_id, "prepared")

        with start_span("workspace.generate_files"):
            brief = await project_store.get_brief(project_id) or {}
            work_items = await project_store.list_work_items(project_id)
            acceptance = await project_store.list_acceptance_criteria(project_id)
            files = build_fastapi_todo_files(
                brief=brief, work_items=work_items, acceptance_criteria=acceptance
            )
            manifest = build_manifest(files)
            manager.write_files(workspace_root, files)
            await workspace_store.record_workspace_files(
                workspace_id, manifest, project_id=project_id
            )
            await workspace_store.record_operation(
                workspace_id,
                WorkspaceOperation(
                    operation_type="generate_files",
                    status="completed",
                    output_summary=f"{len(manifest)} files generated",
                ),
                project_id=project_id,
            )
        await workspace_store.update_workspace_status(workspace_id, "generated")
        WORKSPACE_FILES_GENERATED_TOTAL.labels(workspace_type=request.workspace_type).inc(
            len(manifest)
        )
        if emit_events:
            await _audit(
                task_id=task_id,
                decision_type=DECISION_WORKSPACE_FILES_GENERATED,
                summary=f"{len(manifest)} files generated in {workspace_key}",
                result="generated",
                artifact_refs=safe_workspace_artifact_refs(
                    project_id=project_id,
                    workspace_id=workspace_id,
                    generated_files_count=len(manifest),
                ),
            )
            await _notify(
                task_id,
                EVENT_WORKSPACE_GENERATION_COMPLETED,
                f"workspace {workspace_key} generated {len(manifest)} files",
            )

        # --- tests ----------------------------------------------------------
        await workspace_store.update_workspace_status(workspace_id, "testing")
        with start_span("workspace.run_tests"):
            pytest_run = run_pytest(workspace_root, env=env)
            await workspace_store.record_test_run(workspace_id, pytest_run, project_id=project_id)
            await workspace_store.record_operation(
                workspace_id,
                WorkspaceOperation(
                    operation_type="run_tests",
                    status="completed",
                    command=pytest_run.command,
                    exit_code=pytest_run.exit_code,
                    output_summary=pytest_run.output_summary,
                ),
                project_id=project_id,
            )
        tests_status = pytest_run.status
        WORKSPACE_TESTS_RUNS_TOTAL.labels(test_type="pytest", status=tests_status).inc()
        if tests_status == "passed":
            WORKSPACE_TESTS_PASSED_TOTAL.labels(test_type="pytest").inc()
        elif tests_status == "failed":
            WORKSPACE_TESTS_FAILED_TOTAL.labels(test_type="pytest").inc()

        # --- static checks --------------------------------------------------
        with start_span("workspace.run_static_checks"):
            static_runs = run_static_checks(workspace_root, env=env)
            for r in static_runs:
                await workspace_store.record_test_run(workspace_id, r, project_id=project_id)
                WORKSPACE_STATIC_CHECKS_TOTAL.labels(test_type=r.test_type, status=r.status).inc()
            await workspace_store.record_operation(
                workspace_id,
                WorkspaceOperation(
                    operation_type="run_static_checks",
                    status="completed",
                    output_summary="; ".join(f"{r.test_type}={r.status}" for r in static_runs),
                ),
                project_id=project_id,
            )
        static_check_status = overall_static_status(static_runs)
        if emit_events:
            await _audit(
                task_id=task_id,
                decision_type=DECISION_WORKSPACE_TESTS_COMPLETED,
                summary=f"tests {tests_status}, static checks {static_check_status}",
                result=tests_status,
                artifact_refs=safe_workspace_artifact_refs(
                    project_id=project_id,
                    workspace_id=workspace_id,
                    tests_status=tests_status,
                    static_check_status=static_check_status,
                ),
            )
            await _audit(
                task_id=task_id,
                decision_type=DECISION_WORKSPACE_STATIC_CHECKS_COMPLETED,
                summary=f"static checks {static_check_status}",
                result=static_check_status,
                artifact_refs=safe_workspace_artifact_refs(
                    project_id=project_id,
                    workspace_id=workspace_id,
                    static_check_status=static_check_status,
                ),
            )
            await _notify(
                task_id,
                EVENT_WORKSPACE_TESTS_COMPLETED,
                f"workspace {workspace_key} tests {tests_status}",
            )

        # --- diff summary ---------------------------------------------------
        with start_span("workspace.collect_diff"):
            test_summary = f"pytest={tests_status}; static={static_check_status}"
            diff = build_diff_summary(manifest, test_summary=test_summary)
            diff_summary_id = await workspace_store.record_diff_summary(
                workspace_id, diff, project_id=project_id
            )
            await workspace_store.record_operation(
                workspace_id,
                WorkspaceOperation(
                    operation_type="collect_diff",
                    status="completed",
                    output_summary=f"{diff.changed_files_count} changed files",
                ),
                project_id=project_id,
            )
        WORKSPACE_DIFF_SUMMARIES_TOTAL.labels(workspace_type=request.workspace_type).inc()
        if emit_events:
            await _audit(
                task_id=task_id,
                decision_type=DECISION_WORKSPACE_DIFF_SUMMARIZED,
                summary=f"diff summary: {diff.changed_files_count} changed files",
                result="summarized",
                artifact_refs=safe_workspace_artifact_refs(
                    project_id=project_id,
                    workspace_id=workspace_id,
                    diff_summary_id=diff_summary_id,
                ),
            )

        # --- artifacts ------------------------------------------------------
        with start_span("workspace.persist_artifacts"):
            impl_artifact = build_implementation_summary(
                project_id=project_id,
                workspace_key=workspace_key,
                template=template,
                manifest=manifest,
                tests_status=tests_status,
                static_check_status=static_check_status,
            )
            impl_artifact_id = await workspace_store.record_artifact(
                workspace_id, impl_artifact, project_id=project_id
            )
            await workspace_store.record_artifact(
                workspace_id, build_generated_code_manifest(manifest), project_id=project_id
            )
            await workspace_store.record_artifact(
                workspace_id,
                build_test_result_artifact([pytest_run, *static_runs]),
                project_id=project_id,
            )
            await workspace_store.record_artifact(
                workspace_id, build_diff_summary_artifact(diff), project_id=project_id
            )
            artifacts_count = 4

        # --- work item execution links --------------------------------------
        links = map_work_items(
            work_items, tests_status=tests_status, evidence_artifact_id=impl_artifact_id
        )
        for link in links:
            await workspace_store.link_work_item_execution(project_id, workspace_id, link)

        # --- summarize / finalize ------------------------------------------
        if tests_status == "passed":
            final_status = "tests_passed"
        elif tests_status == "failed":
            final_status = "tests_failed"
        else:
            final_status = "summarized"
        await workspace_store.record_operation(
            workspace_id,
            WorkspaceOperation(operation_type="summarize", status="completed"),
            project_id=project_id,
        )
        await workspace_store.update_workspace_status(workspace_id, final_status, completed=True)
        WORKSPACE_EXECUTION_RUNS_TOTAL.labels(
            workspace_type=request.workspace_type,
            generation_mode="deterministic_template",
            status=final_status,
        ).inc()

        if emit_events:
            refs = safe_workspace_artifact_refs(
                project_id=project_id,
                workspace_id=workspace_id,
                workspace_key=workspace_key,
                status=final_status,
                generated_files_count=len(manifest),
                tests_status=tests_status,
                static_check_status=static_check_status,
                diff_summary_id=diff_summary_id,
                work_item_links_count=len(links),
            )
            await _audit(
                task_id=task_id,
                decision_type=DECISION_WORKSPACE_EXECUTION_COMPLETED,
                summary=(
                    f"workspace execution {final_status} for project {project_id} "
                    f"({len(manifest)} files, tests={tests_status})"
                ),
                result=final_status,
                artifact_refs=refs,
            )
            await _notify(
                task_id,
                EVENT_WORKSPACE_EXECUTION_COMPLETED,
                f"workspace execution {final_status} for project {project_id}",
            )

        return WorkspaceExecutionResult(
            project_id=project_id,
            workspace_id=workspace_id,
            workspace_key=workspace_key,
            workspace_root=workspace_root,
            status=final_status,
            generated_files_count=len(manifest),
            tests_status=tests_status,
            static_check_status=static_check_status,
            diff_summary_id=diff_summary_id,
            artifacts_count=artifacts_count,
            work_item_links_count=len(links),
            controlled_only=True,
            production_executed=False,
            github_write_performed=False,
            repo_write_performed=False,
            deployment_performed=False,
            real_llm_used=False,
        )


__all__ = ["run_workspace_execution", "check_preconditions", "OPERATOR_AGENT"]
