#!/usr/bin/env python3
"""Step 66B.2-V -- Operator UI Validation Record verifier.

Confirms the operator's VISIBLE verdict on the Step 66B.2 Admin Console Task
Assignment UI is recorded with all 10 checklist items, the "Create Task" label
note is documented as a non-blocking difference, Step 66B.2's final PASS status
is documented, and the safety/posture statements are present.

Marker: STEP66B2_OPERATOR_UI_VALIDATION_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"

DOCS = {
    "validation-record": TEST / "step66b2-operator-ui-validation-record.md",
    "ui-report": TEST / "step66b2-task-assignment-ui-report.md",
    "operator-validation-request": TEST
    / "step66b2-task-assignment-ui-operator-validation-request.md",
    "known-gaps": TEST / "step66b2-known-gaps.md",
}

MARKER = "STEP66B2_OPERATOR_UI_VALIDATION_VERIFY"

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    for name, p in DOCS.items():
        if not p.is_file():
            bad(f"missing file: {p} ({name})")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    record_low = texts["validation-record"].lower()

    # Operator response VISIBLE documented.
    if "visible" not in record_low:
        bad("operator validation record missing 'VISIBLE'")

    # 10 checklist items documented.
    checklist_terms = [
        "/tasks` page",
        "test role simulation banner",
        "create task page",
        "production_effect=false` task creation",
        "created task appears in list",
        "task detail opens",
        "submit draft works",
        "intake_review",
        "dispatch_enabled: false` visible",
        "production_effect=true` warning",
    ]
    for term in checklist_terms:
        if term.lower() not in record_low:
            bad(f"operator validation record missing checklist item: {term}")

    # Create Task label documented as non-gap.
    if '"create task"' not in record_low:
        bad("'Create Task' label note not documented")
    if "not a functional gap" not in record_low and "not a gap" not in record_low:
        bad("'Create Task' label note not documented as non-blocking")

    # Step 66B.2 final PASS documented.
    if "step 66b.2 — pass" not in record_low and "step 66b.2 - pass" not in record_low:
        bad("Step 66B.2 final PASS status not documented")
    if "partial_with_gaps" in record_low and "not classified as" not in record_low:
        bad("PARTIAL_WITH_GAPS mentioned without disclaiming it")

    # Safety / posture statements.
    for phrase in (
        "no new workflow was executed",
        "no external action occurred",
        "no production action occurred",
        "production_executed_true_count=0",
    ):
        if phrase not in record_low:
            bad(f"validation record does not state '{phrase}'")

    # Cross-doc consistency: report + request + known-gaps updated.
    if "visible" not in texts["ui-report"].lower():
        bad("ui-report.md not updated with VISIBLE status")
    if "visible" not in texts["operator-validation-request"].lower():
        bad("operator-validation-request.md not updated")
    if "create task" not in texts["known-gaps"].lower():
        bad("known-gaps.md not updated with the Create Task label note")

    # Secret guard.
    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] operator validation record present; VISIBLE + 10 checklist items documented;")
    print("       'Create Task' label recorded as non-blocking; Step 66B.2 final PASS documented;")
    print("       no workflow/external/production action; production_executed_true_count=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
