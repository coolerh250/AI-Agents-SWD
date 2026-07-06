"""Step 65E -- Controlled notification validation (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "controlled-notification-validation-report.md"
EVIDENCE = STAGING / "controlled-notification-validation-evidence.md"
SAFETY = STAGING / "controlled-notification-safety-record.md"
RESET = STAGING / "controlled-notification-reset-record.md"
GAPS = STAGING / "controlled-notification-known-gaps.md"
CONFIRMATION = STAGING / "controlled-notification-operator-confirmation.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (REPORT, EVIDENCE, SAFETY, RESET, GAPS, CONFIRMATION)


def _all_low() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS).lower()


def test_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_one_controlled_send_documented() -> None:
    low = _all_low()
    assert "external_sent=true" in low or 'external_sent": true' in low
    assert "exactly one" in low or "external_sent_count=1" in low


def test_no_production_channel() -> None:
    low = _all_low()
    assert "production channel" in low
    assert "mysanbox" in low and "#general" in low


def test_no_dm() -> None:
    low = _all_low()
    assert "no dm" in low or "no dm was sent" in low


def test_no_secret_values_stored() -> None:
    shapes = re.compile(
        r"(-----BEGIN|ghp_[A-Za-z0-9]{20,}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,}|"
        r"MT[IMQ][A-Za-z0-9_.-]{20,})"
    )
    tok = re.compile(r"(token|api[_-]?key|secret|webhook)\s*[:=]\s*[\"']?[A-Za-z0-9/+]{16,}", re.I)
    for p in DOCS:
        text = p.read_text(encoding="utf-8")
        assert not shapes.search(text), p.name
        assert not tok.search(text), p.name
        assert not re.search(r"password\s*[:=]\s*\S", text, re.IGNORECASE), p.name


def test_reset_documented() -> None:
    low = _all_low()
    assert "run_real_discord_test=false" in low


def test_github_not_written() -> None:
    assert "no github write" in _all_low() or "github write" in _all_low()


def test_llm_not_called() -> None:
    assert "no llm call" in _all_low() or "llm call" in _all_low()


def test_workflow_not_executed() -> None:
    assert "workflow execution" in _all_low()


def test_no_production_action() -> None:
    assert "no production action" in _all_low()


def test_prod_exec_zero_documented() -> None:
    low = _all_low()
    assert "production_executed_true_count=0" in low
    assert not re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low)


def test_operator_confirmation_recorded() -> None:
    text = CONFIRMATION.read_text(encoding="utf-8").lower()
    assert re.search(r"recorded value:\s*\**\s*visible", text)


def test_progress_documents_stage() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "65E" in text
    assert "CONTROLLED_NOTIFICATION_VALIDATION_VERIFY" in text
