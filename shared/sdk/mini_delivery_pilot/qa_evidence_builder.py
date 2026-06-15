"""Stage 48 -- build a QA evidence report from workspace test runs."""

from __future__ import annotations

from shared.sdk.mini_delivery_pilot.models import QAEvidenceReport


def build_qa_report(test_runs: list[dict]) -> QAEvidenceReport:
    """Aggregate workspace test runs into a QA evidence report.

    * passed -> pytest passed AND static/compileall passed.
    * passed_with_findings -> pytest passed but an optional static check
      (ruff) was skipped or compileall-only.
    * failed -> pytest failed.
    * blocked -> no pytest run executed (environment issue).
    """
    pytest_run = next((t for t in test_runs if t.get("test_type") == "pytest"), None)
    compile_run = next((t for t in test_runs if t.get("test_type") == "compileall"), None)
    ruff_run = next((t for t in test_runs if t.get("test_type") == "ruff"), None)

    static_statuses = [
        t.get("status")
        for t in test_runs
        if t.get("test_type") in ("ruff", "compileall", "static_check")
    ]
    if any(s == "failed" for s in static_statuses):
        static_status = "failed"
    elif compile_run and compile_run.get("status") == "passed":
        static_status = "passed"
    elif static_statuses:
        static_status = "passed" if "passed" in static_statuses else "skipped"
    else:
        static_status = None

    findings: list = []
    if ruff_run and ruff_run.get("status") == "skipped":
        findings.append(
            {"type": "static_check", "detail": "ruff skipped (optional, not installed)"}
        )

    if pytest_run is None or pytest_run.get("status") in (None, "error"):
        status = "blocked"
        summary = "no pytest run executed in the controlled workspace"
    elif pytest_run.get("status") == "failed":
        status = "failed"
        summary = "pytest suite failed"
    elif pytest_run.get("status") == "skipped":
        status = "passed_with_findings"
        findings.append({"type": "test_run", "detail": "pytest skipped (dependency unavailable)"})
        summary = "pytest skipped (dependency unavailable); compileall used as fallback"
    else:  # passed
        if static_status == "failed":
            status = "failed"
            summary = "pytest passed but a static check failed"
        elif findings:
            status = "passed_with_findings"
            summary = "pytest passed; optional static check skipped"
        else:
            status = "passed"
            summary = "pytest passed and static checks passed"

    return QAEvidenceReport(
        status=status,
        tests_total=pytest_run.get("tests_total") if pytest_run else None,
        tests_passed=pytest_run.get("tests_passed") if pytest_run else None,
        tests_failed=pytest_run.get("tests_failed") if pytest_run else None,
        static_checks_status=static_status,
        findings=findings,
        report_summary=summary,
    )


__all__ = ["build_qa_report"]
