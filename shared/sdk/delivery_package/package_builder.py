"""Stage 49 -- delivery package build orchestration.

Turns one completed mini delivery pilot's already-persisted evidence into a
formal, human-reviewable Delivery Package + Acceptance Gate:

  pilot evidence -> collect artifacts -> build checklist -> build sections ->
  evaluate acceptance gate -> operator review placeholder (pending) -> handoff
  summaries -> readiness snapshot -> delivery package report -> export metadata.

It NEVER re-runs code generation or tests, NEVER calls an LLM, writes GitHub,
opens a PR, merges, deploys, or delivers externally, and NEVER auto-marks human
acceptance. ``production_executed`` is always False.
"""

from __future__ import annotations

import contextlib
import uuid

from shared.sdk.delivery_package.acceptance_gate import evaluate_acceptance_gate
from shared.sdk.delivery_package.artifact_collector import build_package_artifacts
from shared.sdk.delivery_package.audit_events import (
    DECISION_DELIVERY_PACKAGE_ACCEPTANCE_GATE_EVALUATED,
    DECISION_DELIVERY_PACKAGE_BUILD_FAILED,
    DECISION_DELIVERY_PACKAGE_BUILD_STARTED,
    DECISION_DELIVERY_PACKAGE_READY_FOR_REVIEW,
    DECISION_DELIVERY_PACKAGE_SECTIONS_CREATED,
    DECISION_HANDOFF_SUMMARY_CREATED,
    DECISION_OPERATOR_ACCEPTANCE_REVIEW_CREATED,
    safe_package_artifact_refs,
)
from shared.sdk.delivery_package.checklist_builder import build_acceptance_checklist
from shared.sdk.delivery_package.events import (
    EVENT_DELIVERY_PACKAGE_BUILD_FAILED,
    EVENT_DELIVERY_PACKAGE_BUILD_STARTED,
    EVENT_DELIVERY_PACKAGE_READY_FOR_REVIEW,
)
from shared.sdk.delivery_package.export_metadata import build_export_metadata
from shared.sdk.delivery_package.handoff_builder import build_handoff_summaries
from shared.sdk.delivery_package.models import (
    DeliveryPackage,
    DeliveryPackageRequest,
    DeliveryPackageResult,
    OperatorAcceptanceReview,
)
from shared.sdk.delivery_package.readiness_snapshot import build_readiness_snapshot
from shared.sdk.delivery_package.report_builder import build_delivery_package_report
from shared.sdk.delivery_package.section_builder import build_sections
from shared.sdk.observability.metrics import (
    ACCEPTANCE_GATE_CHECKS_TOTAL,
    ACCEPTANCE_GATE_FAILURES_TOTAL,
    ACCEPTANCE_GATE_RUNS_TOTAL,
    DELIVERY_PACKAGE_BUILD_FAILURES_TOTAL,
    DELIVERY_PACKAGE_BUILDS_TOTAL,
    DELIVERY_PACKAGE_READY_FOR_REVIEW_TOTAL,
    DELIVERY_PACKAGE_SECTIONS_TOTAL,
    DELIVERY_READINESS_SNAPSHOTS_TOTAL,
    HANDOFF_SUMMARIES_CREATED_TOTAL,
    OPERATOR_ACCEPTANCE_REVIEWS_TOTAL,
)
from shared.sdk.observability.tracing import start_span

PACKAGE_AGENT = "delivery-package-agent"


async def _audit(*, task_id, decision_type, summary, result, artifact_refs) -> None:
    with contextlib.suppress(Exception):
        from shared.sdk.audit.publisher import publish_audit_event

        await publish_audit_event(
            task_id=task_id,
            agent=PACKAGE_AGENT,
            decision_type=decision_type,
            summary=summary,
            result=result,
            artifact_refs=artifact_refs,
        )


async def _notify(task_id, event_type, message) -> None:
    with contextlib.suppress(Exception):
        from shared.sdk.notifications.client import send_notification

        await send_notification(task_id or "unknown", event_type, message)


