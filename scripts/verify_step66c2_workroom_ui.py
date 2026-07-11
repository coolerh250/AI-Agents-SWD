#!/usr/bin/env python3
"""Step 66C.2 -- Admin Console Workroom UI verifier.

Confirms the workroom UI docs exist and cover the required content (the
route, task-detail entry point, plain-text rendering, no
dangerouslySetInnerHTML, message composer, clarification display/answer,
dispatch_enabled=false/resume_dispatch_enabled=false), and that the frontend
source (page, client, route/link wiring, guard-covered tests) is present.

Marker: STEP66C2_WORKROOM_UI_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
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
    "task-api-guard-test": FRONTEND / "__tests__" / "taskApiGuard.test.ts",
}

MARKER = "STEP66C2_WORKROOM_UI_VERIFY"

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

    # Route + entry point documented.
    if "/tasks/{task_id}/workroom" not in low and "/tasks/{id}/workroom" not in low:
        bad("/tasks/{id}/workroom route not documented")
    if "open workroom" not in low:
        bad("task detail workroom link not documented")

    # Rendering / security requirements documented.
    if "plain text" not in low:
        bad("plain-text rendering not documented")
    if "dangerouslysetinnerhtml" not in low:
        bad("no dangerouslySetInnerHTML not documented")

    # UI behavior documented.
    if "composer" not in low and "post a message" not in low and "post human message" not in low:
        bad("message composer not documented")
    if "clarification" not in low:
        bad("clarification display not documented")
    if "answer" not in low:
        bad("clarification answer not documented")

    # Safety fields.
    if "dispatch_enabled" not in low or "false" not in low:
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
    ovr = texts["operator-validation-request"].lower()
    for token in ("visible", "not_visible", "partial_with_gaps"):
        if token not in ovr:
            bad(f"operator validation request missing response option: {token}")

    # Frontend source sanity.
    page_src = CODE["workroom-page"].read_text(encoding="utf-8")
    client_src = CODE["workroom-client"].read_text(encoding="utf-8")
    types_src = CODE["workroom-types"].read_text(encoding="utf-8")
    all_frontend_src = page_src + client_src + types_src
    if "dangerouslySetInnerHTML" in all_frontend_src:
        bad("dangerouslySetInnerHTML is used in workroom frontend source -- BLOCKING")

    router_src = CODE["app-router"].read_text(encoding="utf-8")
    if 'path="/tasks/:taskId/workroom"' not in router_src:
        bad("App.tsx missing route declaration: /tasks/:taskId/workroom")

    detail_src = CODE["task-detail-page"].read_text(encoding="utf-8")
    if "open-workroom-link" not in detail_src:
        bad("TaskDetail.tsx missing the Open Workroom link")

    if "X-Task-Actor" not in client_src or "X-Task-Role" not in client_src:
        bad("workroomClient.ts does not send X-Task-Actor/X-Task-Role headers")

    ui_test_src = CODE["ui-test"].read_text(encoding="utf-8")
    if "dangerouslysetinnerhtml" not in ui_test_src.lower():
        bad("WorkroomUI.test.tsx missing an XSS/dangerouslySetInnerHTML guard test")
    if "img src=x onerror" not in ui_test_src.lower():
        bad("WorkroomUI.test.tsx missing a malicious-HTML-renders-as-text test")

    guard_src = CODE["task-api-guard-test"].read_text(encoding="utf-8")
    if "walk(tasks)" not in guard_src.lower().replace(" ", ""):
        bad("taskApiGuard.test.ts no longer walks the whole src/tasks/ directory")

    # Secret guard.
    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] workroom UI docs present; route + task-detail link + plain-text rendering +")
    print("       no dangerouslySetInnerHTML + composer + clarification display/answer +")
    print("       dispatch_enabled/resume_dispatch_enabled=false documented; frontend source")
    print("       (page, client, route/link wiring, XSS guard tests) present; no")
    print("       dispatch/resume/external/production action")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
