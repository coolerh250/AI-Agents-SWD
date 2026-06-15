"""Stage 49 -- acceptance gate evaluation logic."""

from __future__ import annotations

from shared.sdk.delivery_package.acceptance_gate import evaluate_acceptance_gate


def _good_evidence() -> dict:
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
        "safety": {
            "status": "safe",
            "production_executed_count": 0,
            "github_write_performed": False,
            "pr_created": False,
            "deployment_performed": False,
            "secret_leak_detected": False,
        },
        "acceptance_summary": {"total": 10, "satisfied": 10, "failed": 0},
    }


def test_gate_passes_with_findings_when_human_pending() -> None:
    gate = evaluate_acceptance_gate(_good_evidence(), [])
    assert gate.status in ("passed", "passed_with_findings")
    assert gate.decision == "ready_for_operator_review"
    assert gate.human_review_status == "pending"
    assert gate.blocking_findings_count == 0
    assert gate.failed_checks == 0
    assert gate.total_checks >= 15


def test_gate_never_auto_accepts() -> None:
    gate = evaluate_acceptance_gate(_good_evidence(), [])
    assert gate.decision != "accepted"
    assert gate.human_review_required is True


def test_gate_blocks_on_failed_tests() -> None:
    ev = _good_evidence()
    ev["qa"] = {"status": "failed"}
    ev["workspace_report"]["test_runs"] = [{"test_type": "pytest", "status": "failed"}]
    gate = evaluate_acceptance_gate(ev, [])
    assert gate.status in ("blocked", "failed")
    tests_check = next(c for c in gate.checks if c.check_key == "tests_passed")
    assert tests_check.status == "failed"


def test_gate_blocks_on_unsafe_safety() -> None:
    ev = _good_evidence()
    ev["safety"]["status"] = "blocked"
    gate = evaluate_acceptance_gate(ev, [])
    assert gate.status in ("blocked", "failed")


def test_gate_blocks_on_acceptance_failure() -> None:
    ev = _good_evidence()
    ev["acceptance_summary"] = {"total": 10, "satisfied": 9, "failed": 1}
    gate = evaluate_acceptance_gate(ev, [])
    assert gate.status in ("blocked", "failed")


def test_gate_blocks_on_github_write() -> None:
    ev = _good_evidence()
    ev["safety"]["github_write_performed"] = True
    gate = evaluate_acceptance_gate(ev, [])
    chk = next(c for c in gate.checks if c.check_key == "no_github_write")
    assert chk.status == "failed"
    assert gate.status in ("blocked", "failed")


def test_governance_checks_present() -> None:
    gate = evaluate_acceptance_gate(_good_evidence(), [])
    keys = {c.check_key for c in gate.checks}
    for expected in (
        "no_github_write",
        "no_pr_created",
        "no_deploy",
        "no_production_execution",
        "no_secret_leak",
        "human_acceptance_pending",
    ):
        assert expected in keys
    human = next(c for c in gate.checks if c.check_key == "human_acceptance_pending")
    assert human.blocking is False
