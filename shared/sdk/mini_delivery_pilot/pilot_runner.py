"""Stage 48 -- mini delivery pilot orchestration.

Chains the existing controlled stages into one end-to-end pilot:

  request -> project plan -> design review -> controlled workspace execution
  -> test/static evidence -> acceptance evaluation -> QA summary -> safety
  summary -> mini delivery pilot report.

Reuses ``plan_project`` (Stage 45), ``run_design_review`` (Stage 46), and
``run_workspace_execution`` (Stage 47) -- it never re-implements the
generator / reviewer. Controlled-only: no real PR, no GitHub write, no deploy,
no real LLM, no external delivery. ``production_executed`` is always False.
"""

from __future__ import annotations

import contextlib
import uuid

from shared.sdk.design_review import run_design_review
from shared.sdk.mini_delivery_pilot.acceptance_evaluator import (
    evaluate_acceptance,
    summarize_acceptance,
)
from shared.sdk.mini_delivery_pilot.artifact_linker import build_pilot_artifacts
from shared.sdk.mini_delivery_pilot.audit_events import (
    DECISION_MINI_DELIVERY_ACCEPTANCE_EVALUATED,
    DECISION_MINI_DELIVERY_PILOT_COMPLETED,
    DECISION_MINI_DELIVERY_PILOT_FAILED,
    DECISION_MINI_DELIVERY_PILOT_STARTED,
    DECISION_MINI_DELIVERY_QA_EVALUATED,
    DECISION_MINI_DELIVERY_REPORT_CREATED,
    DECISION_MINI_DELIVERY_SAFETY_EVALUATED,
    safe_pilot_artifact_refs,
)
from shared.sdk.mini_delivery_pilot.events import (
    EVENT_DELIVERY_PILOT_COMPLETED,
    EVENT_DELIVERY_PILOT_FAILED,
    EVENT_DELIVERY_PILOT_REPORT_READY,
    EVENT_DELIVERY_PILOT_STARTED,
)
from shared.sdk.mini_delivery_pilot.models import (
    MiniDeliveryPilot,
    MiniDeliveryPilotRequest,
    MiniDeliveryPilotResult,
)
from shared.sdk.mini_delivery_pilot.qa_evidence_builder import build_qa_report
from shared.sdk.mini_delivery_pilot.report_builder import build_mini_delivery_report
from shared.sdk.mini_delivery_pilot.safety_evidence_builder import build_safety_report
from shared.sdk.mini_delivery_pilot.step_tracker import make_step
from shared.sdk.observability.metrics import (
    MINI_DELIVERY_ACCEPTANCE_CRITERIA_TOTAL,
    MINI_DELIVERY_ACCEPTANCE_FAILED_TOTAL,
    MINI_DELIVERY_ACCEPTANCE_SATISFIED_TOTAL,
    MINI_DELIVERY_PILOT_FAILURES_TOTAL,
    MINI_DELIVERY_PILOT_RUNS_TOTAL,
    MINI_DELIVERY_PILOT_STEPS_TOTAL,
    MINI_DELIVERY_QA_REPORTS_TOTAL,
    MINI_DELIVERY_REPORTS_TOTAL,
    MINI_DELIVERY_SAFETY_REPORTS_TOTAL,
)
from shared.sdk.observability.tracing import start_span
from shared.sdk.project_planning import PlannerInput, plan_project
from shared.sdk.workspace_operator import (
    WorkspaceExecutionRequest,
    run_workspace_execution,
)

PILOT_AGENT = "mini-delivery-pilot-agent"


async def _audit(*, task_id, decision_type, summary, result, artifact_refs) -> None:
    with contextlib.suppress(Exception):
        from shared.sdk.audit.publisher import publish_audit_event

        await publish_audit_event(
            task_id=task_id,
            agent=PILOT_AGENT,
            decision_type=decision_type,
            summary=summary,
            result=result,
            artifact_refs=artifact_refs,
        )


async def _notify(task_id, event_type, message) -> None:
    with contextlib.suppress(Exception):
        from shared.sdk.notifications.client import send_notification

        await send_notification(task_id or "unknown", event_type, message)


