"""Stage 48 -- mini delivery report builder."""

from __future__ import annotations

from shared.sdk.mini_delivery_pilot.models import QAEvidenceReport, SafetyEvidenceReport
from shared.sdk.mini_delivery_pilot.report_builder import build_mini_delivery_report


def _report(qa_status="passed", safety_status="safe", failed=0):
    return build_mini_delivery_report(
        pilot_type="fastapi_todo_service",
        project_summary={"project_id": "p1"},
        design_review_summary={"decision": "planning_only"},
        workspace_summary={"generated_files_count": 12},
        qa=QAEvidenceReport(status=qa_status, tests_total=7, tests_passed=7, tests_failed=0),
        acceptance_summary={"total": 10, "satisfied": 10, "failed": failed, "pending": 0},
        safety=SafetyEvidenceReport(status=safety_status),
    )


def test_report_ready_when_green() -> None:
    r = _report()
    assert r.status == "ready"
    assert r.executive_summary
    assert r.project_summary and r.design_review_summary and r.workspace_summary
    assert r.qa_summary["status"] == "passed"
    assert r.safety_summary["status"] == "safe"
    assert any("auth" in lim.lower() for lim in r.known_limitations)
    assert any("Step 47" in s for s in r.next_steps)


def test_report_draft_when_acceptance_failed() -> None:
    assert _report(failed=1).status == "draft"


def test_report_draft_when_qa_failed() -> None:
    assert _report(qa_status="failed").status == "draft"
