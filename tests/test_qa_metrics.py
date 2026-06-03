"""Stage 29 — QA metric counter shape tests."""

from __future__ import annotations

from shared.sdk.observability.metrics import (
    QA_AUTO_FIX_ATTEMPTS_TOTAL,
    QA_AUTO_FIX_REQUESTS_TOTAL,
    QA_BLOCKED_FOR_HUMAN_REVIEW_TOTAL,
    QA_FINDINGS_TOTAL,
    QA_VALIDATION_FAILED_TOTAL,
    QA_VALIDATION_PASSED_TOTAL,
    QA_VALIDATION_RUNS_TOTAL,
)


def _read(counter, **labels) -> float:
    if labels:
        sample = counter.labels(**labels)
    else:
        sample = counter
    return float(sample._value.get())  # type: ignore[attr-defined]


def test_qa_validation_runs_label_status():
    before = _read(QA_VALIDATION_RUNS_TOTAL, status="started")
    QA_VALIDATION_RUNS_TOTAL.labels(status="started").inc()
    after = _read(QA_VALIDATION_RUNS_TOTAL, status="started")
    assert after == before + 1


def test_qa_validation_passed_counter_inc():
    before = _read(QA_VALIDATION_PASSED_TOTAL)
    QA_VALIDATION_PASSED_TOTAL.inc()
    after = _read(QA_VALIDATION_PASSED_TOTAL)
    assert after == before + 1


def test_qa_validation_failed_counter_label_reason():
    before = _read(QA_VALIDATION_FAILED_TOTAL, reason="max_attempts_exceeded")
    QA_VALIDATION_FAILED_TOTAL.labels(reason="max_attempts_exceeded").inc()
    after = _read(QA_VALIDATION_FAILED_TOTAL, reason="max_attempts_exceeded")
    assert after == before + 1


def test_qa_findings_total_three_labels():
    before = _read(QA_FINDINGS_TOTAL, severity="error", category="syntax", auto_fixable="true")
    QA_FINDINGS_TOTAL.labels(severity="error", category="syntax", auto_fixable="true").inc()
    after = _read(QA_FINDINGS_TOTAL, severity="error", category="syntax", auto_fixable="true")
    assert after == before + 1


def test_qa_auto_fix_requests_label_status():
    before = _read(QA_AUTO_FIX_REQUESTS_TOTAL, status="requested")
    QA_AUTO_FIX_REQUESTS_TOTAL.labels(status="requested").inc()
    after = _read(QA_AUTO_FIX_REQUESTS_TOTAL, status="requested")
    assert after == before + 1


def test_qa_blocked_for_human_review_label_reason():
    before = _read(QA_BLOCKED_FOR_HUMAN_REVIEW_TOTAL, reason="unfixable_blocking_findings")
    QA_BLOCKED_FOR_HUMAN_REVIEW_TOTAL.labels(reason="unfixable_blocking_findings").inc()
    after = _read(QA_BLOCKED_FOR_HUMAN_REVIEW_TOTAL, reason="unfixable_blocking_findings")
    assert after == before + 1


def test_qa_auto_fix_attempts_label_result():
    before = _read(QA_AUTO_FIX_ATTEMPTS_TOTAL, result="completed")
    QA_AUTO_FIX_ATTEMPTS_TOTAL.labels(result="completed").inc()
    after = _read(QA_AUTO_FIX_ATTEMPTS_TOTAL, result="completed")
    assert after == before + 1
