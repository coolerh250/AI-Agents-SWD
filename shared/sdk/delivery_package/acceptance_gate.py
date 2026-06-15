"""Stage 49 -- evaluate the acceptance gate for a delivery package.

Maps the mini delivery pilot evidence + package sections to a deterministic
set of acceptance-gate checks. NEVER auto-marks human acceptance: when all
technical checks pass and human acceptance is pending the gate resolves to
``passed_with_findings`` / ``ready_for_operator_review`` with
``human_review_status=pending`` -- it never returns ``accepted``.

Blocking logic:
* any failed critical safety / governance check -> blocked
* acceptance failed > 0 -> blocked
* tests failed -> blocked
* ruff skipped (documented) while pytest/compileall passed -> warning, not blocking
"""

from __future__ import annotations

import uuid

from shared.sdk.delivery_package.models import AcceptanceGateCheckResult, AcceptanceGateRun


def _check(key, ctype, status, severity, blocking, summary, ref=None):
    return AcceptanceGateCheckResult(
        check_key=key,
        check_type=ctype,
        status=status,
        severity=severity,
        blocking=blocking,
        evidence_ref=ref or {},
        summary=summary,
    )


def evaluate_acceptance_gate(
    evidence: dict,
    sections: list,
    *,
    gate_type: str = "mini_delivery_acceptance",
) -> AcceptanceGateRun:
    """Build a deterministic acceptance gate run from evidence + sections."""
    qa = evidence.get("qa") or {}
    safety = evidence.get("safety") or {}
    acc = evidence.get("acceptance_summary") or {}
    review = evidence.get("review") or {}
    workspace_report = evidence.get("workspace_report") or {}
    files = workspace_report.get("files") or []
    test_runs = workspace_report.get("test_runs") or []
    pytest_run: dict = next((t for t in test_runs if t.get("test_type") == "pytest"), {})

    blocking_design = int(evidence.get("blocking_findings_count", 0) or 0)
    missing_sections = [s for s in sections if getattr(s, "status", None) == "missing"]

    qa_ok = qa.get("status") in ("passed", "passed_with_findings")
    safety_ok = safety.get("status") in ("safe", "safe_with_findings")
    tests_failed = qa.get("status") == "failed" or pytest_run.get("status") == "failed"
    acc_failed = int(acc.get("failed", 0) or 0)

    checks: list[AcceptanceGateCheckResult] = [
        _check(
            "project_brief_exists",
            "project",
            "passed" if evidence.get("project_id") else "failed",
            "high",
            True,
            "project brief present",
            {"project_id": evidence.get("project_id")},
        ),
        _check(
            "task_graph_valid",
            "project",
            "passed" if (evidence.get("work_items") or evidence.get("project_id")) else "failed",
            "medium",
            True,
            "task graph / work items present",
        ),
        _check(
            "design_review_completed",
            "design_review",
            "passed" if evidence.get("design_review_session_id") else "failed",
            "high",
            True,
            f"design review decision={review.get('decision')}",
        ),
        _check(
            "no_blocking_design_findings",
            "design_review",
            "passed" if blocking_design == 0 else "failed",
            "high",
            True,
            f"blocking design findings={blocking_design}",
        ),
        _check(
            "workspace_generated",
            "workspace",
            "passed" if files else "failed",
            "high",
            True,
            f"{len(files)} files generated",
        ),
        _check(
            "tests_passed",
            "testing",
            "failed" if tests_failed else "passed",
            "high",
            True,
            f"pytest status={pytest_run.get('status') or qa.get('status')}",
        ),
        _check(
            "acceptance_criteria_satisfied",
            "acceptance",
            "failed" if acc_failed > 0 else "passed",
            "high",
            True,
            f"{acc.get('satisfied', 0)}/{acc.get('total', 0)} satisfied, {acc_failed} failed",
        ),
        _check(
            "qa_report_passed",
            "qa",
            "passed" if qa_ok else "failed",
            "medium",
            False,
            f"QA status={qa.get('status')}",
        ),
        _check(
            "safety_report_safe",
            "safety",
            "passed" if safety_ok else "failed",
            "critical",
            True,
            f"safety status={safety.get('status')}",
        ),
        _check(
            "no_github_write",
            "governance",
            "passed" if not safety.get("github_write_performed") else "failed",
            "critical",
            True,
            "no GitHub write",
        ),
        _check(
            "no_pr_created",
            "governance",
            "passed" if not safety.get("pr_created") else "failed",
            "critical",
            True,
            "no PR created",
        ),
        _check(
            "no_deploy",
            "governance",
            "passed" if not safety.get("deployment_performed") else "failed",
            "critical",
            True,
            "no deploy",
        ),
        _check(
            "no_production_execution",
            "governance",
            "passed" if int(safety.get("production_executed_count", 0) or 0) == 0 else "failed",
            "critical",
            True,
            "no production execution",
        ),
        _check(
            "no_secret_leak",
            "governance",
            "passed" if not safety.get("secret_leak_detected") else "failed",
            "critical",
            True,
            "no secret leak",
        ),
        _check(
            "delivery_sections_complete",
            "documentation",
            "passed" if not missing_sections else "warning",
            "medium",
            False,
            f"{len(missing_sections)} missing sections",
        ),
        _check(
            "known_limitations_documented",
            "documentation",
            "passed",
            "info",
            False,
            "known limitations documented",
        ),
        _check(
            "run_instructions_present",
            "documentation",
            "passed",
            "info",
            False,
            "run instructions present",
        ),
        # Human acceptance is pending -- a warning, NEVER blocking, NEVER auto-checked.
        _check(
            "human_acceptance_pending",
            "human_review",
            "warning",
            "info",
            False,
            "human acceptance is pending (operator review required)",
        ),
    ]

    total = len(checks)
    passed = sum(1 for c in checks if c.status == "passed")
    failed = sum(1 for c in checks if c.status == "failed")
    warning = sum(1 for c in checks if c.status == "warning")
    blocking_failed = sum(1 for c in checks if c.status == "failed" and c.blocking)

    if blocking_failed > 0 or tests_failed or acc_failed > 0 or not safety_ok:
        status = "blocked"
        decision = "needs_changes" if not safety_ok or tests_failed or acc_failed else "blocked"
        human_review_status = "pending"
    elif warning > 0:
        status = "passed_with_findings"
        decision = "ready_for_operator_review"
        human_review_status = "pending"
    else:
        status = "passed"
        decision = "ready_for_operator_review"
        human_review_status = "pending"

    return AcceptanceGateRun(
        gate_key=f"gate-{uuid.uuid4().hex[:12]}",
        gate_type=gate_type,
        status=status,
        decision=decision,
        human_review_required=True,
        human_review_status=human_review_status,
        blocking_findings_count=blocking_failed,
        total_checks=total,
        passed_checks=passed,
        failed_checks=failed,
        warning_checks=warning,
        checks=checks,
    )


__all__ = ["evaluate_acceptance_gate"]
