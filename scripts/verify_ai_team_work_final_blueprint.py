#!/usr/bin/env python3
"""Step 66A.3 -- AI Agents Team Work final UX blueprint verifier.

Confirms all 14 blueprint docs exist and cover the required areas, that operator decisions D1-D14 and
confirmations Q1-Q5 are reflected, that the MVP workroom / whitelist v0.1 / Approvals-P0 / DLQ-Retry-P0
are included, and that this stage is blueprint-only (no UI/backend implementation, no runtime change,
no workflow execution, no external action, no production action).

Marker: AI_TEAM_WORK_FINAL_BLUEPRINT_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST = ROOT / "docs" / "test"

DOCS = {
    "final-ux-blueprint": TEST / "ai-team-work-final-ux-blueprint.md",
    "mvp-implementation-scope": TEST / "ai-team-work-mvp-implementation-scope.md",
    "frontend-page-map": TEST / "ai-team-work-frontend-page-map.md",
    "task-lifecycle-model": TEST / "ai-team-work-task-lifecycle-model.md",
    "agent-workroom-blueprint": TEST / "ai-team-work-agent-workroom-blueprint.md",
    "delivery-inbox-blueprint": TEST / "ai-team-work-delivery-inbox-blueprint.md",
    "operator-action-center-blueprint": TEST / "ai-team-work-operator-action-center-blueprint.md",
    "web-research-governance-blueprint": TEST / "ai-team-work-web-research-governance-blueprint.md",
    "data-model-blueprint": TEST / "ai-team-work-data-model-blueprint.md",
    "api-blueprint": TEST / "ai-team-work-api-blueprint.md",
    "rbac-blueprint": TEST / "ai-team-work-rbac-blueprint.md",
    "step66-implementation-sequence": TEST / "ai-team-work-step66-implementation-sequence.md",
    "risk-register": TEST / "ai-team-work-risk-register.md",
    "acceptance-criteria": TEST / "ai-team-work-acceptance-criteria.md",
}

MARKER = "AI_TEAM_WORK_FINAL_BLUEPRINT_VERIFY"

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def main() -> int:
    for name, p in DOCS.items():
        if not p.is_file():
            bad(f"missing doc: docs/test/{p.name} ({name})")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    low = "\n".join(texts.values()).lower()
    umbrella = texts["final-ux-blueprint"].lower()

    # D1-D14 reflected.
    for i in range(1, 15):
        if f"d{i}" not in umbrella:
            bad(f"final blueprint does not reflect decision D{i}")

    # Q1-Q5 reflected.
    for i in range(1, 6):
        if f"q{i}" not in umbrella:
            bad(f"final blueprint does not reflect confirmation Q{i}")

    # Workroom MVP + message types.
    wr = texts["agent-workroom-blueprint"].lower()
    if "minimum viable workroom" not in wr:
        bad("workroom blueprint missing minimum-viable workroom scope")
    if "clarification_question" not in wr:
        bad("workroom blueprint missing message types")

    # Whitelist v0.1.
    if "whitelist v0.1" not in texts["web-research-governance-blueprint"].lower():
        bad("web research blueprint missing whitelist v0.1")

    # Approvals P0 + DLQ/Retry P0.
    oac = texts["operator-action-center-blueprint"].lower()
    if "dlq" not in oac or "p0" not in oac:
        bad("operator action center missing DLQ/Retry P0")
    if "approvals" not in oac or "p0" not in oac:
        bad("operator action center missing Approvals P0")
    if "approvals + dlq/retry both p0" not in umbrella:
        bad("final blueprint does not state Approvals + DLQ/Retry both P0")

    # Blueprint-only posture.
    for phrase in (
        "no ui implementation",
        "no backend implementation",
        "no runtime change",
        "no workflow execution",
        "no external action",
        "no production action",
    ):
        if phrase not in low:
            bad(f"docs do not state '{phrase}'")

    # Web research not claimed to exist.
    if "no web research was performed" not in low and "no web/browsing/search action" not in low:
        bad("web research blueprint does not assert no web research was performed")

    # Secret guard.
    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print(
        "  [OK] 14 blueprint docs present; D1-D14 + Q1-Q5 reflected; MVP workroom + whitelist v0.1;"
    )
    print("       Approvals + DLQ/Retry both P0; blueprint-only (no UI/backend/runtime/workflow/")
    print("       external/production action); no web research performed")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
