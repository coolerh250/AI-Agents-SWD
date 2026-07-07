#!/usr/bin/env python3
"""Step 65H.1 -- Failure / recovery / governance validation plan verifier.

Confirms the 65H.1 planning docs define a controlled, auditable failure/governance test plan:
approval, cancel/abort, retry/DLQ, and safety/no-production scenarios; a risk register + per-sub-stage
authorization templates; an execution split (65H.2/65H.3/65H.4); an Admin Console checklist and an
abort/reset plan -- while asserting this stage executed no scenario and no external action
(production_executed stays 0).

Marker: FAILURE_GOVERNANCE_VALIDATION_PLAN_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
PLAN = STAGING / "failure-governance-validation-plan.md"
MATRIX = STAGING / "failure-governance-scenario-matrix.md"
AUTHZ = STAGING / "failure-governance-authorization-matrix.md"
CHECKLIST = STAGING / "failure-governance-admin-console-validation-checklist.md"
ABORT_RESET = STAGING / "failure-governance-abort-reset-plan.md"
RISK = STAGING / "failure-governance-risk-register.md"
SPLIT = STAGING / "failure-governance-execution-split.md"
TEMPLATES = STAGING / "failure-governance-operator-authorization-templates.md"

MARKER = "FAILURE_GOVERNANCE_VALIDATION_PLAN_VERIFY"

DOCS = {
    "validation-plan": PLAN,
    "scenario-matrix": MATRIX,
    "authorization-matrix": AUTHZ,
    "admin-console-checklist": CHECKLIST,
    "abort-reset-plan": ABORT_RESET,
    "risk-register": RISK,
    "execution-split": SPLIT,
    "operator-authorization-templates": TEMPLATES,
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

    # Scenario groups documented.
    if "approval" not in low or (
        "granted" not in low or "denied" not in low or "expired" not in low
    ):
        bad("docs do not document approval scenarios (required/granted/denied/expired)")
    if "cancel" not in low or "abort" not in low or "ignore-after-abort" not in low:
        bad("docs do not document cancel/abort/ignore-after-abort scenarios")
    if "retry" not in low or "dlq" not in low or "replay" not in low:
        bad("docs do not document retry/DLQ/replay scenarios")
    if "no-production" not in low and "no production" not in low:
        bad("docs do not document safety/no-production scenarios")
    if "kill switch" not in low:
        bad("docs do not document kill-switch effectiveness")

    # Execution split.
    if "65h.2" not in low or "65h.3" not in low or "65h.4" not in low:
        bad("docs do not document the 65H.2/65H.3/65H.4 execution split")

    # Authorization templates + risk register.
    if "operator authorization" not in low:
        bad("docs do not include operator authorization templates")
    if "high" not in low or "risk" not in low:
        bad("docs do not include a risk register (HIGH classification)")

    # Admin Console checklist + abort/reset.
    if "/safety" not in low or "/audit-evidence" not in low:
        bad("docs do not document the Admin Console formal-page checklist")
    if "abort" not in low or "reset" not in low:
        bad("docs do not document the abort/reset plan")

    # This-stage posture: nothing executed, nothing external.
    if "no scenario" not in low and "no scenario was executed" not in low:
        bad("docs do not state no scenario execution in this stage")
    if "no workflow execution" not in low:
        bad("docs do not state no workflow execution")
    if "no external write" not in low and "external-write=false" not in low:
        bad("docs do not state no external write")
    if "no llm call" not in low:
        bad("docs do not state no LLM call")
    if "no discord send" not in low:
        bad("docs do not state no Discord send")
    if "no production action" not in low:
        bad("docs do not state no production action")

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

    # The approval-expiry mechanism is a tracked unknown (expected).
    if "tracked" not in low and "unknown" not in low and "to confirm" not in low:
        gap("docs do not track any route/mechanism unknown (e.g. approval expiry)")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] approval + cancel/abort + retry/DLQ + safety scenarios planned; risk register +")
    print("       authorization templates + 65H.2/H.3/H.4 split + Admin Console checklist +")
    print("       abort/reset plan present; no scenario/external/production action; prod_exec=0")
    if gaps:
        print(f"{MARKER}: PASS_WITH_GAPS")
        return 0
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
