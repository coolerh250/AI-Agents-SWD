"""Step 65H.1 -- Failure / recovery / governance validation plan (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
PLAN = STAGING / "failure-governance-validation-plan.md"
MATRIX = STAGING / "failure-governance-scenario-matrix.md"
AUTHZ = STAGING / "failure-governance-authorization-matrix.md"
CHECKLIST = STAGING / "failure-governance-admin-console-validation-checklist.md"
ABORT_RESET = STAGING / "failure-governance-abort-reset-plan.md"
RISK = STAGING / "failure-governance-risk-register.md"
SPLIT = STAGING / "failure-governance-execution-split.md"
TEMPLATES = STAGING / "failure-governance-operator-authorization-templates.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (PLAN, MATRIX, AUTHZ, CHECKLIST, ABORT_RESET, RISK, SPLIT, TEMPLATES)


def _all_low() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS).lower()


def test_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_approval_scenarios_documented() -> None:
    low = _all_low()
    assert "approval" in low
    for state in ("granted", "denied", "expired"):
        assert state in low, state


def test_cancel_abort_scenarios_documented() -> None:
    low = _all_low()
    assert "cancel" in low and "abort" in low
    assert "ignore-after-abort" in low


def test_retry_dlq_scenarios_documented() -> None:
    low = _all_low()
    assert "retry" in low and "dlq" in low and "replay" in low


def test_safety_scenarios_documented() -> None:
    low = _all_low()
    assert "no-production" in low or "no production" in low
    assert "kill switch" in low


def test_authorization_templates_documented() -> None:
    low = _all_low()
    assert "operator authorization" in low
    assert "65h.2" in low and "65h.3" in low and "65h.4" in low


def test_abort_reset_plan_documented() -> None:
    low = _all_low()
    assert "abort" in low
    assert "reset" in low


def test_no_execution_claimed() -> None:
    low = _all_low()
    assert "no scenario" in low
    assert "no workflow execution" in low


def test_no_external_action_claimed() -> None:
    low = _all_low()
    assert "no external write" in low or "external-write=false" in low
    assert "no llm call" in low
    assert "no discord send" in low


def test_no_production_action() -> None:
    assert "no production action" in _all_low()


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
    assert "65H.1" in text
    assert "FAILURE_GOVERNANCE_VALIDATION_PLAN_VERIFY" in text
