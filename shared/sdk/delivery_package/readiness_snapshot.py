"""Stage 49 -- build a delivery readiness snapshot for Admin Console v0.

readiness_status:
* ``ready_for_operator_review`` -- all technical readiness flags true and the
  acceptance gate is passed / passed_with_findings (human acceptance pending).
* ``blocked`` -- a blocking gate failure.
* ``failed`` -- the package build itself failed.
"""

from __future__ import annotations

from shared.sdk.delivery_package.models import AcceptanceGateRun, DeliveryReadinessSnapshot


def build_readiness_snapshot(
    evidence: dict,
    sections: list,
    gate: AcceptanceGateRun,
) -> DeliveryReadinessSnapshot:
    qa = evidence.get("qa") or {}
    safety = evidence.get("safety") or {}
    acc = evidence.get("acceptance_summary") or {}
    workspace_report = evidence.get("workspace_report") or {}
    files = workspace_report.get("files") or []
    missing_sections = [s for s in sections if getattr(s, "status", None) == "missing"]

    project_ready = bool(evidence.get("project_id"))
    design_ready = bool(evidence.get("design_review_session_id")) and (
        int(evidence.get("blocking_findings_count", 0) or 0) == 0
    )
    workspace_ready = len(files) > 0
    qa_ready = qa.get("status") in ("passed", "passed_with_findings")
    acceptance_ready = int(acc.get("failed", 0) or 0) == 0 and int(acc.get("total", 0) or 0) > 0
    safety_ready = safety.get("status") in ("safe", "safe_with_findings")
    docs_ready = len(missing_sections) == 0

    blocking_reasons: list = []
    warnings: list = []
    if not project_ready:
        blocking_reasons.append("project_brief_missing")
    if not design_ready:
        blocking_reasons.append("design_review_incomplete_or_blocking_findings")
    if not workspace_ready:
        blocking_reasons.append("workspace_not_generated")
    if not qa_ready:
        blocking_reasons.append("qa_not_passed")
    if not acceptance_ready:
        blocking_reasons.append("acceptance_criteria_failed")
    if not safety_ready:
        blocking_reasons.append("safety_not_safe")
    if not docs_ready:
        warnings.append(f"{len(missing_sections)}_sections_missing")
    if gate.warning_checks:
        warnings.append("acceptance_gate_warnings_present")

    all_technical_ready = all(
        (project_ready, design_ready, workspace_ready, qa_ready, acceptance_ready, safety_ready)
    )
    if gate.status in ("passed", "passed_with_findings") and all_technical_ready:
        readiness_status = "ready_for_operator_review"
    elif gate.status in ("blocked", "failed"):
        readiness_status = "blocked"
    else:
        readiness_status = "not_ready"

    return DeliveryReadinessSnapshot(
        readiness_status=readiness_status,
        project_ready=project_ready,
        design_ready=design_ready,
        workspace_ready=workspace_ready,
        qa_ready=qa_ready,
        acceptance_ready=acceptance_ready,
        safety_ready=safety_ready,
        docs_ready=docs_ready,
        human_acceptance_pending=True,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
    )


__all__ = ["build_readiness_snapshot"]
