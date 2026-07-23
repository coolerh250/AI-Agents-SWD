#!/usr/bin/env python3
"""Step 66C.4-BE2-R -- static verifier for the independent review artifacts.

Self-contained: no database, no Redis, no network. It asserts that every required review
artifact exists, carries the standard non-production footer, records the process marker and the
technical verdict as SEPARATE markers, and that the stage manifest declares the non-activation /
non-merge posture. It does NOT re-run the reproductions (those are recorded in the review docs).
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONTRACT = REPO / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
HANDOFF = REPO / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume"
STAGE = REPO / "docs" / "stages" / "66c4-be2-independent-review"

REQUIRED_REVIEW_DOCS = [
    CONTRACT / "be2-independent-review.md",
    CONTRACT / "be2-lifecycle-poller-review.md",
    CONTRACT / "be2-outbox-relay-review.md",
    CONTRACT / "be2-transaction-and-concurrency-review.md",
    CONTRACT / "be2-failure-recovery-review.md",
    CONTRACT / "be2-observability-and-security-review.md",
    CONTRACT / "be2-test-quality-review.md",
    HANDOFF / "be2-review-result-handoff.md",
    REPO / "docs" / "test" / "step66c4-be2-independent-review-record.md",
    STAGE / "stage-manifest.yaml",
    STAGE / "context-receipt.md",
    STAGE / "stage-gate-report.md",
]

PROCESS_MARKER = "STEP66C4_BE2_INDEPENDENT_REVIEW_VERIFY: PASS"
VERDICT_MARKER = "BE2_TECHNICAL_VERDICT: REMEDIATION_REQUIRED"
FOOTER_SENTINEL = "_Non-production only."
STAGING_COMMENT = "<!-- staging-safety:"

MANIFEST_FLAGS = [
    "implementation_change_allowed: false",
    "merge_allowed: false",
    "be3_authorized: false",
    "producer_cutover_allowed: false",
    "deployment_allowed: false",
    'status: "review-complete"',
]

# No committed review artifact may leak an internal IP, SSH alias, or OS username.
FORBIDDEN_SUBSTRINGS = ["10.0.1.31", "aiagent-swd", "stpadmin"]


def main() -> int:
    errors: list[str] = []

    for path in REQUIRED_REVIEW_DOCS:
        if not path.exists():
            errors.append(f"missing required artifact: {path.relative_to(REPO)}")
            continue
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".md":
            if FOOTER_SENTINEL not in text:
                errors.append(f"missing non-production footer: {path.relative_to(REPO)}")
            if STAGING_COMMENT not in text:
                errors.append(f"missing staging-safety comment: {path.relative_to(REPO)}")
        for bad in FORBIDDEN_SUBSTRINGS:
            if bad in text:
                errors.append(f"masking violation ({bad}) in {path.relative_to(REPO)}")

    handoff = HANDOFF / "be2-review-result-handoff.md"
    if handoff.exists():
        htext = handoff.read_text(encoding="utf-8")
        if PROCESS_MARKER not in htext:
            errors.append("handoff missing process marker")
        if VERDICT_MARKER not in htext:
            errors.append("handoff missing technical verdict marker")

    manifest = STAGE / "stage-manifest.yaml"
    if manifest.exists():
        mtext = manifest.read_text(encoding="utf-8")
        for flag in MANIFEST_FLAGS:
            if flag not in mtext:
                errors.append(f"stage manifest missing flag: {flag}")

    if errors:
        print("STEP66C4_BE2_INDEPENDENT_REVIEW_VERIFY: FAIL")
        for e in errors:
            print(f"  [FAIL] {e}")
        return 1

    print("  [OK] all required review artifacts present with footer + masking")
    print("  [OK] process marker and technical verdict recorded SEPARATELY")
    print("  [OK] stage manifest declares non-activation / non-merge posture")
    print(PROCESS_MARKER)
    print(f"  NOTE: technical verdict recorded separately -> {VERDICT_MARKER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
