#!/usr/bin/env python3
"""Step 65G.2-V -- E2E operator UI validation verifier.

Confirms the operator UI validation record documents the operator's VISIBLE response on the formal
Admin Console pages, corrects Step 65G.2 to PASS, records the fresh-E2E gap as resolved, and asserts
no new external action occurred in this validation-record stage (production_executed stays 0).

Marker: E2E_OPERATOR_UI_VALIDATION_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
RECORD = STAGING / "e2e-staging-operator-ui-validation-record.md"

MARKER = "E2E_OPERATOR_UI_VALIDATION_VERIFY"

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
PASSWORD_ASSIGN = re.compile(r"password\s*[:=]\s*\S", re.IGNORECASE)
TOKEN_ASSIGN = re.compile(
    r"(token|api[_-]?key|secret|webhook)\s*[:=]\s*[\"']?[A-Za-z0-9/+]{16,}", re.I
)

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    if not RECORD.is_file():
        bad(f"missing doc: docs/staging/{RECORD.name}")
        print(f"{MARKER}: FAIL")
        return 1

    text = RECORD.read_text(encoding="utf-8")
    low = text.lower()

    if not re.search(r"operator response:\s*\**\s*visible", low):
        bad("record does not document the operator VISIBLE response")
    if "step 65g.2 final status: pass" not in low and "step 65g.2: **pass**" not in low:
        bad("record does not document Step 65G.2 final status PASS")
    if "operator_visible" not in low:
        bad("record does not document Admin Console formal evidence OPERATOR_VISIBLE")
    if "fresh e2e" not in low or ("resolved" not in low and "validated" not in low):
        bad("record does not document the fresh E2E gap as resolved/validated")
    if "demo evidence was not used" not in low and "not used as the acceptance path" not in low:
        bad("record does not document that Diagnostics/Demo Evidence was not the acceptance path")

    # No new external action in this stage.
    if "no new external action" not in low:
        bad("record does not state no new external action occurred")
    for phrase in ("no workflow execution", "no github write", "no discord send", "no llm call"):
        if phrase not in low:
            bad(f"record does not document '{phrase}'")
    if "no production action" not in low:
        bad("record does not state no production action")

    if "production_executed_true_count=0" not in low:
        bad("record does not document production_executed_true_count=0")
    if re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low):
        bad("production_executed_true_count is non-zero")

    if SECRET_SHAPES.search(text):
        bad("record contains secret-shaped content")
    if PASSWORD_ASSIGN.search(text):
        bad("record contains a stored password assignment")
    if TOKEN_ASSIGN.search(text):
        bad("record contains a stored token/key/secret value")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] operator VISIBLE recorded; Step 65G.2 PASS; fresh E2E resolved; formal evidence")
    print("       OPERATOR_VISIBLE; no new external action; prod_exec=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
