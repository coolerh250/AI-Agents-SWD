#!/usr/bin/env python3
"""Step 66B.3-V -- Operator Validation Record verifier.

Confirms the operator's VISIBLE verdict on the Step 66B.3 RBAC / Audit / Safety
Hardening is recorded with all 10 checklist items, Step 66B.3's final PASS status
is documented, and the no-workflow/no-external/no-production-action posture is
stated.

Marker: STEP66B3_OPERATOR_VALIDATION_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"

DOCS = {
    "validation-record": TEST / "step66b3-operator-validation-record.md",
    "hardening-report": TEST / "step66b3-rbac-audit-safety-hardening-report.md",
    "operator-validation-request": TEST
    / "step66b3-rbac-audit-safety-hardening-operator-validation-request.md",
    "known-gaps": TEST / "step66b3-known-gaps.md",
}

MARKER = "STEP66B3_OPERATOR_VALIDATION_VERIFY"

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

    if "visible" not in record_low:
        bad("operator validation record missing 'VISIBLE'")

    checklist_terms = [
        "/tasks` page",
        "test role simulation banner",
        "current actor / role readout",
        "readable role labels",
        "/tasks/{id}` safety panel",
        "production_effect` warning",
        "dispatch_enabled=false`",
        "production_effect=true` blocked",
        "rbac error readability",
        "production_executed_true_count=0`",
    ]
    for term in checklist_terms:
        if term.lower() not in record_low:
            bad(f"operator validation record missing checklist item: {term}")

    if "step 66b.3 — pass" not in record_low and "step 66b.3 - pass" not in record_low:
        bad("Step 66B.3 final PASS status not documented")
    if "partial_with_gaps" in record_low and "no blocking gaps" not in record_low:
        bad("PARTIAL_WITH_GAPS mentioned without disclaiming it")

    for phrase in (
        "no new workflow was executed",
        "no external action occurred",
        "no production action occurred",
        "production_executed_true_count=0",
    ):
        if phrase not in record_low:
            bad(f"validation record does not state '{phrase}'")

    if "visible" not in texts["hardening-report"].lower():
        bad("hardening-report.md not updated with VISIBLE status")
    if "visible" not in texts["operator-validation-request"].lower():
        bad("operator-validation-request.md not updated")
    if "visible" not in texts["known-gaps"].lower():
        bad("known-gaps.md not updated with operator validation result")

    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] operator validation record present; VISIBLE + 10 checklist items documented;")
    print("       Step 66B.3 final PASS documented; no workflow/external/production action;")
    print("       production_executed_true_count=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