async def gather_evidence(
    *, pilot, pilot_store, project_store, review_store, workspace_store
) -> dict:
    """Collect already-persisted mini delivery pilot evidence into one dict."""
    pilot_id = pilot["id"]
    project_id = pilot.get("project_id")
    workspace_id = pilot.get("workspace_id")
    review_session_id = pilot.get("design_review_session_id")

    project = await project_store.get_project(project_id) if project_id else None
    work_items = await project_store.list_work_items(project_id) if project_id else []
    review = await review_store.get_review(review_session_id) if review_session_id else None
    findings = await review_store.list_findings(review_session_id) if review_session_id else []
    blocking_findings = [
        f
        for f in findings
        if f.get("severity") in ("high", "critical") and f.get("status") == "open"
    ]
    workspace_report = (
        await workspace_store.get_workspace_report(workspace_id) if workspace_id else {}
    )
    qa = await pilot_store.get_qa_report(pilot_id)
    safety = await pilot_store.get_safety_report(pilot_id)
    acceptance_summary = await pilot_store.get_acceptance_summary(pilot_id)
    acceptance_evaluations = await pilot_store.list_acceptance_evaluations(pilot_id)
    mini_delivery_report = await pilot_store.get_pilot_report(pilot_id)

    return {
        "pilot": pilot,
        "project_id": project_id,
        "workspace_id": workspace_id,
        "design_review_session_id": review_session_id,
        "project": project,
        "work_items": work_items,
        "review": review,
        "blocking_findings_count": len(blocking_findings),
        "workspace_report": workspace_report,
        "qa": qa,
        "safety": safety,
        "acceptance_summary": acceptance_summary,
        "acceptance_evaluations": acceptance_evaluations,
        "mini_delivery_report": mini_delivery_report,
    }


