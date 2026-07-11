#!/usr/bin/env python3
"""Step 66C.3 -- Workroom Audit / Visibility / Edge-case Hardening verifier.

Confirms the 9 required docs exist and document G1 (message visibility
filtering) / G3 (task-scoped audit evidence endpoint) / G5 (answered-twice
guard) status, audit privacy (no raw body), and the required safety/posture
statements. Also does light frontend/backend source sanity checks.

Marker: STEP66C3_WORKROOM_AUDIT_VISIBILITY_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"
ORCH = ROOT / "apps" / "orchestrator" / "src"
SHARED = ROOT / "shared" / "sdk" / "tasks"
FRONTEND = ROOT / "apps" / "admin-console" / "src"

DOCS = {
    "hardening-report": TEST / "step66c3-workroom-audit-visibility-hardening-report.md",
    "message-visibility-evidence": TEST / "step66c3-message-visibility-evidence.md",
    "task-audit-evidence-endpoint-record": TEST / "step66c3-task-audit-evidence-endpoint-record.md",
    "answered-twice-guard-record": TEST / "step66c3-answered-twice-guard-record.md",
    "security-record": TEST / "step66c3-security-record.md",
    "safety-record": TEST / "step66c3-safety-record.md",
    "test-deployment-record": TEST / "step66c3-test-deployment-record.md",
    "known-gaps": TEST / "step66c3-known-gaps.md",
    "operator-validation-request": TEST / "step66c3-operator-validation-request.md",
}

CODE = {
    "workroom-api": ORCH / "workroom_api.py",
    "workroom-rbac": SHARED / "workroom_rbac.py",
    "workroom-store": SHARED / "workroom_store.py",
    "workroom-page": FRONTEND / "pages" / "TaskWorkroom.tsx",
    "workroom-client": FRONTEND / "tasks" / "workroomClient.ts",
}

MARKER = "STEP66C3_WORKROOM_AUDIT_VISIBILITY_VERIFY"

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

    # G1/G3/G5 status documented.
    if "g1" not in low or "visibility filtering" not in low:
        bad("G1 (message visibility filtering) status not documented")
    if "g3" not in low or "audit evidence" not in low:
        bad("G3 (task audit evidence endpoint) status not documented")
    if "g5" not in low or "answered-twice" not in low:
        bad("G5 (answered-twice guard) status not documented")

    # Audit privacy documented.
    if "no raw message body" not in low:
        bad("audit privacy (no raw message body) not documented")
    if "raw clarification answer" not in low:
        bad("audit privacy (no raw clarification answer) not documented")

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

    # Backend source sanity.
    api_src = CODE["workroom-api"].read_text(encoding="utf-8")
    rbac_src = CODE["workroom-rbac"].read_text(encoding="utf-8")
    store_src = CODE["workroom-store"].read_text(encoding="utf-8")

    if "audit-evidence" not in api_src:
        bad("workroom_api.py missing the /audit-evidence route")
    if "filter_messages_by_visibility" not in api_src:
        bad("workroom_api.py does not apply filter_messages_by_visibility in get_workroom")
    if "claim_clarification_answer" not in api_src or "claim_clarification_answer" not in store_src:
        bad("answer_clarification is not using an atomic claim_clarification_answer store method")
    if "clarification_already_answered" not in api_src:
        bad("workroom_api.py missing the clarification_already_answered error code")
    if "_VISIBILITY_ROLES" not in rbac_src:
        bad("workroom_rbac.py missing the visibility-role matrix")
    if "_AUDIT_EVIDENCE_ROLES" not in rbac_src:
        bad("workroom_rbac.py missing the audit-evidence RBAC role set")
    if "WHERE id=$1 AND status='open'" not in store_src:
        bad("workroom_store.py claim is not atomic (missing WHERE ... AND status='open')")

    # Frontend source sanity.
    page_src = CODE["workroom-page"].read_text(encoding="utf-8")
    client_src = CODE["workroom-client"].read_text(encoding="utf-8")
    if "dangerouslySetInnerHTML" in page_src or "dangerouslySetInnerHTML" in client_src:
        bad("dangerouslySetInnerHTML is used in workroom frontend source -- BLOCKING")
    if "getAuditEvidence" not in client_src:
        bad("workroomClient.ts missing getAuditEvidence()")
    if "AuditEvidenceSection" not in page_src:
        bad("TaskWorkroom.tsx missing the Audit Evidence section")
    if "workroom-visibility-note" not in page_src:
        bad("TaskWorkroom.tsx missing the visibility note")

    # Secret guard.
    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] 9 docs present; G1/G3/G5 status + audit privacy + safety posture documented;")
    print("       backend (audit-evidence route, visibility filter, atomic answer claim,")
    print("       clarification_already_answered) + frontend (Audit Evidence section,")
    print("       visibility note, getAuditEvidence client, no dangerouslySetInnerHTML) present")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
