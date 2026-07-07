#!/usr/bin/env python3
"""Step 65H.2 -- Approval & governance path validation verifier.

Confirms the 65H.2 records document a real controlled approval/governance run: the approval
required/granted/denied and production-block paths validated on controlled workflows with no external
integration, the expiry path recorded as a tracked gap, and no production action (production_executed
stays 0). Operator UI validation is pending.

Marker: APPROVAL_GOVERNANCE_VALIDATION_VERIFY:
        PASS | PASS_WITH_GAPS | PASS_WITH_OPERATOR_VALIDATION_PENDING | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REPORT = STAGING / "approval-governance-validation-report.md"
EVIDENCE = STAGING / "approval-governance-evidence.md"
SAFETY = STAGING / "approval-governance-safety-record.md"
GAPS = STAGING / "approval-governance-known-gaps.md"
VALIDATION = STAGING / "approval-governance-operator-validation-request.md"

MARKER = "APPROVAL_GOVERNANCE_VALIDATION_VERIFY"

DOCS = {
    "validation-report": REPORT,
    "evidence": EVIDENCE,
    "safety-record": SAFETY,
    "known-gaps": GAPS,
    "operator-validation-request": VALIDATION,
}

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
PASSWORD_ASSIGN = re.compile(r"password\s*[:=]\s*\S", re.IGNORECASE)
TOKEN_ASSIGN = re.compile(
    r"(token|api[_-]?key|secret|webhook)\s*[:=]\s*[\"']?[A-Za-z0-9/+]{16,}", re.I
)

failures: list[str] = []
gaps: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def gap(m: str) -> None:
    gaps.append(m)
    print(f"  [GAP] {m}")


def main() -> int:
    for name, p in DOCS.items():
        if not p.is_file():
            bad(f"missing doc: docs/staging/{p.name} ({name})")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    texts = {name: p.read_text(encoding="utf-8") for name, p in DOCS.items()}
    low = "\n".join(texts.values()).lower()

    # Paths validated.
    if "granted" not in low or "approved" not in low or "resume" not in low:
        bad("docs do not document the approval-granted/resume path")
    if "denied" not in low or "rejected" not in low:
        bad("docs do not document the approval-denied/terminal path")
    if "production block" not in low and "production-block" not in low:
        bad("docs do not document the production-block path")
    if "waiting_approval" not in low:
        bad("docs do not document the waiting_approval blocked state")

    # Expiry tracked gap.
    if "expired" not in low or ("tracked gap" not in low and "tracked" not in low):
        bad("docs do not record the approval-expiry tracked gap")

    # No external / no production.
    if "no external" not in low and "external-write=false" not in low:
        bad("docs do not state no external integration used")
    for phrase in ("no github write", "no discord send", "no llm call", "no production action"):
        if phrase not in low:
            bad(f"docs do not state '{phrase}'")
    if "operator ui validation" not in low and "operator validation" not in low:
        bad("docs do not document operator UI validation pending")

    for name, text in texts.items():
        tl = text.lower()
        if "production_executed_true_count=0" not in tl:
            bad(f"{name} does not document production_executed_true_count=0")

    if re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low):
        bad("production_executed_true_count is non-zero")

    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")
        if PASSWORD_ASSIGN.search(text):
            bad(f"{name} contains a stored password assignment")
        if TOKEN_ASSIGN.search(text):
            bad(f"{name} contains a stored token/key/secret value")

    # The expiry path is a tracked gap -> PASS_WITH_GAPS is expected.
    gap("approval expired/timeout path is a tracked gap (no safe route)")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    operator_confirmed = bool(
        re.search(
            r"operator response:\s*\**\s*visible", texts["operator-validation-request"].lower()
        )
    )

    print("  [OK] approval required/granted/denied + production-block validated; expiry = tracked")
    print("       gap; no external integration; no production action; prod_exec=0")
    if not operator_confirmed:
        print(f"{MARKER}: PASS_WITH_GAPS")
        return 0
    print(f"{MARKER}: PASS_WITH_GAPS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