async def run_delivery_package_build(
    *,
    request: DeliveryPackageRequest,
    pilot_store,
    project_store,
    review_store,
    workspace_store,
    package_store,
    emit_events: bool = True,
    env: dict | None = None,
) -> DeliveryPackageResult:
    """Build one controlled delivery package + acceptance gate from a pilot."""
    task_id = request.source_task_id
    package_type = request.package_type
    package_key = f"pkg-{uuid.uuid4().hex[:12]}"

    with start_span(
        "delivery_package.build",
        **{"service.name": PACKAGE_AGENT, "package_type": package_type},
    ):
        result = DeliveryPackageResult(package_key=package_key, package_type=package_type)

        # --- preconditions: pilot must be a completed, safe pilot -------------
        try:
            pilot = await pilot_store.get_pilot(request.pilot_id)
        except Exception:
            pilot = None
        if pilot is None:
            return await _fail_no_package(result, "pilot_not_found", task_id, emit_events)
        result.pilot_id = pilot["id"]
        result.project_id = pilot.get("project_id")
        result.workspace_id = pilot.get("workspace_id")
        result.design_review_session_id = pilot.get("design_review_session_id")

        evidence = await gather_evidence(
            pilot=pilot,
            pilot_store=pilot_store,
            project_store=project_store,
            review_store=review_store,
            workspace_store=workspace_store,
        )

        precondition = _check_preconditions(pilot, evidence)
        if precondition is not None:
            return await _fail_with_package(
                result,
                precondition,
                task_id,
                emit_events,
                package_store,
                package_type,
                package_key,
                pilot,
                status="blocked",
            )

        # --- create the package (building) -----------------------------------
        package = DeliveryPackage(
            package_key=package_key,
            package_type=package_type,
            status="building",
            project_id=evidence.get("project_id"),
            pilot_id=pilot["id"],
            workspace_id=evidence.get("workspace_id"),
            design_review_session_id=evidence.get("design_review_session_id"),
            created_by_agent=request.requested_by_agent,
        )
        package_id = await package_store.create_delivery_package(package)
        result.package_id = package_id
        if emit_events:
            await _audit(
                task_id=task_id,
                decision_type=DECISION_DELIVERY_PACKAGE_BUILD_STARTED,
                summary=f"delivery package build started ({package_key})",
                result="started",
                artifact_refs=safe_package_artifact_refs(
                    package_id=package_id, package_key=package_key, pilot_id=pilot["id"]
                ),
            )
            await _notify(
                task_id, EVENT_DELIVERY_PACKAGE_BUILD_STARTED, f"package {package_key} started"
            )

        # --- artifacts -------------------------------------------------------
        with start_span("delivery_package.collect_artifacts"):
            artifacts = build_package_artifacts(evidence)
            await package_store.create_artifacts(package_id, evidence.get("project_id"), artifacts)

        # --- checklist + sections -------------------------------------------
        with start_span("delivery_package.build_sections"):
            checklist = build_acceptance_checklist(evidence)
            sections = build_sections(evidence, checklist)
            await package_store.create_sections(package_id, evidence.get("project_id"), sections)
        for s in sections:
            DELIVERY_PACKAGE_SECTIONS_TOTAL.labels(status=s.status).inc()
        result.sections_ready_count = sum(1 for s in sections if s.status == "ready")
        result.sections_missing_count = sum(1 for s in sections if s.status == "missing")
        if emit_events:
            await _audit(
                task_id=task_id,
                decision_type=DECISION_DELIVERY_PACKAGE_SECTIONS_CREATED,
                summary=f"{len(sections)} sections created",
                result="created",
                artifact_refs=safe_package_artifact_refs(
                    package_id=package_id,
                    sections_ready_count=result.sections_ready_count,
                    sections_missing_count=result.sections_missing_count,
                ),
            )

        # --- acceptance gate -------------------------------------------------
        with start_span("delivery_package.evaluate_acceptance_gate"):
            gate = evaluate_acceptance_gate(evidence, sections)
            gate_run_id = await package_store.create_acceptance_gate_run(
                package_id, evidence.get("project_id"), pilot["id"], gate
            )
            await package_store.create_gate_check_results(
                gate_run_id, package_id, evidence.get("project_id"), gate.checks
            )
        result.acceptance_gate_run_id = gate_run_id
        result.acceptance_gate_status = gate.status
        result.acceptance_gate_decision = gate.decision
        result.blocking_findings_count = gate.blocking_findings_count
        ACCEPTANCE_GATE_RUNS_TOTAL.labels(status=gate.status, decision=gate.decision).inc()
        for c in gate.checks:
            ACCEPTANCE_GATE_CHECKS_TOTAL.labels(check_type=c.check_type, status=c.status).inc()
        if gate.status in ("blocked", "failed"):
            ACCEPTANCE_GATE_FAILURES_TOTAL.labels(decision=gate.decision).inc()
        if emit_events:
            await _audit(
                task_id=task_id,
                decision_type=DECISION_DELIVERY_PACKAGE_ACCEPTANCE_GATE_EVALUATED,
                summary=f"acceptance gate {gate.status} ({gate.decision})",
                result=gate.status,
                artifact_refs=safe_package_artifact_refs(
                    package_id=package_id,
                    gate_run_id=gate_run_id,
                    status=gate.status,
                    decision=gate.decision,
                    blocking_findings_count=gate.blocking_findings_count,
                ),
            )

        # --- operator review placeholder (pending -- never auto-accepted) ----
        operator_review_id = await package_store.create_operator_review_placeholder(
            package_id,
            evidence.get("project_id"),
            gate_run_id,
            OperatorAcceptanceReview(
                review_status="pending",
                review_summary="awaiting human operator acceptance (controlled-only)",
            ),
        )
        result.operator_review_id = operator_review_id
        OPERATOR_ACCEPTANCE_REVIEWS_TOTAL.labels(review_status="pending").inc()
        if emit_events:
            await _audit(
                task_id=task_id,
                decision_type=DECISION_OPERATOR_ACCEPTANCE_REVIEW_CREATED,
                summary="operator acceptance review placeholder created (pending)",
                result="pending",
                artifact_refs=safe_package_artifact_refs(
                    package_id=package_id, human_acceptance_status="pending"
                ),
            )

        # --- handoff summaries ----------------------------------------------
        with start_span("delivery_package.build_handoff"):
            handoffs = build_handoff_summaries(evidence, gate)
            handoff_ids = await package_store.create_handoff_summaries(
                package_id, evidence.get("project_id"), handoffs
            )
        result.handoff_summary_ids = handoff_ids
        for h in handoffs:
            HANDOFF_SUMMARIES_CREATED_TOTAL.labels(summary_type=h.summary_type).inc()
        if emit_events:
            await _audit(
                task_id=task_id,
                decision_type=DECISION_HANDOFF_SUMMARY_CREATED,
                summary=f"{len(handoffs)} handoff summaries created",
                result="created",
                artifact_refs=safe_package_artifact_refs(package_id=package_id),
            )

        # --- readiness snapshot ---------------------------------------------
        with start_span("delivery_package.create_readiness_snapshot"):
            snapshot = build_readiness_snapshot(evidence, sections, gate)
            readiness_id = await package_store.create_readiness_snapshot(
                package_id, evidence.get("project_id"), pilot["id"], snapshot
            )
        result.readiness_snapshot_id = readiness_id
        result.readiness_status = snapshot.readiness_status
        DELIVERY_READINESS_SNAPSHOTS_TOTAL.labels(readiness_status=snapshot.readiness_status).inc()

        # --- finalize package status ----------------------------------------
        if gate.status in ("blocked", "failed"):
            package_status = "blocked"
        else:
            package_status = "ready_for_review"
        result.package_status = package_status

        # --- delivery package report + export metadata ----------------------
        with start_span("delivery_package.persist_report"):
            report = build_delivery_package_report(
                package_id=package_id,
                project_id=evidence.get("project_id"),
                pilot_id=pilot["id"],
                package_status=package_status,
                gate=gate,
                human_acceptance_status="pending",
                readiness_status=snapshot.readiness_status,
                sections=sections,
                artifact_refs=[a.model_dump() for a in artifacts],
            )
            await package_store.set_package_report(package_id, report)
            stored_pkg = await package_store.get_delivery_package(package_id) or {}
            export_meta = build_export_metadata(
                package={**stored_pkg, "status": package_status},
                gate=gate.model_dump(),
                readiness=snapshot.model_dump(),
                sections=sections,
                handoff_summaries=handoffs,
            )
            await package_store.set_export_metadata(package_id, export_meta)

        await package_store.update_package_status(
            package_id, package_status, completed=(package_status == "ready_for_review")
        )
        DELIVERY_PACKAGE_BUILDS_TOTAL.labels(package_type=package_type, status=package_status).inc()
        if package_status == "ready_for_review":
            DELIVERY_PACKAGE_READY_FOR_REVIEW_TOTAL.labels(package_type=package_type).inc()
            if emit_events:
                await _audit(
                    task_id=task_id,
                    decision_type=DECISION_DELIVERY_PACKAGE_READY_FOR_REVIEW,
                    summary=(
                        f"delivery package ready_for_review ({package_key}): gate={gate.decision}, "
                        f"human_acceptance=pending"
                    ),
                    result="ready_for_review",
                    artifact_refs=safe_package_artifact_refs(
                        package_id=package_id,
                        package_key=package_key,
                        project_id=evidence.get("project_id"),
                        pilot_id=pilot["id"],
                        status=package_status,
                        decision=gate.decision,
                        human_acceptance_status="pending",
                        readiness_status=snapshot.readiness_status,
                        sections_ready_count=result.sections_ready_count,
                        sections_missing_count=result.sections_missing_count,
                        blocking_findings_count=gate.blocking_findings_count,
                    ),
                )
                await _notify(
                    task_id,
                    EVENT_DELIVERY_PACKAGE_READY_FOR_REVIEW,
                    f"package {package_key} ready_for_review",
                )
        else:
            DELIVERY_PACKAGE_BUILD_FAILURES_TOTAL.labels(package_type=package_type).inc()
            if emit_events:
                await _audit(
                    task_id=task_id,
                    decision_type=DECISION_DELIVERY_PACKAGE_BUILD_FAILED,
                    summary=f"delivery package {package_status}: acceptance gate {gate.status}",
                    result=package_status,
                    artifact_refs=safe_package_artifact_refs(
                        package_id=package_id, status=package_status, decision=gate.decision
                    ),
                )
                await _notify(
                    task_id,
                    EVENT_DELIVERY_PACKAGE_BUILD_FAILED,
                    f"package {package_key} {package_status}",
                )
        return result


