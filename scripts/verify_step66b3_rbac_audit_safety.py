#!/usr/bin/env python3
"""Step 66B.3 -- RBAC / Audit / Safety Hardening verifier.

Confirms the 66B.3 hardening docs exist and cover the required content: RBAC
fail-closed behavior (missing/invalid role), Requester own-task scoping,
production_effect=true blocked, dispatch_enabled=false, audit evidence,
test-only auth boundary, and the real identity/session/CSRF future gap. Also
confirms the backend/frontend source hardening (task_rbac_denied audit event,
readable role labels, safety panel) is present.

Marker: STEP66B3_RBAC_AUDIT_SAFETY_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"
ORCH = ROOT / "apps" / "orchestrator" / "src"
FRONTEND = ROOT / "apps" / "admin-console" / "src"
SHARED = ROOT / "shared" / "sdk" / "tasks"

DOCS = {
    "hardening-report": TEST / "step66b3-rbac-audit-safety-hardening-report.md",
    "rbac-validation-evidence": TEST / "step66b3-rbac-validation-evidence.md",
    "audit-evidence-record": TEST / "step66b3-audit-evidence-record.md",
    "safety-validation-record": TEST / "step66b3-safety-validation-record.md",
    "test-deployment-record": TEST / "step66b3-test-deployment-record.md",
    "known-gaps": TEST / "step66b3-known-gaps.md",
}

CODE = {
    "task-api": ORCH / "task_api.py",
    "audit-events": SHARED / "audit_events.py",
    "test-role": FRONTEND / "tasks" / "testRole.ts",
    "test-role-banner": FRONTEND / "tasks" / "TestRoleBanner.tsx",
    "task-detail-page": FRONTEND / "pages" / "TaskDetail.tsx",
}

MARKER = "STEP66B3_RBAC_AUDIT_SAFETY_VERIFY"

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)

failures: list[str] = []
gaps: list[str] = []


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

    # Doc-set required content (per stage docs' "Docs must state" list).
    for phrase in (
        "66b.3 hardened rbac / audit / safety only",
        "no workflow dispatch occurred",
        "no external action occurred",
        "no production action occurred",
        "production_executed_true_count=0",
        "test-only role simulation is not production auth",
        "real identity/session/csrf remains future work",
    ):
        if phrase not in low:
            bad(f"docs do not state '{phrase}'")

    # RBAC behavior documented.
    if "requester" not in low or ("own task" not in low and "own-task" not in low):
        bad("Requester own-task rule not documented")
    if "not_own_task" not in low or "other actor" not in low:
        bad("Requester cannot view other actor's task not documented")
    if "missing_role" not in low or "invalid_role" not in low:
        bad("invalid/missing role fail-closed behavior not documented")
    if "production_effect=true" not in low or "blocked" not in low:
        bad("production_effect=true blocked behavior not documented")
    if "dispatch_enabled" not in low or "false" not in low:
        bad("dispatch_enabled=false not documented")
    if "task_rbac_denied" not in low:
        bad("task_rbac_denied audit event not documented")
    if "task_api_test_auth_enabled" not in low and "test-only auth" not in low:
        bad("test-only auth boundary not documented")

    # Real identity/session/CSRF future gap.
    if "identity" not in low or "csrf" not in low:
        bad("real identity/session/CSRF future gap not documented")

    # Source hardening checks.
    task_api_src = CODE["task-api"].read_text(encoding="utf-8")
    if "missing_role" not in task_api_src:
        bad("task_api.py missing distinct missing_role handling")
    if "_deny(" not in task_api_src or "DECISION_TASK_RBAC_DENIED" not in task_api_src:
        bad("task_api.py missing _deny()/task_rbac_denied wiring")
    if '"dispatch_enabled": False' not in task_api_src.replace("'", '"'):
        bad("task_api.py get_task does not return dispatch_enabled")

    audit_src = CODE["audit-events"].read_text(encoding="utf-8")
    if "DECISION_TASK_RBAC_DENIED" not in audit_src:
        bad("audit_events.py missing DECISION_TASK_RBAC_DENIED")

    test_role_src = CODE["test-role"].read_text(encoding="utf-8")
    if "TASK_ROLE_LABELS" not in test_role_src:
        bad("testRole.ts missing TASK_ROLE_LABELS (readable role names)")

    banner_src = CODE["test-role-banner"].read_text(encoding="utf-8")
    if "current-identity" not in banner_src:
        bad("TestRoleBanner.tsx missing current-identity readout")

    detail_src = CODE["task-detail-page"].read_text(encoding="utf-8")
    if "safety-panel" not in detail_src:
        bad("TaskDetail.tsx missing safety-panel")

    # Secret guard.
    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] 66B.3 hardening docs present (report, RBAC/audit/safety validation records,")
    print("       test deployment record, known gaps); Requester own-task + cross-actor denial +")
    print("       missing/invalid role fail-closed + production_effect=true blocked +")
    print("       dispatch_enabled=false + task_rbac_denied audit documented; test-only auth")
    print("       boundary + real identity/session/CSRF future gap documented; backend/frontend")
    print("       hardening source present; no workflow/external/production action")
    if gaps:
        print(f"{MARKER}: PASS_WITH_GAPS")
        return 0
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
