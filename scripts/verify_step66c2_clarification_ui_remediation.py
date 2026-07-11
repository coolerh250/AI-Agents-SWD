#!/usr/bin/env python3
"""Step 66C.2-R -- Clarification UI Remediation verifier.

Confirms the remediation docs exist and document the operator NOT_VISIBLE
failure, the create-clarification UI, the message-vs-clarification
distinction, the answer-clarification UI, the required security/safety
statements, and that the frontend source (client method, page form, XSS
guard tests) is actually present.

Marker: STEP66C2_CLARIFICATION_UI_REMEDIATION_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"
FRONTEND = ROOT / "apps" / "admin-console" / "src"

DOCS = {
    "remediation-report": TEST / "step66c2-remediation-report.md",
    "clarification-ui-evidence": TEST / "step66c2-clarification-ui-evidence.md",
    "remediation-safety-record": TEST / "step66c2-remediation-safety-record.md",
    "remediation-operator-validation-request": TEST
    / "step66c2-remediation-operator-validation-request.md",
    "workroom-ui-report": TEST / "step66c2-workroom-ui-report.md",
    "known-gaps": TEST / "step66c2-known-gaps.md",
}

CODE = {
    "workroom-page": FRONTEND / "pages" / "TaskWorkroom.tsx",
    "workroom-client": FRONTEND / "tasks" / "workroomClient.ts",
    "ui-test": FRONTEND / "__tests__" / "WorkroomUI.test.tsx",
}

MARKER = "STEP66C2_CLARIFICATION_UI_REMEDIATION_VERIFY"

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    for name, p in {**DOCS, **CODE}.items():
        if not p.is_file():
            bad(f"missing file: {p} ({name})")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    low = "\n".join(texts.values()).lower()

    # Operator failure documented.
    if "not_visible" not in low:
        bad("operator NOT_VISIBLE failure not documented")

    # Remediation content documented.
    if "create clarification" not in low:
        bad("create clarification UI not documented")
    if "send message" not in low:
        bad("normal message vs clarification distinction not documented")
    if "answer" not in low:
        bad("answer clarification UI not documented")

    # Rendering / security requirements documented.
    if "plain text" not in low:
        bad("plain-text rendering not documented")
    if "dangerouslysetinnerhtml" not in low:
        bad("no dangerouslySetInnerHTML not documented")

    # Safety fields.
    if "dispatch_enabled" not in low:
        bad("dispatch_enabled=false not documented")
    if "resume_dispatch_enabled" not in low:
        bad("resume_dispatch_enabled=false not documented")

    # Posture statements.
    for phrase in (
        "no workflow dispatch occurred",
        "no workflow resume occurred",
        "no external action occurred",
        "no production action occurred",
        "production_executed_true_count=0",
    ):
        if phrase not in low:
            bad(f"docs do not state '{phrase}'")

    # Operator validation request response options.
    ovr = texts["remediation-operator-validation-request"].lower()
    for token in ("visible", "not_visible", "partial_with_gaps"):
        if token not in ovr:
            bad(f"operator validation request missing response option: {token}")

    # Frontend source sanity.
    page_src = CODE["workroom-page"].read_text(encoding="utf-8")
    client_src = CODE["workroom-client"].read_text(encoding="utf-8")
    if "dangerouslySetInnerHTML" in page_src or "dangerouslySetInnerHTML" in client_src:
        bad("dangerouslySetInnerHTML is used in workroom frontend source -- BLOCKING")

    if "createClarification" not in client_src:
        bad("workroomClient.ts missing createClarification()")
    if "/clarifications" not in client_src:
        bad("workroomClient.ts createClarification() does not call /clarifications")

    if "CreateClarificationForm" not in page_src and "Create Clarification" not in page_src:
        bad("TaskWorkroom.tsx missing a Create Clarification UI element")
    if "Send Message" not in page_src:
        bad("TaskWorkroom.tsx composer not relabeled to distinguish it from Create Clarification")

    ui_test_src = CODE["ui-test"].read_text(encoding="utf-8")
    if "workroom-create-clarification" not in ui_test_src:
        bad("WorkroomUI.test.tsx missing create-clarification test coverage")
    if "role_cannot_create_clarification" not in ui_test_src:
        bad("WorkroomUI.test.tsx missing an RBAC-error-readability test for create-clarification")
    ui_test_low = ui_test_src.lower()
    if "malicious-looking clarification question" not in ui_test_low:
        bad("WorkroomUI.test.tsx missing a malicious clarification-question rendering test")
    if "malicious-looking clarification answer" not in ui_test_low:
        bad("WorkroomUI.test.tsx missing a malicious clarification-answer rendering test")

    # Secret guard.
    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print(
        "  [OK] remediation docs present; operator NOT_VISIBLE failure + create-clarification UI +"
    )
    print("       message-vs-clarification distinction + answer UI + plain-text rendering + no")
    print("       dangerouslySetInnerHTML + dispatch/resume=false + safety posture documented;")
    print("       frontend source (createClarification() client method, Create Clarification form,")
    print("       RBAC-error test, malicious-text tests) present")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
