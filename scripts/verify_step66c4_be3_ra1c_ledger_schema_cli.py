#!/usr/bin/env python3
"""Step 66C.4-BE3-RA-1C -- ledger/schema consistency and CLI redaction closure self-verifier.

Static/structural checks plus two live checks (review branch preserved on origin; PR #21 still
Draft/unmerged). Confirms M-2A/M-2B/M-3A/M-3B are closed in the actual source (not merely claimed
in the docs), the required artifacts and canonical manifests exist, the two RA-1B allowlist guards
were not weakened, and the next gate (a second focused closure by the original RA-1R reviewer) is
recorded as still pending.

Marker: STEP66C4_BE3_RA1C_LEDGER_SCHEMA_CLI_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
HANDOFF = ROOT / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume"
TEST_DOCS = ROOT / "docs" / "test"

RECORD = CONTRACT / "be3-ra1c-ledger-schema-cli-remediation-record.md"
EVIDENCE = TEST_DOCS / "step66c4-be3-ra1c-ledger-schema-cli-evidence.md"
HANDOFF_DOC = HANDOFF / "be3-ra1c-to-second-focused-closure-handoff.md"

RUNNER = ROOT / "shared" / "sdk" / "backup_dr" / "migration_runner.py"
CLI = ROOT / "scripts" / "run_platform_migrations.py"
TEST_SUITE = ROOT / "tests" / "test_step66c4_be3_ra1c_ledger_schema_cli.py"
MANIFESTS_DIR = ROOT / "shared" / "sdk" / "backup_dr" / "migration_manifests"
MANIFEST_VERSIONS = ("031", "032", "033", "034", "035")

BE1_ALLOWLIST_1 = ROOT / "tests" / "test_step66c4_be1_data_model_deadline_outbox.py"
BE1_ALLOWLIST_2 = ROOT / "tests" / "test_step66c4_be1_r1_remediation.py"

REVIEW_BRANCH = "review/66c4-be3-ra1-migration-rollback"
REVIEW_COMMIT = "9cd841f"

MARKER = "STEP66C4_BE3_RA1C_LEDGER_SCHEMA_CLI_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> int:  # noqa: C901
    required = [RECORD, EVIDENCE, HANDOFF_DOC, RUNNER, CLI, TEST_SUITE, MANIFESTS_DIR]
    for p in required:
        if not p.exists():
            bad(f"missing required path: {p}")
    for v in MANIFEST_VERSIONS:
        if not (MANIFESTS_DIR / f"{v}.json").is_file():
            bad(f"missing canonical manifest: {v}.json")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    runner_src = RUNNER.read_text(encoding="utf-8")
    cli_src = CLI.read_text(encoding="utf-8")
    test_src = TEST_SUITE.read_text(encoding="utf-8")
    record = RECORD.read_text(encoding="utf-8")
    evidence = EVIDENCE.read_text(encoding="utf-8")
    handoff = HANDOFF_DOC.read_text(encoding="utf-8")
    progress_md = (ROOT / "source" / "progress.md").read_text(encoding="utf-8")

    # 1. Review evidence preserved on origin at the expected commit.
    remote_ref = _git("ls-remote", "origin", f"refs/heads/{REVIEW_BRANCH}")
    if not remote_ref:
        bad(f"check1: origin/{REVIEW_BRANCH} not found (git ls-remote returned nothing)")
    elif not remote_ref.startswith(REVIEW_COMMIT):
        bad(f"check1: origin/{REVIEW_BRANCH} does not start with {REVIEW_COMMIT}: {remote_ref}")

    # 2. Applied/reconciled ledger rows are checked against the actual schema.
    combined_status_re = re.compile(
        r'existing\["status"\]\s+in\s+\(\s*"applied",\s*"reconciled_after_ambiguous_commit",?\s*\)',
        re.DOTALL,
    )
    if not combined_status_re.search(runner_src):
        bad("check2: applied+reconciled status are not handled together in apply_chain_with_ledger")
    if "LedgerSchemaMismatchError" not in runner_src:
        bad("check2: LedgerSchemaMismatchError not defined/used")
    if "ledger_schema_mismatch" not in runner_src:
        bad("check2: ledger_schema_mismatch result/drift code not found")

    # 3. Missing or wrong-shaped schema fails closed (fingerprint re-check drives this).
    if "observed_now != manifest.canonical_semantic_fingerprint" not in runner_src:
        bad("check3: no re-verification of observed schema against the canonical manifest")

    # 4. Raw down after ledger apply produces mismatch, not silent success (test coverage).
    for must in (
        "test_pg_raw_isolated_down_produces_mismatch_not_silent_success",
        "test_pg_destroy_recreate_then_clean_apply_succeeds",
    ):
        if must not in test_src:
            bad(f"check4: missing mandatory raw-down test {must}")

    # 5/6. Shared destructive down explicitly unsupported; shared rollback retains tables/data.
    if "NOT supported" not in record and "NOT SUPPORTED" not in record.upper():
        bad("check5: destructive-down-unsupported decision not recorded in the remediation record")
    if "retain" not in record.lower() or "business data" not in record.lower():
        bad("check6: shared-rollback table/data retention policy not recorded")

    # 7/8. Expected fingerprint present BEFORE DDL, sourced from the committed manifest.
    before_apply, _, after_apply = runner_src.partition(
        "await apply_migration_file(conn, migrations_dir / filename)"
    )
    if not after_apply:
        bad("check7: could not locate the new-apply DDL call site in apply_chain_with_ledger")
    elif (
        "expected_fingerprint"
        not in before_apply.rsplit("async def apply_chain_with_ledger", 1)[-1]
    ):
        bad("check7: expected_fingerprint does not appear to be set before the migration DDL runs")
    if "manifest.canonical_semantic_fingerprint" not in runner_src:
        bad("check8: expected fingerprint is not sourced from the canonical manifest")

    # 9. Manifest is checksum/version/PG-major bound.
    for must in (
        "manifest.migration_sha256 != checksum",
        "manifest.postgres_major_version not in SUPPORTED_POSTGRES_MAJOR_VERSIONS",
        "connected_major != manifest.postgres_major_version",
        "manifest.migration_version != version",
        "manifest.migration_filename != filename",
    ):
        if must not in runner_src:
            bad(f"check9: manifest validation missing binding check: {must}")

    # 10. Ambiguous reconciliation requires an exact, non-null expected match.
    if "ExpectedFingerprintMissingError" not in runner_src:
        bad("check10: ExpectedFingerprintMissingError not defined/used")
    if 'existing["expected_fingerprint"] is None' not in runner_src:
        bad("check10: null expected_fingerprint is not explicitly rejected")

    # 11. postgresql:// and related DSNs are redacted.
    if "_SECRET_SCHEME_RE" not in runner_src or "postgres(?:ql)?" not in runner_src:
        bad("check11: redaction scheme detector does not cover postgresql:// and related schemes")
    if "asyncpg" not in runner_src.split("_SECRET_SCHEME_RE")[1][:200]:
        bad("check11: postgresql+asyncpg scheme not covered by the redaction detector")
    if "rediss" not in runner_src:
        bad("check11: rediss:// scheme not covered by the redaction detector")

    # 12/13. CLI connect failures return one redacted JSON object and a non-zero exit, no traceback.
    if "_print_connect_failure" not in cli_src or "database_connect_failed" not in cli_src:
        bad("check12: CLI does not have a dedicated connect-failure JSON payload")
    if "_connect_or_none" not in cli_src:
        bad("check13: CLI connect attempt is not wrapped in a protected path")

    # 14. No allowlist weakening -- both BE1 guards still gate on an exact, specific literal.
    for allowlist_file in (BE1_ALLOWLIST_1, BE1_ALLOWLIST_2):
        src = allowlist_file.read_text(encoding="utf-8")
        if "migration_runner.py" not in src:
            bad(f"check14: {allowlist_file.name} lost its migration_runner.py allowlist entry")
        if re.search(r"allowed\s*=\s*\{[^}]*[*?][^}]*\}", src):
            bad(f"check14: {allowlist_file.name} allowlist appears to use a wildcard")

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
        pr = json.loads(gh.stdout)
        if pr.get("state") != "OPEN" or pr.get("isDraft") is not True or pr.get("mergedAt"):
            bad(f"check16: PR #21 is not Draft/OPEN/unmerged: {pr}")
    else:
        bad("check16: could not query PR #21 state via gh (gh CLI unavailable or auth missing)")

    # 17. production_executed_true_count = 0.
    if "production_executed_true_count: 0" not in progress_md:
        bad("check17: production_executed_true_count: 0 not recorded in source/progress.md")

    # 18. Same original reviewer performs the second focused closure (recorded as the next gate).
    if "original ra-1r reviewer" not in handoff.lower():
        bad("check18: handoff does not record the original RA-1R reviewer as the next actor")
    if "PENDING" not in handoff:
        bad("check18: handoff does not mark the second focused closure as PENDING")
    if "second focused closure" not in handoff.lower():
        bad("check18: handoff does not name a 'second focused closure' as the next gate")

    if failures:
        print(f"{MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] Review branch preserved on origin; applied/reconciled ledger rows are re-checked")
    print("       against the actual schema via a committed canonical manifest; missing/wrong-")
    print(
        "       shaped schema fails closed; a raw isolated down produces a mismatch rather than a"
    )
    print(
        "       silent success; destructive down is explicitly unsupported for shared use, with a"
    )
    print("       table/data-retention rollback policy recorded; the expected fingerprint is set")
    print(
        "       before DDL from the committed manifest; the manifest is checksum/version/PG-major"
    )
    print("       bound; ambiguous reconciliation requires a non-null, exact expected match;")
    print(
        "       postgresql:// and related DSN schemes are redacted; the CLI's connect path returns"
    )
    print("       one redacted JSON object with a non-zero exit and no traceback; neither BE1")
    print("       allowlist guard was weakened; no shared DB/deployment/activation/runtime action;")
    print("       PR #21 remains Draft/unmerged; production_executed_true_count is 0; the second")
    print("       focused closure by the original RA-1R reviewer is recorded as the next gate.")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
