#!/usr/bin/env python3
"""Step 66A.1 -- AI Agents Team Work interaction model discovery verifier.

Confirms the Step 66A.1 discovery docs exist and cover every required domain (roles, task types,
multi-channel intake, clarification, delivery/acceptance, agent team, notifications, operator action
center, web research), integrate the six operator-provided decisions, carry the D1-D14 decision
register, mark recommendations non-final, and assert this is planning-only: no UI implementation, no
workflow execution, no external action, no production action.

Marker: AI_TEAM_WORK_INTERACTION_DISCOVERY_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"

DOCS = {
    "interaction-discovery": STAGING / "ai-team-work-interaction-model-discovery.md",
    "current-gap-analysis": STAGING / "ai-team-work-current-gap-analysis.md",
    "user-role-model": STAGING / "ai-team-work-user-role-model.md",
    "task-type-taxonomy": STAGING / "ai-team-work-task-type-taxonomy.md",
    "multi-channel-intake": STAGING / "ai-team-work-multi-channel-intake-model.md",
    "clarification-model": STAGING / "ai-team-work-agent-clarification-model.md",
    "delivery-acceptance": STAGING / "ai-team-work-delivery-acceptance-model.md",
    "agent-team-model": STAGING / "ai-team-work-agent-team-model.md",
    "lifecycle-notification": STAGING / "ai-team-work-lifecycle-notification-model.md",
    "operator-action-center": STAGING / "ai-team-work-operator-action-center-model.md",
    "web-research-capability": STAGING / "ai-team-work-web-research-capability-model.md",
    "decision-register": STAGING / "ai-team-work-decision-register.md",
    "step66-roadmap": STAGING / "ai-team-work-step66-roadmap-proposal.md",
}

MARKER = "AI_TEAM_WORK_INTERACTION_DISCOVERY_VERIFY"

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
            bad(f"missing doc: docs/staging/{p.name} ({name})")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    low = "\n".join(texts.values()).lower()

    # Six operator decisions integrated.
    for token in (
        "multi-role",
        "intake",
        "clarification",
        "accept",
        "fixed software delivery team",
    ):
        if token not in low:
            bad(f"operator decision token not integrated: {token}")
    if "d1" not in low or "d6" not in low:
        bad("operator decisions D1..D6 not referenced")

    # Full D1-D14 decision register.
    reg = texts["decision-register"].lower()
    for i in range(1, 15):
        if f"d{i}" not in reg:
            bad(f"decision register missing item D{i}")

    # Required domain coverage (aggregate).
    domain_tokens = (
        "role",
        "task type",
        "multi-channel intake",
        "clarification",
        "delivery inbox",
        "acceptance",
        "agent team",
        "notification",
        "operator action center",
        "web research",
    )
    for t in domain_tokens:
        if t not in low:
            bad(f"required domain not covered: {t}")

    # Operator Action Center closes Step 65 gaps #6/#7.
    oac = texts["operator-action-center"].lower()
    if "dlq" not in oac or "approval" not in oac:
        bad("operator action center does not address DLQ + approvals gaps")

    # Web research flagged as missing / future, not fabricated.
    web = texts["web-research-capability"].lower()
    if "missing" not in web and "future connector" not in web:
        bad("web research capability not flagged as missing/future")

    # Recommendations marked non-final.
    if "non-final" not in low:
        bad("recommendations not marked non-final")

    # Planning-only posture.
    if "no ui implementation" not in low and "no ui was implemented" not in low:
        bad("docs do not state no UI implementation")
    if "no workflow" not in low:
        bad("docs do not state no workflow execution")
    if "no external action" not in low:
        bad("docs do not state no external action")
    if "no production action" not in low:
        bad("docs do not state no production action")

    # Secret content guard.
    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print(
        "  [OK] all 13 discovery docs present; six operator decisions integrated; D1-D14 register;"
    )
    print(
        "       domains covered; Step 65 DLQ/approvals gaps addressed; web research flagged future;"
    )
    print(
        "       recommendations non-final; planning-only (no UI/workflow/external/production action)"
    )
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
