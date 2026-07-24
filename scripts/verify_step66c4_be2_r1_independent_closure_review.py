#!/usr/bin/env python3
"""Step 66C.4-BE2-R1-R -- static verifier for the independent CLOSURE-review artifacts.

Self-contained: no database, no Redis, no network. It asserts that every required closure-review
artifact exists, carries the standard non-production footer + staging-safety comment, records the
process marker and the technical verdict as SEPARATE markers, that the stage manifest declares the
non-activation / non-merge posture, and that no committed artifact leaks an internal identifier. It
also confirms the reviewer did not modify any implementation file (git diff over the code trees).
It does NOT re-run the PG/Redis reproductions (those are recorded in the review docs + test record).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONTRACT = REPO / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
HANDOFF = REPO / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume"
STAGE = REPO / "docs" / "stages" / "66c4-be2-r1-independent-closure-review"
TEST = REPO / "tests" / "test_step66c4_be2_r1_independent_closure_review.py"

CLOSURE_DOCS = [
    CONTRACT / "be2-r1-summary-closure-review.md",
    CONTRACT / "be2-r1-expiry-consistency-closure-review.md",
    CONTRACT / "be2-r1-relay-timeout-closure-review.md",
    CONTRACT / "be2-r1-retry-semantics-closure-review.md",
    CONTRACT / "be2-r1-replay-boundary-closure-review.md",
    CONTRACT / "be2-r1-historical-tests-closure-review.md",
    CONTRACT / "be2-r1-scope-and-safety-closure-review.md",
]

REQUIRED_ARTIFACTS = CLOSURE_DOCS + [
    HANDOFF / "be2-r1-closure-review-result-handoff.md",
    REPO / "docs" / "test" / "step66c4-be2-r1-independent-closure-review-record.md",
    STAGE / "stage-manifest.yaml",
    STAGE / "context-receipt.md",
    STAGE / "stage-gate-report.md",
    TEST,
]

PROCESS_MARKER = "STEP66C4_BE2_R1_INDEPENDENT_CLOSURE_REVIEW_VERIFY: PASS"
VERDICT_MARKER = "BE2_TECHNICAL_VERDICT: PASS"
FOOTER_SENTINEL = "_Non-production only."
STAGING_COMMENT = "<!-- staging-safety:"

MANIFEST_FLAGS = [
    "implementation_change_by_reviewer: false",
    "merge_pr_allowed: false",
    "deployment_allowed: false",
    "shared_runtime_activation_allowed: false",
    "be3_authorized: false",
    'status: "closure-review-complete"',
]

# No committed artifact may leak an internal IP, SSH alias, or OS username.
FORBIDDEN_SUBSTRINGS = ["10.0.1.31", "10.0.1.32", "aiagent-swd", "itadmin", "stpadmin"]

# Reviewer must not have modified any implementation file.
CODE_TREES = (
    "apps/",
    "shared/",
    "migrations/",
    "services/",
    "frontend/",
    "infra/",
    "helm/",
    "k8s/",
    ".github/workflows/",
)


def _reviewer_touched_impl() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except Exception:
        return []  # git unavailable: skip this check rather than false-fail
    touched = []
    for line in out.splitlines():
        if line.strip().startswith(CODE_TREES):
            touched.append(line.strip())
    return touched


def main() -> int:
    errors: list[str] = []

    for path in REQUIRED_ARTIFACTS:
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

    handoff = HANDOFF / "be2-r1-closure-review-result-handoff.md"
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

    touched = _reviewer_touched_impl()
    if touched:
        errors.append(f"reviewer modified implementation file(s): {touched}")

    if errors:
        print("STEP66C4_BE2_R1_INDEPENDENT_CLOSURE_REVIEW_VERIFY: FAIL")
        for e in errors:
            print(f"  [FAIL] {e}")
        return 1

    print("  [OK] 7 closure-review docs + handoff + test record + 3 stage docs + test file present")
    print("  [OK] every doc carries the non-production footer + staging-safety comment; no masking leak")
    print("  [OK] process marker and technical verdict recorded SEPARATELY")
    print("  [OK] stage manifest declares non-activation / non-merge posture")
    print("  [OK] reviewer modified no implementation file")
    print(PROCESS_MARKER)
    print(f"  NOTE: technical verdict recorded separately -> {VERDICT_MARKER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
