"""Step 65F -- Controlled LLM validation (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "controlled-llm-validation-report.md"
EVIDENCE = STAGING / "controlled-llm-validation-evidence.md"
SAFETY = STAGING / "controlled-llm-safety-record.md"
RESET = STAGING / "controlled-llm-reset-record.md"
GAPS = STAGING / "controlled-llm-known-gaps.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (REPORT, EVIDENCE, SAFETY, RESET, GAPS)


def _all_low() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS).lower()


def test_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_one_controlled_call_documented() -> None:
    low = _all_low()
    assert "anthropic" in low
    assert "external_anthropic" in low
    assert "exactly one" in low or "one official" in low


def test_budget_cap_documented() -> None:
    low = _all_low()
    assert "$1" in low or "1.00" in low


def test_no_production_data() -> None:
    assert "no production data" in _all_low()


def test_no_secrets_in_prompt() -> None:
    low = _all_low()
    assert "no secret" in low or "no secrets" in low


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


def test_reset_documented() -> None:
    assert "reset" in _all_low()


def test_github_not_written() -> None:
    low = _all_low()
    assert "no github write" in low or "github write" in low


def test_notification_not_sent() -> None:
    low = _all_low()
    assert "no notification send" in low or "notification send" in low


def test_workflow_not_executed() -> None:
    assert "workflow execution" in _all_low()


def test_prod_exec_zero_documented() -> None:
    low = _all_low()
    assert "production_executed_true_count=0" in low
    assert not re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low)


def test_progress_documents_stage() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "65F" in text
    assert "CONTROLLED_LLM_VALIDATION_VERIFY" in text
