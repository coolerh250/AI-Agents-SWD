#!/usr/bin/env python3
"""Step 66B.2 -- Admin Console Task Assignment UI verifier.

Confirms the task assignment UI docs exist and cover the required content (the 3
routes, create/submit flow, test-only role simulation, production_effect warning,
dispatch_enabled=false, operator validation request), and that the frontend source
(pages, tasks module, guard test, route/nav wiring) is present.

Marker: STEP66B2_TASK_ASSIGNMENT_UI_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"
FRONTEND = ROOT / "apps" / "admin-console" / "src"

DOCS = {
    "ui-report": TEST / "step66b2-task-assignment-ui-report.md",
    "ui-evidence": TEST / "step66b2-task-assignment-ui-evidence.md",
    "ui-safety-record": TEST / "step66b2-task-assignment-ui-safety-record.md",
    "operator-validation-request": TEST
    / "step66b2-task-assignment-ui-operator-validation-request.md",
    "known-gaps": TEST / "step66b2-known-gaps.md",
}

CODE = {
    "task-list-page": FRONTEND / "pages" / "TaskList.tsx",
    "task-new-page": FRONTEND / "pages" / "TaskNew.tsx",
    "task-detail-page": FRONTEND / "pages" / "TaskDetail.tsx",
    "task-client": FRONTEND / "tasks" / "taskClient.ts",
    "task-types": FRONTEND / "tasks" / "taskTypes.ts",
    "test-role": FRONTEND / "tasks" / "testRole.ts",
    "test-role-banner": FRONTEND / "tasks" / "TestRoleBanner.tsx",
    "task-api-guard-test": FRONTEND / "__tests__" / "taskApiGuard.test.ts",
    "ui-behavior-test": FRONTEND / "__tests__" / "TaskAssignmentUI.test.tsx",
    "app-router": FRONTEND / "App.tsx",
    "nav": FRONTEND / "components" / "Nav.tsx",
}

MARKER = "STEP66B2_TASK_ASSIGNMENT_UI_VERIFY"

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

    # Routes documented.
    if "/tasks" not in low:
        bad("/tasks route not documented")
    if "/tasks/new" not in low:
        bad("/tasks/new route not documented")
    if "/tasks/{id}" not in low and "/tasks/:taskid" not in low.replace(" ", ""):
        bad("/tasks/{id} route not documented")

    # Create + submit flow documented.
    if "create draft" not in low and "create task" not in low:
        bad("task create flow not documented")
    if "submit draft" not in low and "post /tasks/{id}/submit" not in low:
        bad("task submit flow not documented")

    # Test-only role simulation + production_effect warning + dispatch_enabled.
    if "test role simulation" not in low and "test-only role simulation" not in low:
        bad("test-only role simulation not documented")
    if "production_effect" not in low or "warning" not in low:
        bad("production_effect warning not documented")
    if "dispatch_enabled: false" not in low and "dispatch_enabled=false" not in low.replace(
        " ", ""
    ):
        bad("dispatch_enabled=false not documented")

    # Operator validation request exists + has the 3-way response options.
    ovr = texts["operator-validation-request"].lower()
    for token in ("visible", "not_visible", "partial_with_gaps"):
        if token not in ovr:
            bad(f"operator validation request missing response option: {token}")

    # Posture statements.
    for phrase in (
        "no workflow dispatch occurred",
        "no external action occurred",
        "no production action occurred",
        "production_executed_true_count=0",
        "not production auth",
    ):
        if phrase not in low:
            bad(f"docs do not state '{phrase}'")

    # Frontend source sanity.
    router_src = CODE["app-router"].read_text(encoding="utf-8")
    for route_decl in (
        'path="/tasks"',
        'path="/tasks/new"',
        'path="/tasks/:taskId"',
    ):
        if route_decl not in router_src:
            bad(f"App.tsx missing route declaration: {route_decl}")

    nav_src = CODE["nav"].read_text(encoding="utf-8")
    if '"/tasks"' not in nav_src:
        bad("Nav.tsx missing /tasks nav entry")

    client_src = CODE["task-client"].read_text(encoding="utf-8")
    if "X-Task-Actor" not in client_src or "X-Task-Role" not in client_src:
        bad("taskClient.ts does not send X-Task-Actor/X-Task-Role headers")

    ro_guard = (FRONTEND / "__tests__" / "readOnlyGuard.test.ts").read_text(encoding="utf-8")
    if '"tasks"' not in ro_guard:
        bad("readOnlyGuard.test.ts does not exclude the tasks/ module")

    # Secret guard.
    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] task assignment UI docs present; 3 routes + create/submit flow documented;")
    print("       test-only role simulation + production_effect warning + dispatch_enabled=false")
    print("       documented; operator validation request present; frontend source (pages, tasks")
    print("       module, guard test, route/nav wiring) present; no dispatch/external/prod action")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
