"""Stage 48 -- QA evidence builder."""

from __future__ import annotations

from shared.sdk.mini_delivery_pilot.qa_evidence_builder import build_qa_report


def _runs(pytest_status, *, ruff="passed", compileall="passed", total=7, passed=7, failed=0):
    runs = [
        {
            "test_type": "pytest",
            "status": pytest_status,
            "tests_total": total,
            "tests_passed": passed,
            "tests_failed": failed,
        },
        {"test_type": "compileall", "status": compileall},
    ]
    if ruff is not None:
        runs.append({"test_type": "ruff", "status": ruff})
    return runs


def test_passed_when_all_green() -> None:
    qa = build_qa_report(_runs("passed"))
    assert qa.status == "passed"
    assert qa.tests_passed == 7
    assert qa.tests_failed == 0
    assert qa.static_checks_status == "passed"


def test_passed_with_findings_when_ruff_skipped() -> None:
    qa = build_qa_report(_runs("passed", ruff="skipped"))
    assert qa.status == "passed_with_findings"
    assert any("ruff" in str(f).lower() for f in qa.findings)


def test_failed_when_pytest_failed() -> None:
    qa = build_qa_report(_runs("failed", failed=2))
    assert qa.status == "failed"


def test_blocked_when_no_pytest() -> None:
    qa = build_qa_report([{"test_type": "compileall", "status": "passed"}])
    assert qa.status == "blocked"


def test_passed_with_findings_when_pytest_skipped() -> None:
    qa = build_qa_report(_runs("skipped"))
    assert qa.status == "passed_with_findings"
