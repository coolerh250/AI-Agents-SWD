"""Step 65I -- Staging functional acceptance report (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "staging-functional-acceptance-report.md"
EVIDENCE = STAGING / "staging-functional-acceptance-evidence-summary.md"
GAPS = STAGING / "staging-functional-acceptance-gap-register.md"
DECISION = STAGING / "staging-functional-acceptance-decision-template.md"
PROD_SEP = STAGING / "staging-functional-acceptance-production-readiness-separation.md"
NEXT = STAGING / "staging-functional-acceptance-next-actions.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (REPORT, EVIDENCE, GAPS, DECISION, PROD_SEP, NEXT)


def _all_low() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS).lower()


def test_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_all_stages_summarized() -> None:
    low = _all_low()
    for stage in ("65a", "65b", "65c", "65d", "65e", "65f", "65g", "65h"):
        assert stage in low, stage


def test_integrations_summarized() -> None:
    low = _all_low()
    assert "github sandbox" in low and "validated" in low
    assert "discord" in low
    assert "governance gap" in low or "validated_with_governance_gap" in low


def test_e2e_summarized() -> None:
    low = _all_low()
    assert "fresh" in low and "e2e" in low


def test_failure_governance_summarized() -> None:
    assert "completed_with_gaps" in _all_low()


def test_gap_classification_present() -> None:
    low = _all_low()
    for cls in (
        "accepted_staging_gap",
        "operator_ux_gap",
        "production_readiness_gap",
        "deferred_scope",
    ):
        assert cls in low, cls


def test_production_readiness_separation_present() -> None:
    low = _all_low()
    assert "production readiness" in low
    assert "not production readiness" in low


def test_operator_decision_template_present() -> None:
    low = _all_low()
    assert "pass_with_accepted_gaps" in low
    assert "fail" in low


def test_no_final_decision_by_claude_code() -> None:
    low = _all_low()
    assert "claude code does not decide" in low or "does not choose" in low


def test_no_new_execution_claimed() -> None:
    low = _all_low()
    assert "no new workflow" in low
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
    assert "65I" in text
    assert "STAGING_FUNCTIONAL_ACCEPTANCE_REPORT_VERIFY" in text
