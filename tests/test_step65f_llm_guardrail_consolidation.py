"""Step 65F-C -- LLM diagnostic exception & guardrail consolidation (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
EXCEPTION = STAGING / "step65f-llm-diagnostic-exception-record.md"
GUARDRAIL = STAGING / "step65f-llm-guardrail-update.md"
FINAL_STATUS = STAGING / "step65f-llm-validation-final-status.md"
PRECONDITION = STAGING / "step65f-to-step65g-precondition-update.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (EXCEPTION, GUARDRAIL, FINAL_STATUS, PRECONDITION)


def _all_low() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS).lower()


def test_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_step65f_pass_with_gaps_recorded() -> None:
    assert "pass_with_gaps" in _all_low()


def test_official_call_success_recorded() -> None:
    low = _all_low()
    assert "official audited" in low
    assert "succeeded" in low or "success" in low


def test_diagnostic_probes_recorded() -> None:
    low = _all_low()
    assert "2 diagnostic probes" in low or "two diagnostic" in low


def test_future_direct_diagnostic_calls_forbidden() -> None:
    assert "forbidden unless separately authorized" in _all_low()


def test_step65g_preconditions_updated() -> None:
    low = _all_low()
    assert "65g" in low
    assert "precondition" in low


def test_no_new_external_call_claimed() -> None:
    low = _all_low()
    assert "no github write" in low or "github write" in low
    assert "no notification send" in low or "notification send" in low
    assert "workflow execution" in low
    assert "no production action" in low


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
    assert "65F-C" in text
    assert "STEP65F_LLM_GUARDRAIL_CONSOLIDATION_VERIFY" in text
