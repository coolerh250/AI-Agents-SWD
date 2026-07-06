#!/usr/bin/env python3
"""Step 65G.1 -- E2E staging workflow readiness verifier.

Confirms the 65G.1 planning docs define a controlled, auditable E2E execution plan: a test case, an
execution plan, GitHub/Discord/LLM controlled-rail guardrails, budget/call limits, an Admin Console
validation checklist, an abort/reset plan, and an operator-authorization template -- while asserting
this stage executed no workflow and no external call (production_executed stays 0).

Marker: E2E_STAGING_WORKFLOW_READINESS_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
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

MARKER = "E2E_STAGING_WORKFLOW_READINESS_VERIFY"

DOCS = {
    "readiness-report": REPORT,
    "test-case": TEST_CASE,
    "execution-plan": EXEC_PLAN,
    "integration-guardrails": GUARDRAILS,
    "budget-and-call-limits": LIMITS,
    "admin-console-checklist": CHECKLIST,
    "abort-and-reset-plan": ABORT_RESET,
    "operator-authorization-template": AUTH_TEMPLATE,
}

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
PASSWORD_ASSIGN = re.compile(r"password\s*[:=]\s*\S", re.IGNORECASE)
TOKEN_ASSIGN = re.compile(
    r"(token|api[_-]?key|secret|webhook)\s*[:=]\s*[\"']?[A-Za-z0-9/+]{16,}", re.I
)

failures: list[str] = []
gaps: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def gap(m: str) -> None:
    gaps.append(m)
    print(f"  [GAP] {m}")


def main() -> int:
    for name, p in DOCS.items():
        if not p.is_file():
            bad(f"missing doc: docs/staging/{p.name} ({name})")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    low = "\n".join(texts.values()).lower()

    # Test case present.
    if "test case" not in low or "user profile preference api" not in low:
        bad("docs do not define the E2E test case")

    # Controlled rails documented.
    if "github sandbox" not in low and "sandbox draft-pr" not in low and "sandbox repo" not in low:
        bad("docs do not document the GitHub sandbox controlled rail")
    if "mysanbox" not in low or "#general" not in low:
        bad("docs do not document the Discord staging controlled rail (MySanbox/#general)")
    if "budget/audit rail" not in low and "budget/audit" not in low:
        bad("docs do not document the LLM budget/audit rail")

    # Forbidden direct diagnostic calls.
    if "direct diagnostic external call" not in low:
        bad("docs do not forbid direct diagnostic external calls")

    # Budget / call limits.
    if "≤ $1" not in low and "<= $1" not in low and "$1" not in low:
        bad("docs do not document the LLM budget cap")
    if "1 draft-pr flow" not in low and "1 draft pr" not in low:
        bad("docs do not document the GitHub draft-PR flow limit")

    # Operator authorization template + Admin Console checklist + abort/reset.
    if "operator authorization" not in low:
        bad("docs do not include an operator authorization template")
    if "/safety" not in low or "/audit-evidence" not in low:
        bad("docs do not document the Admin Console formal-page checklist")
    if "abort" not in low or "reset" not in low:
        bad("docs do not document the abort/reset plan")

    # This-stage posture: no execution, no external calls.
    if "no workflow execution" not in low and "no workflow was executed" not in low:
        bad("docs do not state no workflow execution in this stage")
    if "no github write" not in low:
        bad("docs do not state no GitHub write in this stage")
    if "no discord send" not in low:
        bad("docs do not state no Discord send in this stage")
    if "no llm call" not in low:
        bad("docs do not state no LLM call in this stage")
    if "no production action" not in low:
        bad("docs do not state no production action in this stage")

    for name, text in texts.items():
        tl = text.lower()
        if "production_executed_true_count=0" not in tl:
            bad(f"{name} does not document production_executed_true_count=0")

    if re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low):
        bad("production_executed_true_count is non-zero")

    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")
        if PASSWORD_ASSIGN.search(text):
            bad(f"{name} contains a stored password assignment")
        if TOKEN_ASSIGN.search(text):
            bad(f"{name} contains a stored token/key/secret value")

    # The stream-mode workflow_state visibility is a tracked gap (expected).
    if "tracked gap" not in low and "workflow_state" not in low:
        gap("docs do not track the workflow-trace-visibility gap for 65G.2")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] E2E test case + execution plan defined; GitHub/Discord/LLM controlled-rail")
    print("       guardrails + budget/call limits + Admin Console checklist + abort/reset plan +")
    print("       operator-authorization template present; no execution/external call; prod_exec=0")
    if gaps:
        print(f"{MARKER}: PASS_WITH_GAPS")
        return 0
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
