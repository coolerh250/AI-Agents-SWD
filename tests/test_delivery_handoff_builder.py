"""Stage 49 -- handoff summaries (business / technical / operator)."""

from __future__ import annotations

from shared.sdk.delivery_package.acceptance_gate import evaluate_acceptance_gate
from shared.sdk.delivery_package.handoff_builder import build_handoff_summaries


def _evidence() -> dict:
    return {
        "project_id": "p1",
        "design_review_session_id": "d1",
        "blocking_findings_count": 0,
        "work_items": [],
        "review": {"decision": "go"},
        "pilot": {"id": "pilot1", "pilot_type": "fastapi_todo_service", "status": "completed"},
        "project": {"title": "Todo Service"},
        "workspace_report": {
            "files": [{"relative_path": "app/main.py"}],
            "test_runs": [{"test_type": "pytest", "status": "passed"}],
        },
        "qa": {"status": "passed", "tests_total": 5, "tests_passed": 5, "tests_failed": 0},
        "safety": {"status": "safe", "production_executed_count": 0},
        "acceptance_summary": {"total": 10, "satisfied": 10, "failed": 0},
    }


def test_three_summary_types() -> None:
    ev = _evidence()
    gate = evaluate_acceptance_gate(ev, [])
    summaries = build_handoff_summaries(ev, gate)
    types = {s.summary_type for s in summaries}
    assert types == {"business_summary", "technical_summary", "operator_summary"}


def test_summaries_have_content() -> None:
    ev = _evidence()
    gate = evaluate_acceptance_gate(ev, [])
    for s in build_handoff_summaries(ev, gate):
        assert s.summary
        assert s.limitations