async def run_mini_delivery_pilot(
    *,
    request: MiniDeliveryPilotRequest,
    project_store,
    discussion_store,
    review_store,
    workspace_store,
    pilot_store,
    workspace_base_root: str | None = None,
    emit_events: bool = True,
    env: dict | None = None,
) -> MiniDeliveryPilotResult:
    """Run one controlled mini delivery pilot end-to-end and persist evidence."""
    task_id = request.source_task_id
    pilot_type = request.pilot_type
    pilot_key = f"pilot-{uuid.uuid4().hex[:12]}"

    with start_span(
        "mini_delivery_pilot.run",
        **{"service.name": PILOT_AGENT, "pilot_type": pilot_type},
    ):
        pilot = MiniDeliveryPilot(
            pilot_key=pilot_key,
            pilot_type=pilot_type,
            status="planning",
            project_id=request.project_id,
            source_task_id=task_id,
            created_by_agent=request.requested_by_agent,
        )
        pilot_id = await pilot_store.create_pilot(pilot)
        if emit_events:
            await _audit(
                task_id=task_id,
                decision_type=DECISION_MINI_DELIVERY_PILOT_STARTED,
                summary=f"mini delivery pilot started ({pilot_key})",
                result="started",
                artifact_refs=safe_pilot_artifact_refs(pilot_id=pilot_id, pilot_key=pilot_key),
            )
            await _notify(task_id, EVENT_DELIVERY_PILOT_STARTED, f"pilot {pilot_key} started")

        result = MiniDeliveryPilotResult(
            pilot_id=pilot_id, pilot_key=pilot_key, pilot_type=pilot_type
        )

        async def _record_step(step_key, status, summary, refs=None):
            await pilot_store.create_step(
                pilot_id,
                make_step(step_key, status, summary=summary, evidence_refs=refs or []),
                project_id=result.project_id,
            )
            MINI_DELIVERY_PILOT_STEPS_TOTAL.labels(
                step_type=make_step(step_key, status).step_type, status=status
            ).inc()

        async def _fail(reason, status="failed"):
            result.pilot_status = status
            result.blocked_reason = reason
            await pilot_store.update_pilot_status(pilot_id, status)
            MINI_DELIVERY_PILOT_FAILURES_TOTAL.labels(pilot_type=pilot_type).inc()
            MINI_DELIVERY_PILOT_RUNS_TOTAL.labels(pilot_type=pilot_type, status=status).inc()
            if emit_events:
                await _audit(
                    task_id=task_id,
                    decision_type=DECISION_MINI_DELIVERY_PILOT_FAILED,
                    summary=f"mini delivery pilot {status}: {reason}",
                    result=status,
                    artifact_refs=safe_pilot_artifact_refs(
                        pilot_id=pilot_id, pilot_key=pilot_key, status=status
                    ),
                )
                await _notify(
                    task_id, EVENT_DELIVERY_PILOT_FAILED, f"pilot {pilot_key} {status}: {reason}"
                )
            return result

        # --- 1. project plan ----------------------------------------------
        with start_span("mini_delivery_pilot.project_plan"):
            project_id = request.project_id
            if not project_id:
                planner_out = await plan_project(
                    PlannerInput(request_text=request.request_text, task_id=task_id),
                    project_store,
                    emit_events=emit_events,
                )
                project_id = planner_out.project_id
            project = await project_store.get_project(project_id)
            if project is None:
                return await _fail("project_not_found")
            result.project_id = project_id
            snapshot = await project_store.get_latest_graph_snapshot(project_id)
            if (snapshot or {}).get("validation_status", "valid") != "valid":
                await _record_step("project_plan", "failed", "graph invalid")
                return await _fail("project_graph_invalid")
        await pilot_store.update_pilot_status(
            pilot_id,
            "planned",
            project_id=project_id,
            graph_snapshot_id=(snapshot or {}).get("id"),
        )
        await _record_step(
            "project_plan",
            "passed",
            "project planned + graph valid",
            refs=[{"project_id": project_id}],
        )

        # --- 2. design review ---------------------------------------------
        await pilot_store.update_pilot_status(pilot_id, "design_reviewing")
        with start_span("mini_delivery_pilot.design_review"):
            review = await review_store.get_latest_review(project_id)
            if review is None:
                dr_out = await run_design_review(
                    project_id=project_id,
                    project_store=project_store,
                    discussion_store=discussion_store,
                    review_store=review_store,
                    source_task_id=task_id,
                    emit_events=emit_events,
                )
                review_session_id = dr_out.review_session_id
                decision = dr_out.decision
                blocking = dr_out.blocking_findings_count
            else:
                review_session_id = review["id"]
                decision = review["decision"]
                findings = await review_store.list_findings(review_session_id)
                blocking = len(
                    [
                        f
                        for f in findings
                        if f.get("severity") in ("high", "critical") and f.get("status") == "open"
                    ]
                )
            result.design_review_session_id = review_session_id
            if decision not in ("planning_only", "go_with_findings", "go") or blocking > 0:
                await _record_step("design_review", "blocked", f"decision={decision}")
                await pilot_store.update_pilot_status(
                    pilot_id, "design_reviewed", design_review_session_id=review_session_id
                )
                return await _fail(f"design_review_blocked:{decision}", status="blocked")
        await pilot_store.update_pilot_status(
            pilot_id, "design_reviewed", design_review_session_id=review_session_id
        )
        dr_status = "passed_with_findings" if decision == "go_with_findings" else "passed"
        await _record_step(
            "design_review",
            dr_status,
            f"decision={decision}, blocking=0",
            refs=[{"design_review_session_id": review_session_id, "decision": decision}],
        )

        # --- 3. controlled workspace execution ----------------------------
        await pilot_store.update_pilot_status(pilot_id, "workspace_executing")
        with start_span("mini_delivery_pilot.workspace_execution"):
            ws_result = await run_workspace_execution(
                request=WorkspaceExecutionRequest(
                    project_id=project_id,
                    design_review_session_id=review_session_id,
                    source_task_id=task_id,
                ),
                project_store=project_store,
                review_store=review_store,
                workspace_store=workspace_store,
                base_root=workspace_base_root,
                emit_events=emit_events,
                env=env,
            )
            if ws_result.status == "failed":
                await _record_step("workspace_execution", "failed", ws_result.blocked_reason or "")
                return await _fail(f"workspace_failed:{ws_result.blocked_reason}")
            result.workspace_id = ws_result.workspace_id
        await pilot_store.update_pilot_status(
            pilot_id, "workspace_completed", workspace_id=ws_result.workspace_id
        )
        await _record_step(
            "workspace_execution",
            "passed",
            f"{ws_result.generated_files_count} files generated",
            refs=[{"workspace_id": ws_result.workspace_id}],
        )
        result.tests_status = ws_result.tests_status
        test_step_status = (
            "passed"
            if ws_result.tests_status == "passed"
            else ("failed" if ws_result.tests_status == "failed" else "passed_with_findings")
        )
        await _record_step(
            "test_execution",
            test_step_status,
            f"pytest={ws_result.tests_status}, static={ws_result.static_check_status}",
            refs=[{"tests_status": ws_result.tests_status}],
        )

        # --- gather workspace evidence ------------------------------------
        test_runs = await workspace_store.list_test_runs(ws_result.workspace_id)
        ws_files = await workspace_store.list_workspace_files(ws_result.workspace_id)
        file_paths = [f["relative_path"] for f in ws_files]
        pytest_run: dict = next(
            (t for t in test_runs if t.get("test_type") == "pytest"), {}
        )

        # --- 4. QA evidence -----------------------------------------------
        await pilot_store.update_pilot_status(pilot_id, "qa_evaluating")
        with start_span("mini_delivery_pilot.qa_evaluation"):
            qa = build_qa_report(test_runs)
            qa_report_id = await pilot_store.create_qa_report(
                pilot_id, project_id, ws_result.workspace_id, qa
            )
            result.qa_report_id = qa_report_id
            result.qa_status = qa.status
        MINI_DELIVERY_QA_REPORTS_TOTAL.labels(status=qa.status).inc()
        await _record_step(
            "qa_summary",
            "passed" if qa.status in ("passed", "passed_with_findings") else "failed",
            qa.report_summary,
        )
        if emit_events:
            await _audit(
                task_id=task_id,
                decision_type=DECISION_MINI_DELIVERY_QA_EVALUATED,
                summary=f"QA evidence: {qa.status}",
                result=qa.status,
                artifact_refs=safe_pilot_artifact_refs(
                    pilot_id=pilot_id, project_id=project_id, qa_status=qa.status
                ),
            )

        # --- 5. safety evidence -------------------------------------------
        await pilot_store.update_pilot_status(pilot_id, "safety_evaluating")
        with start_span("mini_delivery_pilot.safety_evaluation"):
            safety = build_safety_report(workspace_result=ws_result.model_dump())
            safety_report_id = await pilot_store.create_safety_report(
                pilot_id, project_id, ws_result.workspace_id, safety
            )
            result.safety_report_id = safety_report_id
            result.safety_status = safety.status
        MINI_DELIVERY_SAFETY_REPORTS_TOTAL.labels(status=safety.status).inc()
        await _record_step(
            "safety_summary",
            "passed" if safety.status == "safe" else "blocked",
            safety.report_summary,
        )
        if emit_events:
            await _audit(
                task_id=task_id,
                decision_type=DECISION_MINI_DELIVERY_SAFETY_EVALUATED,
                summary=f"safety evidence: {safety.status}",
                result=safety.status,
                artifact_refs=safe_pilot_artifact_refs(
                    pilot_id=pilot_id, project_id=project_id, safety_status=safety.status
                ),
            )
        if safety.status not in ("safe", "safe_with_findings"):
            return await _fail("safety_blocked", status="blocked")

        # --- 6. acceptance evaluation -------------------------------------
        await pilot_store.update_pilot_status(pilot_id, "acceptance_evaluating")
        with start_span("mini_delivery_pilot.acceptance_evaluation"):
            criteria = await project_store.list_acceptance_criteria(project_id)
            evaluations = evaluate_acceptance(
                criteria=criteria,
                pytest_status=pytest_run.get("status"),
                pytest_passed=pytest_run.get("tests_passed"),
                pytest_failed=pytest_run.get("tests_failed"),
                generated_files=file_paths,
                safety_ok=(safety.status in ("safe", "safe_with_findings")),
            )
            await pilot_store.create_acceptance_evaluations(pilot_id, project_id, evaluations)
            acc = summarize_acceptance(evaluations)
            result.acceptance_total = acc["total"]
            result.acceptance_satisfied = acc["satisfied"]
            result.acceptance_failed = acc["failed"]
            result.acceptance_pending = acc["pending"]
        MINI_DELIVERY_ACCEPTANCE_CRITERIA_TOTAL.labels(pilot_type=pilot_type).inc(acc["total"])
        MINI_DELIVERY_ACCEPTANCE_SATISFIED_TOTAL.labels(pilot_type=pilot_type).inc(acc["satisfied"])
        if acc["failed"]:
            MINI_DELIVERY_ACCEPTANCE_FAILED_TOTAL.labels(pilot_type=pilot_type).inc(acc["failed"])
        acc_step_status = "passed" if acc["failed"] == 0 else "failed"
        await _record_step(
            "acceptance_evaluation",
            acc_step_status,
            f"{acc['satisfied']}/{acc['total']} satisfied, {acc['failed']} failed, "
            f"{acc['pending']} pending",
            refs=[acc],
        )
        if emit_events:
            await _audit(
                task_id=task_id,
                decision_type=DECISION_MINI_DELIVERY_ACCEPTANCE_EVALUATED,
                summary=f"acceptance {acc['satisfied']}/{acc['total']} satisfied",
                result="evaluated",
                artifact_refs=safe_pilot_artifact_refs(
                    pilot_id=pilot_id,
                    project_id=project_id,
                    acceptance_total=acc["total"],
                    acceptance_satisfied=acc["satisfied"],
                ),
            )

        # --- 7. mini delivery report --------------------------------------
        await pilot_store.update_pilot_status(pilot_id, "report_ready")
        with start_span("mini_delivery_pilot.report_build"):
            ws_report = await workspace_store.get_workspace_report(ws_result.workspace_id)
            project_summary = {
                "project_id": project_id,
                "title": project.get("title"),
                "project_type": project.get("project_type"),
                "work_items_count": ws_report.get("files_count"),
            }
            design_review_summary = {
                "design_review_session_id": review_session_id,
                "decision": decision,
                "blocking_findings_count": 0,
            }
            workspace_summary = {
                "workspace_id": ws_result.workspace_id,
                "generated_files_count": ws_result.generated_files_count,
                "tests_status": ws_result.tests_status,
                "static_check_status": ws_result.static_check_status,
            }
            report = build_mini_delivery_report(
                pilot_type=pilot_type,
                project_summary=project_summary,
                design_review_summary=design_review_summary,
                workspace_summary=workspace_summary,
                qa=qa,
                acceptance_summary=acc,
                safety=safety,
            )
            report_id = await pilot_store.create_delivery_report(
                pilot_id, project_id, ws_result.workspace_id, report
            )
            result.mini_delivery_report_id = report_id
        MINI_DELIVERY_REPORTS_TOTAL.labels(status=report.status).inc()
        await _record_step("pilot_report", "passed", f"report status={report.status}")
        if emit_events:
            await _audit(
                task_id=task_id,
                decision_type=DECISION_MINI_DELIVERY_REPORT_CREATED,
                summary=f"mini delivery report {report.status}",
                result=report.status,
                artifact_refs=safe_pilot_artifact_refs(pilot_id=pilot_id, project_id=project_id),
            )
            await _notify(
                task_id, EVENT_DELIVERY_PILOT_REPORT_READY, f"pilot {pilot_key} report ready"
            )

        # --- 8. pilot artifacts -------------------------------------------
        artifacts = build_pilot_artifacts(
            project_id=project_id,
            design_review_session_id=review_session_id,
            workspace_id=ws_result.workspace_id,
            qa_report_id=qa_report_id,
            safety_report_id=safety_report_id,
            mini_delivery_report_id=report_id,
            acceptance_total=acc["total"],
        )
        for art in artifacts:
            await pilot_store.create_pilot_artifact(pilot_id, project_id, art)

        # --- finalize -----------------------------------------------------
        final_status = (
            "completed"
            if (
                qa.status in ("passed", "passed_with_findings")
                and safety.status in ("safe", "safe_with_findings")
                and acc["failed"] == 0
            )
            else "report_ready"
        )
        result.pilot_status = final_status
        await pilot_store.update_pilot_status(pilot_id, final_status, completed=True)
        MINI_DELIVERY_PILOT_RUNS_TOTAL.labels(pilot_type=pilot_type, status=final_status).inc()
        if emit_events:
            await _audit(
                task_id=task_id,
                decision_type=DECISION_MINI_DELIVERY_PILOT_COMPLETED,
                summary=(
                    f"mini delivery pilot {final_status} ({pilot_key}): "
                    f"QA={qa.status}, safety={safety.status}, "
                    f"acceptance {acc['satisfied']}/{acc['total']}"
                ),
                result=final_status,
                artifact_refs=safe_pilot_artifact_refs(
                    pilot_id=pilot_id,
                    pilot_key=pilot_key,
                    project_id=project_id,
                    workspace_id=ws_result.workspace_id,
                    design_review_session_id=review_session_id,
                    status=final_status,
                    qa_status=qa.status,
                    safety_status=safety.status,
                    acceptance_total=acc["total"],
                    acceptance_satisfied=acc["satisfied"],
                ),
            )
            await _notify(
                task_id, EVENT_DELIVERY_PILOT_COMPLETED, f"pilot {pilot_key} {final_status}"
            )
        return result


__all__ = ["run_mini_delivery_pilot", "PILOT_AGENT"]
