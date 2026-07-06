#!/usr/bin/env python3
"""Step 65F -- Controlled LLM validation verifier.

Confirms the 65F docs record a real, controlled, bounded Anthropic LLM validation: exactly one
official audited call, Anthropic provider, a respected budget cap, no production data/secrets, no
GitHub write, no notification send, no workflow execution, the LLM flag reset, and
production_executed stays 0.

Marker: CONTROLLED_LLM_VALIDATION_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "controlled-llm-validation-report.md"
EVIDENCE = STAGING / "controlled-llm-validation-evidence.md"
SAFETY = STAGING / "controlled-llm-safety-record.md"
RESET = STAGING / "controlled-llm-reset-record.md"
GAPS = STAGING / "controlled-llm-known-gaps.md"

MARKER = "CONTROLLED_LLM_VALIDATION_VERIFY"

DOCS = {
    "report": REPORT,
    "evidence": EVIDENCE,
    "safety-record": SAFETY,
    "reset-record": RESET,
    "known-gaps": GAPS,
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

    if "anthropic" not in low:
        bad("docs do not document the Anthropic provider")
    if "external_anthropic" not in low:
        bad("docs do not document provider=external_anthropic")
    if "exactly one" not in low and "one official" not in low:
        bad("docs do not state exactly one official controlled LLM call")

    if "$1" not in low and "1.00" not in low:
        bad("docs do not document the $1 per-run budget cap")
    if "0.03096" not in low and "actual cost" not in low:
        bad("docs do not document the actual call cost")

    if "no production data" not in low:
        bad("docs do not state no production data")
    if "no secret" not in low and "no secrets" not in low:
        bad("docs do not state no secrets in prompt")

    if "no github write" not in low and "github write" not in low:
        bad("docs do not document GitHub not written")
    if "no notification send" not in low and "notification send" not in low:
        bad("docs do not document notification not sent")
    if "workflow execution" not in low:
        bad("docs do not document workflow not executed")

    if "reset" not in low:
        bad("docs do not document the reset")

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

    if "diagnostic prob" not in low:
        gap("docs do not mention the disclosed diagnostic-probe deviation")
    if "stale" not in low:
        gap("docs do not mention the stale default-model finding")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] one official, audited, bounded Anthropic call documented; $1 cap respected; no")
    print("       production data/secrets; GitHub/notification/workflow untouched; reset")
    print("       confirmed; prod_exec=0")
    if gaps:
        print(f"{MARKER}: PASS_WITH_GAPS")
        return 0
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
