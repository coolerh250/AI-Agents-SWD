#!/usr/bin/env python3
"""Step 66C.1-V -- Operator API Validation Record verifier.

Confirms the operator's READY_WITH_GAPS verdict on the Step 66C.1 Agent
Workroom & Clarification Data/API Foundation is recorded, Step 66C.1's final
PASS status is documented, the validated capabilities and G1-G5 gaps are
documented, the future-step mapping to 66C.2/66C.3/66C.4/66S is documented,
and the no-workflow/no-resume/no-external/no-production posture is stated.

Marker: STEP66C1_OPERATOR_API_VALIDATION_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"

DOCS = {
    "validation-record": TEST / "step66c1-operator-api-validation-record.md",
    "foundation-report": TEST / "step66c1-workroom-clarification-api-foundation-report.md",
    "operator-validation-request": TEST / "step66c1-operator-validation-request.md",
    "known-gaps": TEST / "step66c1-known-gaps.md",
    "implementation-sequence": TEST / "ai-team-work-step66-implementation-sequence.md",
    "risk-register": TEST / "ai-team-work-risk-register.md",
}

MARKER = "STEP66C1_OPERATOR_API_VALIDATION_VERIFY"

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

    if "ready_with_gaps" not in record_low:
        bad("operator validation record missing 'READY_WITH_GAPS'")

    if "step 66c.1 — pass" not in record_low and "step 66c.1 - pass" not in record_low:
        bad("Step 66C.1 final PASS status not documented")

    # Validated capabilities (spot-check a representative subset).
    for term in (
        "task_messages` model added",
        "operator_clarification_requests` model added",
        "get /tasks/{id}/workroom` works",
        "post /tasks/{id}/workroom/messages` works",
        "post /tasks/{id}/clarifications` works",
        "clarifications/{id}/answer` works",
        "clarification_needed",
        "answered",
        "intake_review",
        "dispatch_enabled=false",
        "resume_dispatch_enabled=false",
    ):
        if term.lower() not in record_low:
            bad(f"validated capability not documented: {term}")

    # G1-G5 gaps.
    for gap in ("g1", "g2", "g3", "g4", "g5"):
        if gap not in record_low:
            bad(f"gap not documented: {gap}")
    for phrase in (
        "message visibility filtering",
        "reminder / expiry scheduler",
        "audit lookup",
        "project/team rbac scoping",
        "answered-twice guard",
    ):
        if phrase not in record_low:
            bad(f"gap description not documented: {phrase}")

    # Future-step mapping.
    for stage in ("66c.2", "66c.3", "66c.4", "66s"):
        if stage not in record_low:
            bad(f"future-step mapping missing stage: {stage}")

    # Posture statements.
    for phrase in (
        "no new workflow was executed",
        "no external action occurred",
        "no production action occurred",
        "production_executed_true_count=0",
    ):
        if phrase not in record_low:
            bad(f"validation record does not state '{phrase}'")

    # Cross-doc updates.
    if "ready_with_gaps" not in texts["foundation-report"].lower():
        bad("foundation-report.md not updated with READY_WITH_GAPS")
    if "ready_with_gaps" not in texts["operator-validation-request"].lower():
        bad("operator-validation-request.md not updated")
    if "g1" not in texts["known-gaps"].lower() or "g5" not in texts["known-gaps"].lower():
        bad("known-gaps.md not updated with G1-G5 gap IDs")
    for stage in ("66c.2", "66c.3", "66c.4", "66s"):
        if stage not in texts["implementation-sequence"].lower():
            bad(f"implementation-sequence.md missing stage: {stage}")
    if (
        "g1" not in texts["risk-register"].lower()
        and "ready_with_gaps" not in texts["risk-register"].lower()
    ):
        bad("risk-register.md not updated with gap tracking")

    # Secret guard.
    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] operator API validation record present; READY_WITH_GAPS + validated")
    print("       capabilities + G1-G5 gaps documented; future-step mapping to")
    print("       66C.2/66C.3/66C.4/66S documented; Step 66C.1 final PASS documented; no")
    print("       workflow/resume/external/production action; production_executed_true_count=0")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