def _check_preconditions(pilot: dict, evidence: dict) -> str | None:
    """Return a blocked-reason string if a precondition fails, else None."""
    if pilot.get("status") not in ("completed", "report_ready"):
        return f"pilot_not_complete:{pilot.get('status')}"
    if not evidence.get("project"):
        return "project_not_found"
    if not evidence.get("workspace_id"):
        return "workspace_missing"
    if not evidence.get("design_review_session_id"):
        return "design_review_missing"
    if not evidence.get("mini_delivery_report"):
        return "mini_delivery_report_missing"
    safety = evidence.get("safety") or {}
    if safety.get("status") not in ("safe", "safe_with_findings"):
        return f"safety_not_safe:{safety.get('status')}"
    qa = evidence.get("qa") or {}
    if qa.get("status") not in ("passed", "passed_with_findings"):
        return f"qa_not_passed:{qa.get('status')}"
    acc = evidence.get("acceptance_summary") or {}
    if int(acc.get("failed", 0) or 0) > 0:
        return f"acceptance_failed:{acc.get('failed')}"
    return None


async def _fail_no_package(
    result: DeliveryPackageResult, reason: str, task_id, emit_events: bool
) -> DeliveryPackageResult:
    result.package_status = "failed"
    result.blocked_reason = reason
    DELIVERY_PACKAGE_BUILD_FAILURES_TOTAL.labels(package_type=result.package_type).inc()
    DELIVERY_PACKAGE_BUILDS_TOTAL.labels(package_type=result.package_type, status="failed").inc()
    if emit_events:
        await _audit(
            task_id=task_id,
            decision_type=DECISION_DELIVERY_PACKAGE_BUILD_FAILED,
            summary=f"delivery package build failed: {reason}",
            result="failed",
            artifact_refs=safe_package_artifact_refs(status="failed"),
        )
        await _notify(task_id, EVENT_DELIVERY_PACKAGE_BUILD_FAILED, f"package failed: {reason}")
    return result


