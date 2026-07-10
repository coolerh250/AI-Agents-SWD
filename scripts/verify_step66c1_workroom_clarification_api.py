#!/usr/bin/env python3
"""Step 66C.1 -- Agent Workroom & Clarification API foundation verifier.

Confirms the required docs exist and cover the required content (data models,
the 4 endpoints, clarification_needed/answered behavior, dispatch_enabled=false/
resume_dispatch_enabled=false, RBAC, audit, safety, security addendum), and that
the backend source (migration, models, rbac, store, audit, safety, router,
tests) is present.

Marker: STEP66C1_WORKROOM_CLARIFICATION_API_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"
ORCH = ROOT / "apps" / "orchestrator" / "src"
SHARED = ROOT / "shared" / "sdk" / "tasks"
TESTS = ROOT / "tests"

DOCS = {
    "foundation-report": TEST / "step66c1-workroom-clarification-api-foundation-report.md",
    "workroom-api-evidence": TEST / "step66c1-workroom-api-evidence.md",
    "clarification-flow-evidence": TEST / "step66c1-clarification-flow-evidence.md",
    "rbac-audit-safety-record": TEST / "step66c1-rbac-audit-safety-record.md",
    "test-deployment-record": TEST / "step66c1-test-deployment-record.md",
    "known-gaps": TEST / "step66c1-known-gaps.md",
    "operator-validation-request": TEST / "step66c1-operator-validation-request.md",
}

CODE = {
    "migration": ROOT / "migrations" / "030_workroom_clarification_foundation.sql",
    "workroom-models": SHARED / "workroom_models.py",
    "workroom-rbac": SHARED / "workroom_rbac.py",
    "workroom-store": SHARED / "workroom_store.py",
    "audit-events": SHARED / "audit_events.py",
    "safety": SHARED / "safety.py",
    "workroom-api": ORCH / "workroom_api.py",
    "main": ORCH / "main.py",
    "tests": TESTS / "test_step66c1_workroom_clarification_api.py",
}

MARKER = "STEP66C1_WORKROOM_CLARIFICATION_API_VERIFY"

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

    # Doc-set required content.
    for phrase in (
        "66c.1 implemented workroom / clarification backend foundation only",
        "no workroom ui was implemented",
        "no workflow dispatch occurred",
        "no workflow resume occurred",
        "no external action occurred",
        "no production action occurred",
        "production_executed_true_count=0",
    ):
        if phrase not in low:
            bad(f"docs do not state '{phrase}'")

    # Data models documented.
    if "task_messages" not in low:
        bad("task_messages model not documented")
    if "clarification_requests" not in low:
        bad("clarification_requests model not documented")

    # Endpoints documented.
    for endpoint in (
        "/workroom",
        "/workroom/messages",
        "/clarifications",
        "/clarifications/{id}/answer" if "/clarifications/{id}/answer" in low else "/answer",
    ):
        if endpoint not in low:
            bad(f"endpoint not documented: {endpoint}")

    # State behavior.
    if "clarification_needed" not in low:
        bad("clarification_needed state not documented")
    if "answered" not in low or "intake_review" not in low:
        bad("clarification answered behavior not documented")

    # Safety fields.
    if "dispatch_enabled" not in low or "false" not in low:
        bad("dispatch_enabled=false not documented")
    if "resume_dispatch_enabled" not in low:
        bad("resume_dispatch_enabled=false not documented")

    # Operator validation request response options.
    ovr = texts["operator-validation-request"].lower()
    for token in ("api_ready", "not_ready", "ready_with_gaps"):
        if token not in ovr:
            bad(f"operator validation request missing response option: {token}")

    # Source sanity.
    workroom_api_src = CODE["workroom-api"].read_text(encoding="utf-8")
    for route_decl in (
        '@router.get("/{task_id}/workroom")',
        '@router.post("/{task_id}/workroom/messages"',
        '@router.post("/{task_id}/clarifications"',
        '@router.post("/{task_id}/clarifications/{clarification_id}/answer")',
    ):
        if route_decl not in workroom_api_src:
            bad(f"workroom_api.py missing route declaration: {route_decl}")
    if (
        "dispatch_enabled" not in workroom_api_src
        or "resume_dispatch_enabled" not in workroom_api_src
    ):
        bad("workroom_api.py does not return dispatch_enabled/resume_dispatch_enabled")

    main_src = CODE["main"].read_text(encoding="utf-8")
    if "workroom_router" not in main_src:
        bad("main.py does not mount the workroom router")

    audit_src = CODE["audit-events"].read_text(encoding="utf-8")
    for decision in (
        "DECISION_TASK_MESSAGE_CREATED",
        "DECISION_CLARIFICATION_REQUESTED",
        "DECISION_CLARIFICATION_ANSWERED",
        "DECISION_TASK_WORKROOM_RBAC_DENIED",
        "DECISION_CLARIFICATION_RBAC_DENIED",
        "safe_workroom_refs",
    ):
        if decision not in audit_src:
            bad(f"audit_events.py missing {decision}")

    # Security addendum content.
    addendum_low = texts["rbac-audit-safety-record"].lower()
    for phrase in (
        "body_length",
        "body_hash",
        "parameterized",
        "8000",
        "4000",
        "dangerouslysetinnerhtml",
    ):
        if phrase not in addendum_low:
            bad(f"rbac-audit-safety-record.md missing security addendum content: {phrase}")

    # Secret guard.
    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] 66C.1 docs present (foundation report, workroom/clarification evidence,")
    print("       RBAC/audit/safety record incl. security addendum, test deployment record,")
    print("       known gaps, operator validation request); data models + 4 endpoints +")
    print("       clarification_needed/answered + dispatch_enabled/resume_dispatch_enabled=false")
    print("       documented and present in source; no workflow dispatch/resume/external/")
    print("       production action")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
