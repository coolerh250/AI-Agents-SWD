"""Step 65G.1 -- E2E staging workflow readiness (docs + posture)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "e2e-staging-workflow-readiness-report.md"
TEST_CASE = STAGING / "e2e-staging-workflow-test-case.md"
EXEC_PLAN = STAGING / "e2e-staging-workflow-execution-plan.md"
GUARDRAILS = STAGING / "e2e-staging-integration-guardrails.md"
LIMITS = STAGING / "e2e-staging-budget-and-call-limits.md"
CHECKLIST = STAGING / "e2e-staging-admin-console-validation-checklist.md"
ABORT_RESET = STAGING / "e2e-staging-abort-and-reset-plan.md"
AUTH_TEMPLATE = STAGING / "e2e-staging-operator-authorization-template.md"
PROGRESS = ROOT / "source" / "progress.md"

DOCS = (
    REPORT,
    TEST_CASE,
    EXEC_PLAN,
    GUARDRAILS,
    LIMITS,
    CHECKLIST,
    ABORT_RESET,
    AUTH_TEMPLATE,
)


def _all_low() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS).lower()


def test_docs_exist() -> None:
    for p in DOCS:
        assert p.is_file(), p.name


def test_test_case_documented() -> None:
    low = _all_low()
    assert "test case" in low
    assert "user profile preference api" in low


def test_integration_guardrails_documented() -> None:
    low = _all_low()
    assert "sandbox repo" in low or "sandbox draft-pr" in low
    assert "mysanbox" in low and "#general" in low
    assert "budget/audit" in low
    assert "direct diagnostic external call" in low


def test_budget_and_call_limits_documented() -> None:
    low = _all_low()
    assert "$1" in low
    assert "1 draft-pr flow" in low or "1 draft pr" in low


def test_operator_authorization_template_documented() -> None:
    assert "operator authorization" in _all_low()


def test_admin_console_checklist_documented() -> None:
    low = _all_low()
    assert "/safety" in low
    assert "/audit-evidence" in low
    assert "/agent-executions" in low


def test_abort_and_reset_plan_documented() -> None:
    low = _all_low()
    assert "abort" in low
    assert "reset" in low


def test_no_runtime_execution_claimed() -> None:
    low = _all_low()
    assert "no workflow execution" in low or "no workflow was executed" in low
    assert "no github write" in low
    assert "no discord send" in low
    assert "no llm call" in low


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
    assert "65G.1" in text
    assert "E2E_STAGING_WORKFLOW_READINESS_VERIFY" in text
