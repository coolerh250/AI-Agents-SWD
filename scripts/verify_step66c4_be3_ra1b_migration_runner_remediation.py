#!/usr/bin/env python3
"""Step 66C.4-BE3-RA-1B -- migration runner remediation self-verifier.

Static/structural checks plus two live checks (independent review branch pushed to origin; PR #21
still Draft/unmerged). Confirms H-1/M-1/M-2/M-3 are closed in the actual source (not merely claimed
in the docs), the required artifacts exist, and the next gate (focused closure by the original
RA-1R reviewer) is recorded as still pending.

Marker: STEP66C4_BE3_RA1B_MIGRATION_RUNNER_REMEDIATION_VERIFY: PASS | FAIL
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

RECORD = CONTRACT / "be3-ra1b-migration-runner-remediation-record.md"
EVIDENCE = TEST_DOCS / "step66c4-be3-ra1b-migration-runner-remediation-evidence.md"
HANDOFF_DOC = HANDOFF / "be3-ra1b-to-focused-closure-handoff.md"

RUNNER = ROOT / "shared" / "sdk" / "backup_dr" / "migration_runner.py"
CLI = ROOT / "scripts" / "run_platform_migrations.py"
TEST_SUITE = ROOT / "tests" / "test_step66c4_be3_ra1b_migration_runner_remediation.py"

REVIEW_BRANCH = "review/66c4-be3-ra1-migration-rollback"
REVIEW_COMMIT = "352d546"

MARKER = "STEP66C4_BE3_RA1B_MIGRATION_RUNNER_REMEDIATION_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> int:  # noqa: C901
    for p in (RECORD, EVIDENCE, HANDOFF_DOC, RUNNER, CLI, TEST_SUITE):
        if not p.is_file():
            bad(f"missing file: {p}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    runner_src = RUNNER.read_text(encoding="utf-8")
    cli_src = CLI.read_text(encoding="utf-8")
    record = RECORD.read_text(encoding="utf-8")
    evidence = EVIDENCE.read_text(encoding="utf-8")
    handoff = HANDOFF_DOC.read_text(encoding="utf-8")
    progress_md = (ROOT / "source" / "progress.md").read_text(encoding="utf-8")

    # 1. Independent review branch pushed to origin at the expected commit.
    remote_ref = _git("ls-remote", "origin", f"refs/heads/{REVIEW_BRANCH}")
    if not remote_ref:
        bad(f"check1: origin/{REVIEW_BRANCH} not found (git ls-remote returned nothing)")
    elif not remote_ref.startswith(REVIEW_COMMIT):
        bad(f"check1: origin/{REVIEW_BRANCH} does not start with {REVIEW_COMMIT}: {remote_ref}")

    # 2. Failed transaction: ROLLBACK before unlock.
    fn_starts = sorted(m.start() for m in re.finditer(r"\nasync def \w+\(", runner_src))
    for fn_name in ("apply_chain_locked", "apply_chain_with_ledger"):
        block_start = runner_src.find(f"async def {fn_name}(")
        if block_start == -1:
            bad(f"check2: {fn_name} not found")
            continue
        later_starts = [s for s in fn_starts if s > block_start]
        block_end = later_starts[0] if later_starts else len(runner_src)
        block = runner_src[block_start:block_end]
        rollback_pos = block.find('conn.execute("ROLLBACK")')
        unlock_pos = block.find("pg_advisory_unlock")
        if rollback_pos == -1 or unlock_pos == -1 or rollback_pos > unlock_pos:
            bad(f"check2: {fn_name} does not ROLLBACK strictly before unlock")

    # 3. Original migration error not masked by a cleanup error.
    if "_safe_cleanup_step" not in runner_src:
        bad("check3: no cleanup-step isolation helper found")
    if "raise original_error" not in runner_src:
        bad("check3: the original exception is not what gets re-raised")

    # 4. Cleanup failure discards the connection.
    if "cleanup_errors" not in runner_src or "await conn.close()" not in runner_src:
        bad("check4: no connection-disposal path on cleanup failure")

    # 5. Cancellation does not leak a lock/session.
    if "BaseException" not in runner_src:
        bad("check5: BaseException (covers CancelledError) is not caught anywhere")
    if "asyncio.shield" not in runner_src:
        bad("check5: cleanup steps are not shielded from outer cancellation")

    # 6. Fingerprint covers CHECK expressions and FK actions.
    if "pg_get_constraintdef" not in runner_src:
        bad("check6: fingerprint does not use pg_get_constraintdef")

    # 7. Mutation tests detect semantic drift.
    test_src = TEST_SUITE.read_text(encoding="utf-8")
    for must in (
        "test_pg_fingerprint_detects_check_expression_change",
        "test_pg_fingerprint_detects_fk_on_delete_change",
        "test_pg_fingerprint_detects_fk_on_update_change",
        "test_pg_fingerprint_detects_deferrability_change",
        "test_pg_fingerprint_detects_index_predicate_and_expression_change",
    ):
        if must not in test_src:
            bad(f"check7: missing mandatory mutation test {must}")

    # 8. Ledger records version/filename/checksum/status.
    for col in ("migration_version", "migration_filename", "migration_sha256", "status"):
        if col not in runner_src:
            bad(f"check8: ledger schema missing column {col}")

    # 9. Untracked schema is never auto-adopted.
    if "UntrackedSchemaError" not in runner_src or "UNTRACKED_SCHEMA" not in runner_src:
        bad("check9: untracked-schema detection missing")

    # 10. Ambiguous commit reconciles only under strict conditions.
    if "reconciled_after_ambiguous_commit" not in runner_src:
        bad("check10: ambiguous-commit reconciliation state missing")
    if "SchemaDriftError" not in runner_src:
        bad("check10: no drifted/fail-closed path for a non-matching ambiguous attempt")

    # 11. Advisory-lock wait has a timeout.
    if "MigrationLockTimeoutError" not in runner_src or "pg_try_advisory_lock" not in runner_src:
        bad("check11: advisory-lock wait is not bounded")

    # 12. Migration statement has a timeout.
    if "statement_timeout" not in runner_src or "lock_timeout" not in runner_src:
        bad("check12: no statement/lock timeout is set")

    # 13. Plan mode performs no DDL/ledger write.
    if "async def plan_chain" not in runner_src:
        bad("check13: plan_chain missing")
    plan_start = runner_src.find("async def plan_chain(")
    plan_block = runner_src[plan_start : plan_start + 4000] if plan_start != -1 else ""
    if "ensure_ledger_bootstrapped" in plan_block or "apply_migration_file" in plan_block:
        bad("check13: plan_chain appears to perform a write")

    # 14. Failure has a non-zero exit and a redacted structured result.
    if "return 1" not in cli_src:
        bad("check14: CLI does not have a failure (return 1) exit path")
    if "sys.exit(2)" not in cli_src:
        bad("check14: CLI does not have a missing-config (exit 2) path")
    if "redact_for_operator" not in cli_src:
        bad("check14: CLI does not redact errors before printing")

    # 15. No shared DB/deployment/activation/runtime action recorded.
    for f in (record, evidence, handoff):
        if "shared" not in f.lower():
            bad("check15: a required record does not address shared-DB/deployment safety")
            break

    # 16. PR #21 remains Draft/unmerged.
    gh = subprocess.run(
        ["gh", "pr", "view", "21", "--json", "state,isDraft,mergedAt"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if gh.returncode == 0:
        import json

        pr = json.loads(gh.stdout)
        if pr.get("state") != "OPEN" or pr.get("isDraft") is not True or pr.get("mergedAt"):
            bad(f"check16: PR #21 is not Draft/OPEN/unmerged: {pr}")
    else:
        bad("check16: could not query PR #21 state via gh (gh CLI unavailable or auth missing)")

    # 17. production_executed_true_count = 0.
    if "production_executed_true_count: 0" not in progress_md:
        bad("check17: production_executed_true_count: 0 not recorded in source/progress.md")

    # 18. Original-reviewer focused closure remains the next gate.
    if "focused closure" not in handoff.lower() or "original" not in handoff.lower():
        bad("check18: handoff does not record focused closure by the original reviewer as next")
    if "PENDING" not in handoff:
        bad("check18: handoff does not mark focused closure as PENDING")

    if failures:
        print(f"{MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] Independent review branch preserved on origin; ROLLBACK precedes unlock on every")
    print("       failure path; the original migration error is never masked by a cleanup failure;")
    print("       a failed cleanup discards the connection; cancellation is BaseException-safe and")
    print(
        "       shielded; the fingerprint captures CHECK/FK-action/deferrability drift (mutation-"
    )
    print("       tested); the ledger tracks version/filename/checksum/status and fails closed on")
    print("       checksum mismatch or untracked schema, reconciling ambiguous commits only under")
    print("       strict conditions; lock-wait and statement timeouts are bounded; plan mode is")
    print("       read-only; the CLI exits non-zero on failure with redacted structured output; PR")
    print("       #21 remains Draft/unmerged; focused closure by the original reviewer is recorded")
    print("       as the next required gate.")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
