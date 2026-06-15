"""Stage 49 -- delivery readiness snapshot."""

from __future__ import annotations

from shared.sdk.delivery_package.acceptance_gate import evaluate_acceptance_gate
from shared.sdk.delivery_package.readiness_snapshot import build_readiness_snapshot


def _evidence() -> dict:
    return {
        "project_id": "p1",
        "design_review_session_id": "d1",
        "blocking_findings_count": 0,
        "work_items": [{"id": "wi1"}],
        "review": {"decision": "go"},
        "workspace_report": {
            "files": [{"relative_path": "app/main.py"}],
            "test_runs": [{"test_type": "pytest", "status": "passed"}],
        },
        "qa": {"status": "passed"},
        "safety": {"status": "safe", "production_executed_count": 0},
        "acceptance_summary": {"total": 10, "satisfied": 10, "failed": 0},
    }


def test_ready_for_operator_review() -> None:
    ev = _evidence()
    gate = evaluate_acceptance_gate(ev, [])
    snap = build_readiness_snapshot(ev, [], gate)
    assert snap.readiness_status == "ready_for_operator_review"
    assert snap.project_ready
    assert snap.design_ready
    assert snap.workspace_ready
    assert snap.qa_ready
    assert snap.acceptance_ready
    assert snap.safety_ready
    assert snap.docs_ready
    assert snap.human_acceptance_pending is True


def test_blocked_when_gate_blocked() -> None:
    ev = _evidence()
    ev["safety"]["status"] = "blocked"
    gate = evaluate_acceptance_gate(ev, [])
    snap = build_readiness_snapshot(ev, [], gate)
    assert snap.readiness_status == "blocked"
    assert "safety_not_safe" in snap.blocking_reasons
