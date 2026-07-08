#!/usr/bin/env python3
"""Step 66A.0 -- Environment reset / staging cleanup / test handoff verifier.

Confirms the Step 66A.0 docs record: staging validation runtime cleanup (scoped to the
aiagents-staging project), staging secret residue removed without printing, the test runtime reset
and redeployment on the verified test host (or a documented blocker), and the safety invariants
(production_executed_true_count=0, no production action, no unscoped docker prune) -- with no secret
content committed.

Marker: ENVIRONMENT_RESET_TEST_HANDOFF_VERIFY: PASS | PASS_WITH_GAPS | FAIL
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "docs" / "staging"

REPORT = STAGING / "environment-reset-and-test-handoff-report.md"
CLEANUP = STAGING / "staging-cleanup-record.md"
DEPLOY = STAGING / "test-environment-reset-deployment-report.md"
SAFETY = STAGING / "test-runtime-safety-validation.md"

MARKER = "ENVIRONMENT_RESET_TEST_HANDOFF_VERIFY"

DOCS = {
    "env-reset-report": REPORT,
    "staging-cleanup-record": CLEANUP,
    "test-deployment-report": DEPLOY,
    "test-runtime-safety": SAFETY,
}

SECRET_SHAPES = re.compile(
    r"(-----BEGIN [A-Z ]*PRIVATE KEY|ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"AKIA[0-9A-Z]{16}|xoxb-[A-Za-z0-9-]{10,}|sk-ant-[A-Za-z0-9_-]{20,})"
)
PASSWORD_ASSIGN = re.compile(r"password\s*[:=]\s*\S", re.IGNORECASE)
TOKEN_ASSIGN = re.compile(
    r"(bot[_-]?token|api[_-]?key|access[_-]?token)\s*[:=]\s*[\"']?[A-Za-z0-9/+]{16,}", re.I
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

    # Existence of required records.
    if "staging cleanup record" not in low:
        bad("staging cleanup record not present")
    if "test handoff" not in low and "test environment reset" not in low:
        bad("test handoff / test environment reset report not present")
    if "test runtime safety validation" not in low:
        bad("test runtime safety validation not present")

    # Staging docker cleanup documented + scoped.
    if "aiagents-staging" not in low:
        bad("staging docker cleanup (aiagents-staging project) not documented")
    if "scoped to the aiagents-staging project" not in low:
        bad("staging cleanup not documented as scoped to the aiagents-staging project")
    if "down --volumes" not in low:
        bad("staging teardown command not documented")

    # Secrets not printed / not committed.
    if "staging secrets were not printed" not in low:
        bad("docs do not state staging secrets were not printed")
    if "not committed" not in low:
        bad("docs do not state staging secrets were not committed")

    # Test runtime deployment or blocker documented.
    if "test runtime deployment completed" not in low and "blocker" not in low:
        bad("test runtime deployment completion or blocker not documented")

    # Safety invariants.
    if "production_executed_true_count=0" not in low:
        bad("production_executed_true_count=0 not documented")
    if "no production action" not in low:
        bad("no-production-action not documented")
    if "no unscoped docker prune" not in low:
        bad("no-unscoped-docker-prune not documented")

    # Non-zero prod-exec guard.
    if re.search(r"production_executed_true_count\s*[`]*\s*[:=]?\s*[`]*\s*[1-9]", low):
        bad("production_executed_true_count is non-zero")

    # Secret content guard.
    for name, text in texts.items():
        if SECRET_SHAPES.search(text):
            bad(f"{name} contains secret-shaped content")
        if PASSWORD_ASSIGN.search(text):
            bad(f"{name} contains a stored password assignment")
        if TOKEN_ASSIGN.search(text):
            bad(f"{name} contains a stored token/key value")

    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    # PASS_WITH_GAPS if deployment could not complete but a blocker is documented.
    if "test runtime deployment completed" not in low and "blocker" in low:
        print("  [OK] staging cleanup + test handoff documented; deployment blocked (documented)")
        print(f"{MARKER}: PASS_WITH_GAPS")
        return 0

    print("  [OK] staging validation runtime cleaned (scoped); secrets not printed/committed;")
    print("       test runtime redeployed; prod_exec=0; no production action; no unscoped prune")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
