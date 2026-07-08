"""Step 65H.4 -- Retry / DLQ / manual replay validation (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "retry-dlq-validation-report.md"
EVIDENCE = STAGING / "retry-dlq-evidence.md"
SAFETY = STAGING / "retry-dlq-safety-record.md"
GAPS = STAGING / "retry-dlq-known-gaps.md"
VALIDATION = STAGING / "retry-dlq-operator-validation-request.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (REPORT, EVIDENCE, SAFETY, GAPS, VALIDATION)


def _all_low() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS).lower()


def test_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_retry_dlq_paths_documented() -> None:
    low = _all_low()
    assert "simulate_failure" in low
    assert "retry" in low and "scheduler" in low
    assert "deadletter" in low or "dlq" in low or "dead-letter" in low
    assert "manual replay" in low and "replayed" in low
    assert "terminal failure" in low and "deadletter.terminal" in low


def test_retry_count_limit_documented() -> None:
    low = _all_low()
    assert "max_retries=3" in low or "retry_count" in low


def test_no_unsafe_methods() -> None:
    low = _all_low()
    assert "no unsafe stream injection" in low or "no db manipulation" in low


def test_no_external_integration() -> None:
    low = _all_low()
    assert "no external" in low or "external-write=false" in low
    for phrase in ("no github write", "no discord send", "no llm call"):
        assert phrase in low, phrase


def test_no_production_action() -> None:
    assert "no production action" in _all_low()


def test_operator_validation_pending() -> None:
    low = _all_low()
    assert "operator ui validation" in low or "operator validation" in low
    assert "pending" in low


def test_no_secret_values_stored() -> None:
    shapes = re.compile(
        r"(-----BEGIN|ghp_[A-Za-z0-9]{20,}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    tok = re.compile(r"(token|api[_-]?key|secret|webhook)\s*[:=]\s*[\"']?[A-Za-z0-9/+]{16,}", re.I)
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert not shapes.search(text), p.name
        assert not tok.search(text), p.name
        assert not re.search(r"password\s*[:=]\s*\S", text, re.IGNORECASE), p.name


def test_prod_exec_zero_documented() -> None:
    low = _all_low()
    assert "production_executed_true_count=0" in low
    assert not re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low)


def test_progress_documents_stage() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "65H.4" in text
    assert "RETRY_DLQ_VALIDATION_VERIFY" in text
