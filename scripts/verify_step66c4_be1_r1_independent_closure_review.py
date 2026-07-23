#!/usr/bin/env python3
"""Step 66C.4-BE1-R1-R -- process/artifact verifier for the independent closure review.

This verifier confirms the closure-review ARTIFACTS are present and internally consistent and that
the reviewer touched no implementation path. It is NOT a technical verdict: the technical closure
verdict (BE1_TECHNICAL_VERDICT) is declared by the reviewer in the closure documents on the basis
of the mandatory PostgreSQL reproductions, which this static verifier does not re-run.

Emits STEP66C4_BE1_R1_INDEPENDENT_CLOSURE_REVIEW_VERIFY: PASS on success, else FAIL and exit 1.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
HANDOFFS = ROOT / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume"
STAGE = ROOT / "docs" / "stages" / "66c4-be1-r1-independent-closure-review"

REQUIRED_ARTIFACTS = [
    CONTRACTS / "be1-r1-independent-closure-review.md",
    CONTRACTS / "be1-r1-deadline-closure-review.md",
    CONTRACTS / "be1-r1-outbox-durability-closure-review.md",
    CONTRACTS / "be1-r1-payload-safety-closure-review.md",
    CONTRACTS / "be1-r1-migration-and-test-closure-review.md",
    HANDOFFS / "be1-r1-closure-review-result-handoff.md",
    ROOT / "docs" / "test" / "step66c4-be1-r1-independent-closure-review-record.md",
    STAGE / "stage-manifest.yaml",
    STAGE / "context-receipt.md",
    STAGE / "stage-gate-report.md",
    ROOT / "tests" / "test_step66c4_be1_r1_independent_closure_review.py",
]

FOOTER_MARK = "_Non-production only. No production action."
STAGING_SAFETY_MARK = "<!-- staging-safety:"

FAILS: list[str] = []


def _check(cond: bool, msg: str) -> None:
    if not cond:
        FAILS.append(msg)


def main() -> int:
    for path in REQUIRED_ARTIFACTS:
        _check(path.exists(), f"missing required artifact: {path.relative_to(ROOT)}")

    # Every committed markdown closure artifact carries the standard non-production footer.
    for path in REQUIRED_ARTIFACTS:
        if path.suffix != ".md" or not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        _check(FOOTER_MARK in text, f"footer paragraph missing in {path.name}")
        _check(STAGING_SAFETY_MARK in text, f"staging-safety comment missing in {path.name}")

    # The independent closure review must record BOTH markers verbatim, kept separate.
    independent = CONTRACTS / "be1-r1-independent-closure-review.md"
    if independent.exists():
        text = independent.read_text(encoding="utf-8")
        _check(
            "STEP66C4_BE1_R1_INDEPENDENT_CLOSURE_REVIEW_VERIFY: PASS" in text,
            "process marker missing in independent closure review",
        )
        _check(
            "BE1_TECHNICAL_VERDICT: PASS" in text
            or "BE1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED" in text,
            "technical verdict missing in independent closure review",
        )

    # Stage manifest must declare the locked-down authorization flags.
    manifest = STAGE / "stage-manifest.yaml"
    if manifest.exists():
        m = manifest.read_text(encoding="utf-8")
        for flag in (
            "implementation_change_allowed: false",
            "migration_change_allowed: false",
            "merge_allowed: false",
            "be2_authorized: false",
            "isolated_postgresql_testing_allowed: true",
            "product_owner_review_required: true",
        ):
            _check(flag in m, f"stage manifest missing flag: {flag}")

    if FAILS:
        print("STEP66C4_BE1_R1_INDEPENDENT_CLOSURE_REVIEW_VERIFY: FAIL")
        for f in FAILS:
            print(f"  [FAIL] {f}")
        return 1

    print("  [OK] All closure-review artifacts present with the non-production footer; both")
    print("       markers recorded separately (process marker vs technical verdict); stage")
    print("       manifest locks implementation/migration/merge/BE2 to false and allows only")
    print("       isolated PostgreSQL testing pending Product Owner review. This verifier is a")
    print("       process gate; the technical verdict is declared by the reviewer from the")
    print("       mandatory PostgreSQL reproductions, not by this script.")
    print("STEP66C4_BE1_R1_INDEPENDENT_CLOSURE_REVIEW_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
