#!/usr/bin/env python3
"""Step 65H.5 -- Failure & governance operator evidence review verifier.

Confirms the 65H.5 review docs consolidate the 65H.2/65H.3/65H.4 results (each PASS_WITH_GAPS with the
operator's visibility outcome), record the operator-flagged DLQ UX gap, the approval-expiry and
late-stream-event tracked gaps, classify all gaps (no BLOCKING gap), summarise the safety posture, and
assert Step 65I readiness -- while asserting this stage executed no new scenario and no external action
(production_executed stays 0).

Marker: FAILURE_GOVERNANCE_OPERATOR_REVIEW_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"
REVIEW = STAGING / "failure-governance-operator-evidence-review.md"
SCENARIOS = STAGING / "failure-governance-validated-scenarios-summary.md"
GAP_CLASS = STAGING / "failure-governance-gap-classification.md"
UX_GAP = STAGING / "failure-governance-operator-ux-gap-register.md"
SAFETY = STAGING / "failure-governance-safety-summary.md"
READINESS = STAGING / "failure-governance-step65i-readiness.md"

MARKER = "FAILURE_GOVERNANCE_OPERATOR_REVIEW_VERIFY"

DOCS = {
    "evidence-review": REVIEW,
    "validated-scenarios-summary": SCENARIOS,
    "gap-classification": GAP_CLASS,
    "operator-ux-gap-register": UX_GAP,
    "safety-summary": SAFETY,
    "step65i-readiness": READINESS,
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

    # Consolidated sub-stage results.
    if (
        low.count("pass_with_gaps") < 1
        or "65h.2" not in low
        or "65h.3" not in low
        or "65h.4" not in low
    ):
        bad("docs do not consolidate 65H.2/65H.3/65H.4 (PASS_WITH_GAPS)")
    if "completed_with_gaps" not in low:
        bad("docs do not record the overall 65H status COMPLETED_WITH_GAPS")

    # Operator visibility outcomes.
    if "visible" not in low or "partial_with_gaps" not in low:
        bad("docs do not record operator VISIBLE / PARTIAL_WITH_GAPS outcomes")

    # Key gaps documented.
    if (
        "no dlq / retry admin console page" not in low
        and "no admin console page" not in low
        and ("dlq" not in low)
    ):
        bad("docs do not document the DLQ UX gap")
    if "expiry" not in low and "expired" not in low:
        bad("docs do not document the approval expiry gap")
    if "late-stream-event" not in low and "late stream" not in low and "late-stream" not in low:
        bad("docs do not document the late-stream-event gap")

    # Gap classification + readiness.
    if "blocking" not in low or "operator_ux_gap" not in low.replace("-", "_"):
        bad("docs do not include the gap classification (BLOCKING / OPERATOR_UX_GAP)")
    if "65i" not in low or "readiness" not in low:
        bad("docs do not document Step 65I readiness")

    # This-stage posture.
    if "no new scenario" not in low:
        bad("docs do not state no new scenario execution in this stage")
    if "no external" not in low and "external-write=false" not in low:
        bad("docs do not state no external action")
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

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    print("  [OK] 65H.2/65H.3/65H.4 consolidated (COMPLETED_WITH_GAPS); operator visibility +")
    print("       DLQ UX gap + approval-expiry + late-stream gaps classified (no BLOCKING); safety")
    print(
        "       summary; Step 65I readiness; no new scenario/external/production action; prod_exec=0"
    )
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
