"""Step 65H.5 -- Failure & governance operator evidence review (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REVIEW = STAGING / "failure-governance-operator-evidence-review.md"
SCENARIOS = STAGING / "failure-governance-validated-scenarios-summary.md"
GAP_CLASS = STAGING / "failure-governance-gap-classification.md"
UX_GAP = STAGING / "failure-governance-operator-ux-gap-register.md"
SAFETY = STAGING / "failure-governance-safety-summary.md"
READINESS = STAGING / "failure-governance-step65i-readiness.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (REVIEW, SCENARIOS, GAP_CLASS, UX_GAP, SAFETY, READINESS)


def _all_low() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS).lower()


def test_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_substages_consolidated() -> None:
    low = _all_low()
    for s in ("65h.2", "65h.3", "65h.4"):
        assert s in low, s
    assert "pass_with_gaps" in low
    assert "completed_with_gaps" in low


def test_operator_visibility_documented() -> None:
    low = _all_low()
    assert "visible" in low
    assert "partial_with_gaps" in low


def test_dlq_ux_gap_documented() -> None:
    low = _all_low()
    assert "dlq" in low
    assert "admin console page" in low


def test_approval_expiry_gap_documented() -> None:
    low = _all_low()
    assert "expiry" in low or "expired" in low


def test_late_stream_gap_documented() -> None:
    low = _all_low()
    assert "late-stream" in low or "late stream" in low or "late-stream-event" in low


def test_no_new_execution_claimed() -> None:
    low = _all_low()
    assert "no new scenario" in low


def test_no_external_action_claimed() -> None:
    low = _all_low()
    assert "no external" in low or "external-write=false" in low
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


def test_step65i_readiness_documented() -> None:
    low = _all_low()
    assert "65i" in low
    assert "readiness" in low or "ready" in low


def test_progress_documents_stage() -> None:
    text = PROGRESS.read_text(encoding="utf-8")
    assert "65H.5" in text
    assert "FAILURE_GOVERNANCE_OPERATOR_REVIEW_VERIFY" in text
