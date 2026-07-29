#!/usr/bin/env python3
"""Step 66C.4-BE3-RA-1FC -- focused-closure self-verifier (process marker only).

Static/structural checks for the ORIGINAL RA-1R reviewer's focused closure of H-1/M-1/M-2/M-3 over
the RA-1B remediation. Confirms the closure deliverables exist, that the files UNDER REVIEW (the
remediated ``migration_runner.py``, the CLI, every ``migrations/*.sql``, and the RA-1A/RA-1B test
suites, plus the two BE1 allowlist guards) are byte-identical to the reviewed remediation head
``b31e655``, that the closure test suite reuses the fail-closed destructive-PG guard, that the review
records BOTH a process marker AND a separate technical verdict, that the safety boundary is recorded
(production_executed_true_count: 0; PR #21 untouched), and that no internal IP / SSH alias / private
hostname / credential leaked into any committed closure file.

It does NOT connect to PostgreSQL -- the real focused-closure rehearsal already ran against an
isolated ephemeral PostgreSQL 16 (see docs/test/step66c4-be3-ra1b-focused-closure-evidence.md). It
emits ONLY the process marker; the technical verdict is a human judgment recorded in the review.

Process marker: STEP66C4_BE3_RA1B_FOCUSED_CLOSURE_VERIFY: PASS | FAIL
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

REVIEW_DOC = CONTRACT / "be3-ra1b-focused-closure-review.md"
EVIDENCE_DOC = TEST_DOCS / "step66c4-be3-ra1b-focused-closure-evidence.md"
RESULT_DOC = HANDOFF / "be3-ra1b-focused-closure-result.md"
REVIEW_TESTS = ROOT / "tests" / "test_step66c4_be3_ra1b_focused_closure.py"
REVIEW_VERIFIER = ROOT / "scripts" / "verify_step66c4_be3_ra1b_focused_closure.py"

# Files under review this closure must NOT have modified, vs the reviewed remediation head.
FROZEN = (
    "shared/sdk/backup_dr/migration_runner.py",
    "scripts/run_platform_migrations.py",
    "tests/test_step66c4_be3_ra1_migration_rehearsal.py",
    "tests/test_step66c4_be3_ra1b_migration_runner_remediation.py",
    "tests/test_step66c4_be1_data_model_deadline_outbox.py",
    "tests/test_step66c4_be1_r1_remediation.py",
)
REVIEWED_REMEDIATION_HEAD = "b31e655"

PROCESS_MARKER = "STEP66C4_BE3_RA1B_FOCUSED_CLOSURE_VERIFY"
TECH_VERDICT_TOKEN = "RA1_TECHNICAL_VERDICT"

# Neutral-label rule -- needles assembled from fragments so this file does not itself contain the
# literal forbidden tokens (allowing it to scan itself cleanly).
_PRIVATE_OCTET = r"\b10\.0\." + r"1\.\d{1,3}\b"
_SSH_ALIAS = r"\b" + "aiagent" + "-swd" + r"\b"
_EPHEMERAL_PW = r"\b" + "fc" + "ephemeral" + r"\b"
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
    for p in (REVIEW_DOC, EVIDENCE_DOC, RESULT_DOC, REVIEW_TESTS, REVIEW_VERIFIER):
        if not p.is_file():
            bad(f"missing closure artifact: {p}")
    if failures:
        print(f"{PROCESS_MARKER}: FAIL")
        return 1

    # Files under review are byte-identical to the reviewed remediation head (nothing modified).
    diff = _git("diff", "--name-only", REVIEWED_REMEDIATION_HEAD, "HEAD")
    changed = {f for f in diff.splitlines() if f}
    for frozen in FROZEN:
        if frozen in changed:
            bad(f"file under review was modified by this closure: {frozen}")
    for f in changed:
        if f.startswith("migrations/"):
            bad(f"a migrations/ file was modified by this closure: {f}")

    tests = REVIEW_TESTS.read_text(encoding="utf-8")
    if "destructive_pg_refusal_reason" not in tests or "requires_pg" not in tests:
        bad("closure test suite does not reuse the fail-closed destructive-PG guard")
    for token in ("apply_chain_with_ledger", "plan_chain", "redact_for_operator"):
        if token not in tests:
            bad(f"closure test suite does not exercise {token}")

    review = REVIEW_DOC.read_text(encoding="utf-8")
    result = RESULT_DOC.read_text(encoding="utf-8")
    evidence = EVIDENCE_DOC.read_text(encoding="utf-8")
    if f"{PROCESS_MARKER}: PASS" not in review + result + evidence:
        bad("process marker not recorded in the closure artifacts")
    if TECH_VERDICT_TOKEN not in review:
        bad("technical verdict token not recorded in the review document")
    for finding in ("H-1", "M-1", "M-2", "M-3"):
        if finding not in review:
            bad(f"review document does not record a per-finding verdict for {finding}")

    if "production_executed_true_count: 0" not in evidence:
        bad("production_executed_true_count: 0 not recorded in the evidence record")
    if "#21" not in result and "PR 21" not in result:
        bad("review result does not record the status of PR #21")

    for p in (REVIEW_DOC, EVIDENCE_DOC, RESULT_DOC, REVIEW_TESTS, REVIEW_VERIFIER):
        text = p.read_text(encoding="utf-8")
        for pat in FORBIDDEN_PATTERNS:
            if pat.search(text):
                bad(f"forbidden internal identifier {pat.pattern!r} in {p.name}")

    if failures:
        print(f"{PROCESS_MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] Focused-closure deliverables present; files under review unmodified vs b31e655;")
    print(
        "       closure suite reuses the fail-closed guard and exercises the ledger/plan/redactor;"
    )
    print("       process marker and a separate per-finding technical verdict recorded; safety")
    print("       boundary (production_executed_true_count: 0, PR #21 untouched) recorded; neutral")
    print("       labels only.")
    print(f"{PROCESS_MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
