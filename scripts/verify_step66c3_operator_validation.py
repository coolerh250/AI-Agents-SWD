#!/usr/bin/env python3
"""Step 66C.3-V -- Operator Validation Record verifier.

Confirms the operator validation record documents the VISIBLE response, all
12 checklist items, G1/G3/G5 fixed status, the remaining deferred gaps
(G2/G4/G6/pagination/client-hidden RBAC), and the required safety/posture
statements.

Marker: STEP66C3_OPERATOR_VALIDATION_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"

DOCS = {
    "operator-validation-record": TEST / "step66c3-operator-validation-record.md",
    "hardening-report": TEST / "step66c3-workroom-audit-visibility-hardening-report.md",
    "operator-validation-request": TEST / "step66c3-operator-validation-request.md",
    "known-gaps": TEST / "step66c3-known-gaps.md",
}

MARKER = "STEP66C3_OPERATOR_VALIDATION_VERIFY"

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)

CHECKLIST_ITEMS = [
    "workroom visible",
    "visibility note visible",
    "audit evidence section visible",
    "allowed role can view safe audit evidence",
    "restricted role gets a readable restricted message",
    "does not expose raw message body",
    "does not expose raw clarification answer",
    "second answer attempt is blocked",
    "clarification_already_answered",
    "dispatch_enabled: false",
    "resume_dispatch_enabled: false",
    "production_executed_true_count = 0",
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
    low = re.sub(r"\s+", " ", "\n".join(texts.values()).lower())
    record_low = re.sub(r"\s+", " ", texts["operator-validation-record"].lower())

    if "visible" not in record_low:
        bad("operator VISIBLE response not documented")
    if "pass, operator visible" not in low and "pass" not in low:
        bad("Step 66C.3 final PASS status not documented")

    for item in CHECKLIST_ITEMS:
        if item not in record_low:
            bad(f"checklist item not documented: {item}")

    for gap_id in ("g1", "g3", "g5"):
        if gap_id not in record_low:
            bad(f"fixed gap {gap_id.upper()} not documented in the validation record")
    if "fixed" not in record_low:
        bad("gap-fixed status wording not found")

    for gap_id in ("g2", "g4", "g6"):
        if gap_id not in low:
            bad(f"remaining gap {gap_id.upper()} not mapped")
    for target in ("66c.4", "66s", "later"):
        if target not in low:
            bad(f"gap mapping missing target: {target}")
    if "pagination" not in low:
        bad("audit evidence pagination deferral not documented")
    if "client-hidden rbac" not in low:
        bad("client-hidden RBAC improvements deferral not documented")

    for phrase in (
        "no workflow dispatch",
        "no workflow resume",
        "no external action",
        "no production action",
        "production_executed_true_count=0",
    ):
        if phrase not in low:
            bad(f"docs do not state '{phrase}'")

    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] operator validation record documents VISIBLE response, all 12 checklist items,")
    print("       G1/G3/G5 fixed, remaining gaps (G2/G4/G6/pagination/client-hidden RBAC) mapped,")
    print("       and the required safety/posture statements")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
