"""Step 66B.2 -- Admin Console Task Assignment UI (docs + source-structure checks).

The actual UI-behavior tests (page rendering, form validation, API client calls,
production_effect warning, test-role banner, dispatch_enabled=false, error states) are
frontend vitest tests: apps/admin-console/src/__tests__/TaskAssignmentUI.test.tsx and
taskApiGuard.test.ts. Run them with (from apps/admin-console/):
    npm test         # vitest run
    npm run build    # tsc -b && vite build
This Python file follows the repo's tests/test_stepNN_*.py convention: it confirms the
required docs exist with the required content, and that the frontend source files this
stage claims to have added/wired are actually present -- it does not execute vitest.
"""

from __future__ import annotations

import re
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
    "readonly-guard-test": FRONTEND / "__tests__" / "readOnlyGuard.test.ts",
}


def _all_low() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in DOCS.values()).lower()


def test_docs_exist() -> None:
    for name, p in DOCS.items():
        assert p.is_file(), name


def test_frontend_source_exists() -> None:
    for name, p in CODE.items():
        assert p.is_file(), name


def test_routes_documented() -> None:
    low = _all_low()
    assert "/tasks" in low
    assert "/tasks/new" in low
    assert "/tasks/{id}" in low or "/tasks/:taskid" in low.replace(" ", "")


def test_create_and_submit_flow_documented() -> None:
    low = _all_low()
    assert "create draft" in low or "create task" in low
    assert "submit draft" in low or "post /tasks/{id}/submit" in low


def test_test_role_simulation_documented() -> None:
    low = _all_low()
    assert "test role simulation" in low or "test-only role simulation" in low
    assert "not production auth" in low


def test_production_effect_warning_documented() -> None:
    low = _all_low()
    assert "production_effect" in low
    assert "warning" in low


def test_dispatch_enabled_false_documented() -> None:
    low = _all_low()
    assert "dispatch_enabled: false" in low or "dispatch_enabled=false" in low.replace(" ", "")


def test_operator_validation_request_response_options() -> None:
    ovr = DOCS["operator-validation-request"].read_text(encoding="utf-8").lower()
    for token in ("visible", "not_visible", "partial_with_gaps"):
        assert token in ovr, token


def test_posture_statements() -> None:
    low = _all_low()
    for phrase in (
        "no workflow dispatch occurred",
        "no external action occurred",
        "no production action occurred",
        "production_executed_true_count=0",
    ):
        assert phrase in low, phrase


def test_app_router_has_task_routes() -> None:
    src = CODE["app-router"].read_text(encoding="utf-8")
    assert 'path="/tasks"' in src
    assert 'path="/tasks/new"' in src
    assert 'path="/tasks/:taskId"' in src


def test_nav_has_tasks_entry() -> None:
    src = CODE["nav"].read_text(encoding="utf-8")
    assert '"/tasks"' in src


def test_task_client_sends_required_headers() -> None:
    src = CODE["task-client"].read_text(encoding="utf-8")
    assert "X-Task-Actor" in src
    assert "X-Task-Role" in src


def test_readonly_guard_excludes_tasks_module() -> None:
    src = CODE["readonly-guard-test"].read_text(encoding="utf-8")
    assert '"tasks"' in src


def test_no_secret_shapes() -> None:
    shapes = re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
        r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
    )
    for name, p in DOCS.items():
        assert not shapes.search(p.read_text(encoding="utf-8")), name
