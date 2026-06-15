"""Stage 48 -- evidence-based acceptance evaluator."""

from __future__ import annotations

from shared.sdk.mini_delivery_pilot.acceptance_evaluator import (
    evaluate_acceptance,
    summarize_acceptance,
)

CRITERIA = [
    {
        "id": "c1",
        "criterion_key": "AC-001",
        "description": "Can create a todo.",
        "verification_method": "integration_test",
        "work_item_id": "w1",
    },
    {
        "id": "c2",
        "criterion_key": "AC-002",
        "description": "Can list todos.",
        "verification_method": "integration_test",
        "work_item_id": "w1",
    },
    {
        "id": "c3",
        "criterion_key": "AC-003",
        "description": "Can get a todo by id.",
        "verification_method": "integration_test",
        "work_item_id": "w1",
    },
    {
        "id": "c4",
        "criterion_key": "AC-004",
        "description": "Can update a todo.",
        "verification_method": "integration_test",
        "work_item_id": "w1",
    },
    {
        "id": "c5",
        "criterion_key": "AC-005",
        "description": "Can delete a todo.",
        "verification_method": "integration_test",
        "work_item_id": "w1",
    },
    {
        "id": "c6",
        "criterion_key": "AC-006",
        "description": "SQLite persistence works locally.",
        "verification_method": "integration_test",
        "work_item_id": "w2",
    },
    {
        "id": "c7",
        "criterion_key": "AC-007",
        "description": "pytest suite passes.",
        "verification_method": "unit_test",
        "work_item_id": "w3",
    },
    {
        "id": "c8",
        "criterion_key": "AC-008",
        "description": "README explains setup, run, test, and API examples.",
        "verification_method": "documentation_review",
        "work_item_id": "w4",
    },
    {
        "id": "c9",
        "criterion_key": "AC-009",
        "description": "No production deployment attempted.",
        "verification_method": "static_check",
        "work_item_id": None,
    },
    {
        "id": "c10",
        "criterion_key": "AC-010",
        "description": "No secret required.",
        "verification_method": "static_check",
        "work_item_id": None,
    },
]
FILES = ["app/main.py", "app/database.py", "README.md", "tests/test_todos.py"]


def _by_key(evals):
    return {e.criterion_key: e for e in evals}


def test_all_satisfied_when_tests_pass() -> None:
    evals = evaluate_acceptance(
        criteria=CRITERIA,
        pytest_status="passed",
        pytest_passed=7,
        pytest_failed=0,
        generated_files=FILES,
        safety_ok=True,
    )
    summary = summarize_acceptance(evals)
    assert summary["total"] == 10
    assert summary["satisfied"] == 10
    assert summary["failed"] == 0
    byk = _by_key(evals)
    assert byk["AC-001"].evidence_type == "test_run"
    assert byk["AC-008"].evidence_type == "generated_file"
    assert byk["AC-009"].evidence_type == "static_check"


def test_crud_pending_when_tests_skipped() -> None:
    evals = evaluate_acceptance(
        criteria=CRITERIA,
        pytest_status="skipped",
        pytest_passed=None,
        pytest_failed=None,
        generated_files=FILES,
        safety_ok=True,
    )
    byk = _by_key(evals)
    assert byk["AC-001"].evaluation_status == "pending"
    # README + safety still satisfied (file/safety evidence)
    assert byk["AC-008"].evaluation_status == "satisfied"
    assert byk["AC-009"].evaluation_status == "satisfied"


def test_crud_failed_when_tests_fail() -> None:
    evals = evaluate_acceptance(
        criteria=CRITERIA,
        pytest_status="failed",
        pytest_passed=5,
        pytest_failed=2,
        generated_files=FILES,
        safety_ok=True,
    )
    assert _by_key(evals)["AC-007"].evaluation_status == "failed"


def test_readme_pending_when_missing() -> None:
    evals = evaluate_acceptance(
        criteria=CRITERIA,
        pytest_status="passed",
        pytest_passed=7,
        pytest_failed=0,
        generated_files=["app/main.py"],
        safety_ok=True,
    )
    assert _by_key(evals)["AC-008"].evaluation_status == "pending"


def test_safety_failed_when_not_ok() -> None:
    evals = evaluate_acceptance(
        criteria=CRITERIA,
        pytest_status="passed",
        pytest_passed=7,
        pytest_failed=0,
        generated_files=FILES,
        safety_ok=False,
    )
    assert _by_key(evals)["AC-009"].evaluation_status == "failed"