async def _fail_with_package(
    result, reason, task_id, emit_events, package_store, package_type, package_key, pilot, *, status
) -> DeliveryPackageResult:
    """Persist a blocked/failed package shell so the failure is inspectable."""
    package = DeliveryPackage(
        package_key=package_key,
        package_type=package_type,
        status=status,
        project_id=pilot.get("project_id"),
        pilot_id=pilot.get("id"),
        workspace_id=pilot.get("workspace_id"),
        design_review_session_id=pilot.get("design_review_session_id"),
        metadata={"blocked_reason": reason},
    )
    with contextlib.suppress(Exception):
        result.package_id = await package_store.create_delivery_package(package)
    result.package_status = status
    result.blocked_reason = reason
    result.acceptance_gate_status = "blocked"
    result.acceptance_gate_decision = "blocked"
    DELIVERY_PACKAGE_BUILD_FAILURES_TOTAL.labels(package_type=package_type).inc()
    DELIVERY_PACKAGE_BUILDS_TOTAL.labels(package_type=package_type, status=status).inc()
    if emit_events:
        await _audit(
            task_id=task_id,
            decision_type=DECISION_DELIVERY_PACKAGE_BUILD_FAILED,
            summary=f"delivery package {status}: {reason}",
            result=status,
            artifact_refs=safe_package_artifact_refs(package_id=result.package_id, status=status),
        )
        await _notify(
            task_id,
            EVENT_DELIVERY_PACKAGE_BUILD_FAILED,
            f"package {package_key} {status}: {reason}",
        )
    return result


__all__ = ["run_delivery_package_build", "gather_evidence", "PACKAGE_AGENT"]
