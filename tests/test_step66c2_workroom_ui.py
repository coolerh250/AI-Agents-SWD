"""Step 66C.2 -- Admin Console Workroom UI (docs + source-structure checks).

The actual UI-behavior tests (page rendering, XSS guardrails, composer/answer-
form validation, RBAC error readability, auth headers) are frontend vitest
tests: apps/admin-console/src/__tests__/WorkroomUI.test.tsx. Run them with
(from apps/admin-console/):
    npm test         # vitest run
    npm run build    # tsc -b && vite build
This Python file follows the repo's tests/test_stepNN_*.py convention: it
confirms the required docs exist with the required content, and that the
frontend source files this stage claims to have added/wired are actually
present -- it does not execute vitest.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"
FRONTEND = ROOT / "apps" / "admin-console" / "src"

DOCS = {
    "ui-report": TEST / "step66c2-workroom-ui-report.md",
    "ui-evidence": TEST / "step66c2-workroom-ui-evidence.md",
    "ui-security-record": TEST / "step66c2-workroom-ui-security-record.md",
    "ui-safety-record": TEST / "step66c2-workroom-ui-safety-record.md",
    "test-deployment-record": TEST / "step66c2-test-deployment-record.md",
    "known-gaps": TEST / "step66c2-known-gaps.md",
    "operator-validation-request": TEST / "step66c2-operator-validation-request.md",
}

CODE = {
    "workroom-page": FRONTEND / "pages" / "TaskWorkroom.tsx",
    "workroom-client": FRONTEND / "tasks" / "workroomClient.ts",
    "workroom-types": FRONTEND / "tasks" / "workroomTypes.ts",
    "task-detail-page": FRONTEND / "pages" / "TaskDetail.tsx",
    "app-router": FRONTEND / "App.tsx",
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


def test_route_and_entry_point_documented() -> None:
    low = _all_low()
    assert "/tasks/{task_id}/workroom" in low or "/tasks/{id}/workroom" in low
    assert "open workroom" in low


def test_plain_text_rendering_documented() -> None:
    low = _all_low()
    assert "plain text" in low
    assert "dangerouslysetinnerhtml" in low


def test_composer_and_clarification_documented() -> None:
    low = _all_low()
    assert "composer" in low or "post a message" in low or "post human message" in low
    assert "clarification" in low
    assert "answer" in low


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
    ovr = DOCS["operator-validation-request"].read_text(encoding="utf-8").lower()
    for token in ("visible", "not_visible", "partial_with_gaps"):
        assert token in ovr, token


def test_no_dangerously_set_inner_html_in_frontend_source() -> None:
    combined = "".join(
        CODE[name].read_text(encoding="utf-8")
        for name in ("workroom-page", "workroom-client", "workroom-types")
    )
    assert "dangerouslySetInnerHTML" not in combined


def test_app_router_has_workroom_route() -> None:
    src = CODE["app-router"].read_text(encoding="utf-8")
    assert 'path="/tasks/:taskId/workroom"' in src


def test_task_detail_has_open_workroom_link() -> None:
    src = CODE["task-detail-page"].read_text(encoding="utf-8")
    assert "open-workroom-link" in src


def test_workroom_client_sends_required_headers() -> None:
    src = CODE["workroom-client"].read_text(encoding="utf-8")
    assert "X-Task-Actor" in src
    assert "X-Task-Role" in src


def test_ui_test_has_xss_guardrails() -> None:
    src = CODE["ui-test"].read_text(encoding="utf-8").lower()
    assert "dangerouslysetinnerhtml" in src
    assert "img src=x onerror" in src


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name
