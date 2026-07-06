#!/usr/bin/env python3
"""Step 65F-C -- LLM diagnostic exception & guardrail consolidation verifier.

Confirms the 65F-C docs formally reconcile the two diagnostic Anthropic probes disclosed in the
Step 65F report, correct Step 65F to PASS_WITH_GAPS while preserving the official audited call's
success, add a forward-looking guardrail forbidding unauthorized direct diagnostic external calls,
update the Step 65G preconditions, and assert no new external call occurred in this stage
(production_executed stays 0).

Marker: STEP65F_LLM_GUARDRAIL_CONSOLIDATION_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
EXCEPTION = STAGING / "step65f-llm-diagnostic-exception-record.md"
GUARDRAIL = STAGING / "step65f-llm-guardrail-update.md"
FINAL_STATUS = STAGING / "step65f-llm-validation-final-status.md"
PRECONDITION = STAGING / "step65f-to-step65g-precondition-update.md"

MARKER = "STEP65F_LLM_GUARDRAIL_CONSOLIDATION_VERIFY"

DOCS = {
    "diagnostic-exception": EXCEPTION,
    "guardrail-update": GUARDRAIL,
    "final-status": FINAL_STATUS,
    "precondition-update": PRECONDITION,
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

    if "pass_with_gaps" not in low:
        bad("docs do not record Step 65F as PASS_WITH_GAPS")
    if "official audited" not in low or ("succeeded" not in low and "success" not in low):
        bad("docs do not preserve the official audited call's success")
    if "2 diagnostic probes" not in low and "two diagnostic" not in low:
        bad("docs do not document the 2 diagnostic probes")
    if "forbidden unless separately authorized" not in low:
        bad(
            "docs do not forbid future direct diagnostic external calls unless separately authorized"
        )
    if "65g" not in low or "precondition" not in low:
        bad("docs do not document updated Step 65G preconditions")

    if "no new" not in low and "no llm call" not in low:
        bad("docs do not state no new LLM call occurred in this stage")
    if "no github write" not in low and "github write" not in low:
        bad("docs do not document no GitHub write")
    if "no notification send" not in low and "notification send" not in low:
        bad("docs do not document no notification send")
    if "workflow execution" not in low:
        bad("docs do not document no workflow execution")
    if "no production action" not in low:
        bad("docs do not state no production action")

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

    if "validated_with_governance_gap" not in low:
        gap("docs do not explicitly state LLM integration status VALIDATED_WITH_GOVERNANCE_GAP")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] Step 65F corrected to PASS_WITH_GAPS; official audited call success preserved;")
    print("       diagnostic probes disclosed; future unauthorized direct diagnostic calls")
    print("       forbidden; 65G preconditions updated; no new external call; prod_exec=0")
    if gaps:
        print(f"{MARKER}: PASS_WITH_GAPS")
        return 0
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
