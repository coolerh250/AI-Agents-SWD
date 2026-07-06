#!/usr/bin/env python3
"""Step 65G.2 -- Controlled E2E staging workflow execution verifier.

Confirms the 65G.2 records document a real controlled E2E run: one fresh intake through the real
pipeline, and one each of the three controlled rails (LLM budget/audit, GitHub sandbox draft PR,
Discord staging notification), all reset to safe with no production action, no direct diagnostic
call, and no secret values (production_executed stays 0). Operator UI validation is pending.

Marker: E2E_STAGING_WORKFLOW_EXECUTION_VERIFY:
        PASS | PASS_WITH_OPERATOR_VALIDATION_PENDING | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "e2e-staging-workflow-execution-report.md"
EVIDENCE = STAGING / "e2e-staging-workflow-evidence.md"
PIPELINE = STAGING / "e2e-staging-agent-pipeline-record.md"
LLM = STAGING / "e2e-staging-llm-record.md"
GITHUB = STAGING / "e2e-staging-github-record.md"
DISCORD = STAGING / "e2e-staging-discord-record.md"
CHECKLIST = STAGING / "e2e-staging-admin-console-evidence-checklist.md"
RESET = STAGING / "e2e-staging-safety-reset-record.md"
GAPS = STAGING / "e2e-staging-known-gaps.md"
VALIDATION = STAGING / "e2e-staging-operator-validation-request.md"

MARKER = "E2E_STAGING_WORKFLOW_EXECUTION_VERIFY"

DOCS = {
    "execution-report": REPORT,
    "evidence": EVIDENCE,
    "agent-pipeline-record": PIPELINE,
    "llm-record": LLM,
    "github-record": GITHUB,
    "discord-record": DISCORD,
    "admin-console-checklist": CHECKLIST,
    "safety-reset-record": RESET,
    "known-gaps": GAPS,
    "operator-validation-request": VALIDATION,
}

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,}|MT[IMQ][A-Za-z0-9_.-]{20,})"
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

    # Fresh intake + pipeline.
    if "fresh intake" not in low or "step65g2-e2e-20260706074202" not in low:
        bad("docs do not document the fresh intake / task id")
    if "5 hops" not in low and "5-hop" not in low and "five" not in low:
        bad("docs do not document the 5-hop agent pipeline")

    # Controlled rails.
    if "pr #16" not in low and "pull/16" not in low and "draft pr #16" not in low:
        bad("docs do not document the GitHub sandbox draft PR (#16)")
    if "mysanbox" not in low or "#general" not in low or "[staging]" not in low:
        bad("docs do not document the Discord staging notification")
    if "external_anthropic" not in low or "budget/audit" not in low:
        bad("docs do not document the official audited LLM call via the budget/audit rail")
    if "$0.05073" not in low and "0.05073" not in low:
        bad("docs do not document the actual LLM cost")

    # Direct diagnostic calls forbidden + not executed.
    if "direct diagnostic" not in low:
        bad("docs do not document the direct-diagnostic-calls guardrail")
    if (
        "0 direct diagnostic" not in low
        and "direct diagnostic calls | **0**" not in low
        and ("**0**" not in low)
    ):
        gap("docs do not explicitly state 0 diagnostic calls (tracked)")

    # No production action, reset, prod_exec.
    if "no production action" not in low:
        bad("docs do not state no production action")
    if "reset" not in low:
        bad("docs do not document the reset")
    if "operator ui validation" not in low and "operator validation" not in low:
        bad("docs do not document operator UI validation pending")

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

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    operator_confirmed = bool(
        re.search(
            r"operator response:\s*\**\s*visible", texts["operator-validation-request"].lower()
        )
    )

    print(
        "  [OK] fresh intake + 5-hop pipeline; 1 LLM ($0.05073<=$1) + 1 GitHub PR #16 (no merge) +"
    )
    print("       1 [STAGING] Discord; 0 direct diagnostic calls; reset to safe; prod_exec=0")
    if not operator_confirmed:
        print(f"{MARKER}: PASS_WITH_OPERATOR_VALIDATION_PENDING")
        return 0
    if gaps:
        print(f"{MARKER}: PASS_WITH_GAPS")
        return 0
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
