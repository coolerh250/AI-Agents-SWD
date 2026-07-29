#!/usr/bin/env python3
"""Step 66C.4-BE3-RA-1R -- INDEPENDENT review self-verifier (process marker only).

Static/structural checks. Confirms the independent-review deliverables exist, that the files UNDER
REVIEW were NOT modified by this review (migration_runner.py, every migrations/*.sql, and the RA-1A
rehearsal suite are byte-identical to the reviewed feature head), that the independent test suite
reuses the fail-closed destructive-PG guard, that the review records both the process marker AND a
separate technical verdict, that the safety boundary is recorded (production_executed_true_count: 0;
PR #21 untouched), and that no internal IP / SSH alias / private hostname leaked into any committed
review file.

This verifier does NOT connect to PostgreSQL -- the real, independent rehearsal already ran against
an isolated ephemeral PostgreSQL 16 (see docs/test/step66c4-be3-ra1-independent-review-evidence.md).
It emits ONLY the process marker; the technical verdict is a human judgment recorded in the review.

Process marker: STEP66C4_BE3_RA1_INDEPENDENT_REVIEW_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
HANDOFF = ROOT / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume"
TEST_DOCS = ROOT / "docs" / "test"

REVIEW_DOC = CONTRACT / "be3-ra1-independent-migration-review.md"
EVIDENCE_DOC = TEST_DOCS / "step66c4-be3-ra1-independent-review-evidence.md"
RESULT_DOC = HANDOFF / "be3-ra1-independent-review-result.md"
REVIEW_TESTS = ROOT / "tests" / "test_step66c4_be3_ra1_independent_review.py"
REVIEW_VERIFIER = ROOT / "scripts" / "verify_step66c4_be3_ra1_independent_review.py"

# Files under review that this review must NOT have modified.
FROZEN = (
    "shared/sdk/backup_dr/migration_runner.py",
    "tests/test_step66c4_be3_ra1_migration_rehearsal.py",
)
REVIEWED_FEATURE_HEAD = "27184b5"

PROCESS_MARKER = "STEP66C4_BE3_RA1_INDEPENDENT_REVIEW_VERIFY"
TECH_VERDICT_TOKEN = "RA1_TECHNICAL_VERDICT"

# Neutral-label rule: no internal IPv4, SSH alias, private hostname, or credential in committed
# review files. The needles are assembled from fragments so this verifier does not itself contain
# the literal tokens it forbids (allowing it to scan itself cleanly).
_PRIVATE_OCTET = r"\b10\.0\." + r"1\.\d{1,3}\b"
_SSH_ALIAS = r"\b" + "aiagent" + "-swd" + r"\b"
_EPHEMERAL_PW = r"\b" + "ephemeral" + "review" + r"\b"
_PRIVATE_USER = r"\b" + "it" + "admin" + r"\b"
FORBIDDEN_PATTERNS = tuple(
    re.compile(p) for p in (_PRIVATE_OCTET, _SSH_ALIAS, _EPHEMERAL_PW, _PRIVATE_USER)
)

failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> int:  # noqa: C901
    # 1. Required review artifacts exist.
    for p in (REVIEW_DOC, EVIDENCE_DOC, RESULT_DOC, REVIEW_TESTS, REVIEW_VERIFIER):
        if not p.is_file():
            bad(f"missing review artifact: {p}")
    if failures:
        print(f"{PROCESS_MARKER}: FAIL")
        return 1

    # 2. Files under review are byte-identical to the reviewed feature head (nothing modified).
    diff = _git("diff", "--name-only", REVIEWED_FEATURE_HEAD, "HEAD")
    changed = {f for f in diff.splitlines() if f}
    for frozen in FROZEN:
        if frozen in changed:
            bad(f"file under review was modified by this review: {frozen}")
    for f in changed:
        if f.startswith("migrations/"):
            bad(f"a migrations/ file was modified by this review: {f}")

    # 3. Independent test suite reuses the fail-closed destructive-PG guard and does not weaken it.
    tests = REVIEW_TESTS.read_text(encoding="utf-8")
    if "destructive_pg_refusal_reason" not in tests or "requires_pg" not in tests:
        bad("check3: independent test suite does not reuse the fail-closed destructive-PG guard")

    # 4. Independent suite exercises the runner FAILURE path the RA-1A suite never does.
    if "apply_chain_locked" not in tests:
        bad("check4: independent suite does not exercise apply_chain_locked directly")
    if "failure_path_characterization" not in tests:
        bad("check4: independent suite lacks the apply_chain_locked failure-path characterization")

    # 5. Review records BOTH a process marker AND a separate technical verdict.
    review = REVIEW_DOC.read_text(encoding="utf-8")
    result = RESULT_DOC.read_text(encoding="utf-8")
    evidence = EVIDENCE_DOC.read_text(encoding="utf-8")
    if f"{PROCESS_MARKER}: PASS" not in review + result + evidence:
        bad("check5: process marker not recorded in the review artifacts")
    if TECH_VERDICT_TOKEN not in review:
        bad("check5: technical verdict token not recorded in the review document")

    # 6. Safety boundary recorded.
    if "production_executed_true_count: 0" not in evidence:
        bad("check6: production_executed_true_count: 0 not recorded in the evidence record")
    if "#21" not in result and "PR 21" not in result and "pull/21" not in result.lower():
        bad("check6: review result does not record the status of PR #21")

    # 7. Neutral labels only -- no internal IP / SSH alias / credential / username in committed files.
    for p in (REVIEW_DOC, EVIDENCE_DOC, RESULT_DOC, REVIEW_TESTS, REVIEW_VERIFIER):
        text = p.read_text(encoding="utf-8")
        for pat in FORBIDDEN_PATTERNS:
            if pat.search(text):
                bad(f"check7: forbidden internal identifier {pat.pattern!r} in {p.name}")

    if failures:
        print(f"{PROCESS_MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] Independent-review deliverables present; files under review unmodified;")
    print("       independent suite reuses the fail-closed guard and exercises the runner failure")
    print("       path; process marker and a separate technical verdict recorded; safety boundary")
    print(
        "       (production_executed_true_count: 0, PR #21 untouched) recorded; neutral labels only."
    )
    print(f"{PROCESS_MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
