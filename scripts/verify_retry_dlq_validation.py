#!/usr/bin/env python3
"""Step 65H.4 -- Retry / DLQ / manual replay validation verifier.

Confirms the 65H.4 records document a real controlled retry/DLQ run: a controlled failure via the
platform's simulate_failure switch, retry-scheduler + DLQ creation, one manual replay, the
retry-count limit (max_retries=3), and terminal failure -- with no external integration, no DB
manipulation, no unsafe stream injection, and no production action (production_executed stays 0).
The operator confirmed VISIBLE-with-gap and flagged that the DLQ has no Admin Console page.

Marker: RETRY_DLQ_VALIDATION_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "retry-dlq-validation-report.md"
EVIDENCE = STAGING / "retry-dlq-evidence.md"
SAFETY = STAGING / "retry-dlq-safety-record.md"
GAPS = STAGING / "retry-dlq-known-gaps.md"
VALIDATION = STAGING / "retry-dlq-operator-validation-request.md"

MARKER = "RETRY_DLQ_VALIDATION_VERIFY"

DOCS = {
    "validation-report": REPORT,
    "evidence": EVIDENCE,
    "safety-record": SAFETY,
    "known-gaps": GAPS,
    "operator-validation-request": VALIDATION,
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


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    for name, p in DOCS.items():
        if not p.is_file():
            bad(f"missing doc: docs/staging/{p.name} ({name})")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    low = "\n".join(texts.values()).lower()

    # Paths validated.
    if "controlled" not in low or "failure" not in low:
        bad("docs do not document the controlled failure")
    if "simulate_failure" not in low:
        bad("docs do not document the platform simulate_failure trigger")
    if "retry" not in low or "scheduler" not in low:
        bad("docs do not document the retry scheduler")
    if "dlq" not in low and "deadletter" not in low and "dead-letter" not in low:
        bad("docs do not document DLQ creation")
    if "manual replay" not in low or "replayed" not in low:
        bad("docs do not document the manual DLQ replay")
    if "terminal failure" not in low or "deadletter.terminal" not in low:
        bad("docs do not document terminal failure")
    if "max_retries=3" not in low and "retry_count" not in low:
        bad("docs do not document the retry-count limit")

    # No unsafe methods.
    if "no unsafe stream injection" not in low and "no db manipulation" not in low:
        bad("docs do not state no DB manipulation / unsafe stream injection")

    # No external / no production.
    if "no external" not in low and "external-write=false" not in low:
        bad("docs do not state no external integration used")
    for phrase in ("no github write", "no discord send", "no llm call", "no production action"):
        if phrase not in low:
            bad(f"docs do not state '{phrase}'")
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

    # Operator confirmed VISIBLE with a flagged UX gap (DLQ has no Admin Console page).
    dlq_ui_gap = "no admin console page" in low or "no dedicated dlq" in low
    if not dlq_ui_gap:
        bad("docs do not record the operator-flagged DLQ-no-Admin-page UX gap")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print(
        "  [OK] controlled failure (simulate_failure) + retry scheduler + DLQ creation + 1 manual"
    )
    print("       replay + retry-count limit + terminal failure validated; no external/injection;")
    print(
        "       no production action; prod_exec=0; operator VISIBLE-with-gap (DLQ has no admin page)"
    )
    print(f"{MARKER}: PASS_WITH_GAPS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
