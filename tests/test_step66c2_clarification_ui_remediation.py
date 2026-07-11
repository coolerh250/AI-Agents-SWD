"""Step 66C.2-R -- Clarification UI Remediation (docs + source-structure checks).

The actual UI-behavior tests (create-clarification form, RBAC-error
readability, malicious-question/answer rendering) are frontend vitest tests:
apps/admin-console/src/__tests__/WorkroomUI.test.tsx. Run them with (from
apps/admin-console/):
    npm test         # vitest run
    npm run build    # tsc -b && vite build
This Python file follows the repo's tests/test_stepNN_*.py convention: it
confirms the required docs exist with the required content, and that the
frontend source this stage claims to have added/wired is actually present --
it does not execute vitest.
"""

from __future__ import annotations

import re
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


def _all_low() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.values()).lower()


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_frontend_source_exists() -> None:
    for name, p in CODE.items():
        assert p.is_file(), name


def test_operator_not_visible_failure_documented() -> None:
    assert "not_visible" in _all_low()


def test_create_clarification_and_distinction_documented() -> None:
    low = _all_low()
    assert "create clarification" in low
    assert "send message" in low


def test_answer_clarification_documented() -> None:
    assert "answer" in _all_low()


def test_plain_text_and_no_dangerously_set_inner_html_documented() -> None:
    low = _all_low()
    assert "plain text" in low
    assert "dangerouslysetinnerhtml" in low


def test_dispatch_and_resume_flags_documented() -> None:
    low = _all_low()
    assert "dispatch_enabled" in low
    assert "resume_dispatch_enabled" in low


def test_posture_statements() -> None:
    low = _all_low()
    for phrase in (
        "no workflow dispatch occurred",
        "no workflow resume occurred",
        "no external action occurred",
        "no production action occurred",
        "production_executed_true_count=0",
    ):
        assert phrase in low, phrase


def test_operator_validation_request_response_options() -> None:
    ovr = DOCS["remediation-operator-validation-request"].read_text(encoding="utf-8").lower()
    for token in ("visible", "not_visible", "partial_with_gaps"):
        assert token in ovr, token


def test_no_dangerously_set_inner_html_in_frontend_source() -> None:
    combined = "".join(
        CODE[name].read_text(encoding="utf-8") for name in ("workroom-page", "workroom-client")
    )
    assert "dangerouslySetInnerHTML" not in combined


def test_workroom_client_has_create_clarification() -> None:
    src = CODE["workroom-client"].read_text(encoding="utf-8")
    assert "createClarification" in src
    assert "/clarifications" in src


def test_workroom_page_has_create_clarification_form() -> None:
    src = CODE["workroom-page"].read_text(encoding="utf-8")
    assert "Create Clarification" in src
    assert "Send Message" in src


def test_ui_test_covers_create_clarification_and_rbac_error() -> None:
    src = CODE["ui-test"].read_text(encoding="utf-8")
    assert "workroom-create-clarification" in src
    assert "role_cannot_create_clarification" in src


def test_ui_test_covers_malicious_question_and_answer() -> None:
    src = CODE["ui-test"].read_text(encoding="utf-8").lower()
    assert "malicious-looking clarification question" in src
    assert "malicious-looking clarification answer" in src


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name
