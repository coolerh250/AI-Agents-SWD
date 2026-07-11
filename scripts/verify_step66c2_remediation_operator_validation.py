#!/usr/bin/env python3
"""Step 66C.2-R-V -- Operator Validation Record verifier.

Confirms the operator validation record documents the VISIBLE response, the
NOT_VISIBLE -> PASS_AFTER_REMEDIATION status history, all 15 checklist items,
that clarification-creation is no longer listed as a gap, that the remaining
gaps are mapped to a future stage, and the required safety/posture
statements.

Marker: STEP66C2_REMEDIATION_OPERATOR_VALIDATION_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"

DOCS = {
    "operator-validation-record": TEST / "step66c2-remediation-operator-validation-record.md",
    "workroom-ui-report": TEST / "step66c2-workroom-ui-report.md",
    "remediation-report": TEST / "step66c2-remediation-report.md",
    "remediation-operator-validation-request": TEST
    / "step66c2-remediation-operator-validation-request.md",
    "known-gaps": TEST / "step66c2-known-gaps.md",
}

MARKER = "STEP66C2_REMEDIATION_OPERATOR_VALIDATION_VERIFY"

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)

CHECKLIST_ITEMS = [
    "workroom page",
    "send message creates a normal workroom message",
    "normal message does not become a clarification automatically",
    "create clarification ui visible",
    "create clarification creates an open clarification",
    "clarification_needed",
    "clarifications section shows the open clarification",
    "answer form visible",
    "answer clarification works",
    "clarification status becomes",
    "answer message appears in the workroom",
    "dispatch_enabled: false",
    "resume_dispatch_enabled: false",
    "production_executed_true_count = 0",
    "plain-text rendering",
]

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
    low = "\n".join(texts.values()).lower()

    record_low = texts["operator-validation-record"].lower()

    if "visible" not in record_low:
        bad("operator VISIBLE response not documented")
    if "not_visible" not in low:
        bad("Step 66C.2 initial NOT_VISIBLE not documented")
    if "pass_after_remediation" not in low:
        bad("Step 66C.2 final PASS_AFTER_REMEDIATION not documented")

    for item in CHECKLIST_ITEMS:
        if item not in record_low:
            bad(f"checklist item not documented: {item}")

    if "no longer a gap" not in record_low and "no longer listed as a gap" not in record_low:
        bad("clarification creation UI no longer being a gap is not documented")

    for gap_id in ("g1", "g2", "g3", "g4", "g5", "g6"):
        if gap_id not in low:
            bad(f"remaining gap {gap_id.upper()} not mapped")
    for target in ("66c.3", "66c.4", "66s", "later"):
        if target not in low:
            bad(f"gap mapping missing target stage: {target}")

    for phrase in (
        "no workflow dispatch",
        "no workflow resume",
        "no external action",
        "no production action",
        "production_executed_true_count=0",
    ):
        if phrase not in low:
            bad(f"docs do not state '{phrase}'")

    # Secret guard.
    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] operator validation record documents VISIBLE response, NOT_VISIBLE -> ")
    print("       PASS_AFTER_REMEDIATION history, all 15 checklist items, clarification-creation")
    print("       no longer a gap, remaining gaps G1-G6 mapped to future stages, and the required")
    print("       safety/posture statements")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
