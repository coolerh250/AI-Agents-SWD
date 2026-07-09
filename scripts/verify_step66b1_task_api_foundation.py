#!/usr/bin/env python3
"""Step 66B.1 -- Operator Task Assignment API Foundation verifier.

Confirms the task API foundation docs exist and cover the required content (model,
lifecycle enum, the 4 endpoints, RBAC, audit events, production_effect safety, no
dispatch/external/production action, prod_exec=0), and that the source code for the
foundation (migration, shared/sdk/tasks module, task_api.py router) is present.

Marker: STEP66B1_TASK_API_FOUNDATION_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"

DOCS = {
    "foundation-report": TEST / "step66b1-task-api-foundation-report.md",
    "api-evidence": TEST / "step66b1-task-api-evidence.md",
    "rbac-safety-record": TEST / "step66b1-task-rbac-safety-record.md",
    "test-deployment-record": TEST / "step66b1-test-deployment-record.md",
    "known-gaps": TEST / "step66b1-known-gaps.md",
}

CODE = {
    "migration": ROOT / "migrations" / "029_operator_task_api_foundation.sql",
    "models": ROOT / "shared" / "sdk" / "tasks" / "models.py",
    "rbac": ROOT / "shared" / "sdk" / "tasks" / "rbac.py",
    "store": ROOT / "shared" / "sdk" / "tasks" / "store.py",
    "audit_events": ROOT / "shared" / "sdk" / "tasks" / "audit_events.py",
    "safety": ROOT / "shared" / "sdk" / "tasks" / "safety.py",
    "router": ROOT / "apps" / "orchestrator" / "src" / "task_api.py",
    "test": ROOT / "tests" / "test_step66b1_task_api_foundation.py",
}

MARKER = "STEP66B1_TASK_API_FOUNDATION_VERIFY"

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
            bad(f"missing file: {p.relative_to(ROOT)} ({name})")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    low = "\n".join(texts.values()).lower()

    # Task model + lifecycle enum documented.
    if "operator_tasks" not in low:
        bad("task data model (operator_tasks) not documented")
    for state in ("draft", "submitted", "intake_review", "blocked", "canceled"):
        if state not in low:
            bad(f"task lifecycle state not documented: {state}")

    # 4 endpoints documented.
    for ep in ("post /tasks", "get /tasks", "get /tasks/{", "post /tasks/{"):
        if ep not in low:
            bad(f"endpoint not documented: {ep}")

    # RBAC + audit + safety documented.
    if "rbac" not in low:
        bad("RBAC behavior not documented")
    for event in ("task_created", "task_submitted", "task_rejected_by_policy"):
        if event not in low:
            bad(f"audit event not documented: {event}")
    if "production_effect" not in low:
        bad("production_effect safety not documented")

    # Posture statements.
    for phrase in (
        "no admin console task ui implemented",
        "no workflow dispatch occurred",
        "no external action occurred",
        "no production action occurred",
        "production_executed_true_count=0",
    ):
        if phrase not in low:
            bad(f"docs do not state '{phrase}'")

    # Source code sanity: RBAC role set + audit decision types + fail-closed auth.
    rbac_src = CODE["rbac"].read_text(encoding="utf-8")
    for role in (
        "requester",
        "pm_engineering_lead",
        "reviewer_approver",
        "platform_admin",
        "agent_operator",
        "security_compliance_reviewer",
    ):
        if role not in rbac_src:
            bad(f"rbac.py missing role: {role}")

    audit_src = CODE["audit_events"].read_text(encoding="utf-8")
    for const in (
        "DECISION_TASK_CREATED",
        "DECISION_TASK_SUBMITTED",
        "DECISION_TASK_REJECTED_BY_POLICY",
    ):
        if const not in audit_src:
            bad(f"audit_events.py missing constant: {const}")

    router_src = CODE["router"].read_text(encoding="utf-8")
    if "task_api_test_auth_disabled" not in router_src:
        bad("router does not implement fail-closed test-auth gate")
    if "dispatch_enabled" not in router_src:
        bad("router does not return dispatch_enabled (no-dispatch guarantee)")

    migration_src = CODE["migration"].read_text(encoding="utf-8")
    if "production_effect" not in migration_src or "DEFAULT false" not in migration_src:
        bad("migration does not default production_effect to false")

    # Secret guard.
    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] task model + lifecycle enum documented; 4 endpoints documented; RBAC + audit +")
    print("       production_effect safety documented; no dispatch/external/production action;")
    print("       prod_exec=0; source code present (migration, sdk module, router, tests)")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
