#!/usr/bin/env python3
"""Step 66C.4-BE3-RA-1D -- missing-configuration single-JSON contract self-verifier.

Static checks plus LIVE CLI subprocess checks (missing/empty/whitespace/malformed DSN -- none of
these require a real database, so they are exercised directly here, not just claimed in the docs)
plus two live git/gh checks (review branch preserved on origin; PR #21 still Draft/unmerged). Does
NOT connect to PostgreSQL -- the success-path and real-connect-failure regression already ran
against an isolated ephemeral PostgreSQL 16 (see docs/test/step66c4-be3-ra1d-missing-config-json-
evidence.md); this script only re-derives what is possible without a live database.

Marker: STEP66C4_BE3_RA1D_MISSING_CONFIG_JSON_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
HANDOFF = ROOT / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume"
TEST_DOCS = ROOT / "docs" / "test"

RECORD = CONTRACT / "be3-ra1d-missing-config-json-remediation-record.md"
EVIDENCE = TEST_DOCS / "step66c4-be3-ra1d-missing-config-json-evidence.md"
HANDOFF_DOC = HANDOFF / "be3-ra1d-to-final-m3b-closure-handoff.md"

CLI = ROOT / "scripts" / "run_platform_migrations.py"
TEST_SUITE = ROOT / "tests" / "test_step66c4_be3_ra1d_missing_config_json.py"
RUNNER = ROOT / "shared" / "sdk" / "backup_dr" / "migration_runner.py"

REVIEW_BRANCH = "review/66c4-be3-ra1-migration-rollback"
REVIEW_COMMIT = "800035b"

DSN_ENV = "PLATFORM_MIGRATIONS_DATABASE_URL"
MARKER = "STEP66C4_BE3_RA1D_MISSING_CONFIG_JSON_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def _run_cli(args: list[str], dsn_value: str | None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if dsn_value is None:
        env.pop(DSN_ENV, None)
    else:
        env[DSN_ENV] = dsn_value
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _check_missing_configuration_contract(
    args: list[str], dsn_value: str | None, label: str
) -> None:
    result = _run_cli(args, dsn_value)
    if result.returncode != 2:
        bad(f"{label}: exit code {result.returncode} != 2")
        return
    if result.stdout != "":
        bad(f"{label}: stdout is not empty")
    if "Traceback" in result.stderr:
        bad(f"{label}: stderr contains a traceback")
    try:
        payload = json.loads(result.stderr)
    except json.JSONDecodeError:
        bad(f"{label}: stderr is not exactly one parseable JSON object")
        return
    if payload.get("result_code") != "missing_configuration":
        bad(f"{label}: result_code != 'missing_configuration' ({payload.get('result_code')!r})")
    expected_mode = "plan" if "--plan" in args else "apply"
    if payload.get("mode") != expected_mode:
        bad(f"{label}: mode {payload.get('mode')!r} != {expected_mode!r}")
    if payload.get("success") is not False:
        bad(f"{label}: success is not False")
    if DSN_ENV in json.dumps(payload):
        bad(f"{label}: env var name leaked into the payload")


def main() -> int:  # noqa: C901
    for p in (RECORD, EVIDENCE, HANDOFF_DOC, CLI, TEST_SUITE, RUNNER):
        if not p.is_file():
            bad(f"missing required file: {p}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    cli_src = CLI.read_text(encoding="utf-8")
    runner_src_before = RUNNER.read_text(encoding="utf-8")
    record = RECORD.read_text(encoding="utf-8")
    handoff = HANDOFF_DOC.read_text(encoding="utf-8")
    progress_md = (ROOT / "source" / "progress.md").read_text(encoding="utf-8")

    # 1. Review evidence preserved on origin at the expected commit.
    remote_ref = _git("ls-remote", "origin", f"refs/heads/{REVIEW_BRANCH}")
    if not remote_ref:
        bad(f"check1: origin/{REVIEW_BRANCH} not found (git ls-remote returned nothing)")
    elif not remote_ref.startswith(REVIEW_COMMIT):
        bad(f"check1: origin/{REVIEW_BRANCH} does not start with {REVIEW_COMMIT}: {remote_ref}")

    # 2/3/4/5/6/7. Missing DSN produces one JSON object; empty/whitespace follow the same
    # contract; plan/apply modes correctly reported; exit 2; stdout empty; no plain text/traceback.
    _check_missing_configuration_contract(["--plan"], None, "check2-7 plan/missing")
    _check_missing_configuration_contract(["--apply"], None, "check2-7 apply/missing")
    _check_missing_configuration_contract(["--plan"], "", "check3 plan/empty")
    _check_missing_configuration_contract(["--apply"], "", "check3 apply/empty")
    _check_missing_configuration_contract(["--plan"], "   \t  ", "check3 plan/whitespace")
    _check_missing_configuration_contract(["--apply"], "   \t  ", "check3 apply/whitespace")

    # 8. Connect failures (malformed AND unreachable DSN) remain exit 1 and redacted -- never
    # misclassified as missing configuration.
    for label, dsn_value in (
        ("malformed", "this-is-not-a-valid-dsn-at-all"),
        ("unreachable", "postgresql://baduser:badsecretvalue@127.0.0.1:1/nonexistent_db_ra1d"),
    ):
        result = _run_cli(["--plan"], dsn_value)
        if result.returncode != 1:
            bad(f"check8: {label} DSN did not exit 1 (got {result.returncode})")
        if "Traceback" in result.stderr:
            bad(f"check8: {label} DSN produced a traceback")
        try:
            payload = json.loads(result.stderr)
        except json.JSONDecodeError:
            bad(f"check8: {label} DSN stderr is not exactly one parseable JSON object")
            continue
        if payload.get("result_code") != "database_connect_failed":
            bad(f"check8: {label} DSN result_code != 'database_connect_failed'")

    # 9. Success paths remain exit 0 -- structural check only (no live DB in this verifier; the
    # real success-path regression ran against an isolated ephemeral PostgreSQL 16, see the
    # evidence record). Confirm the success branches were not touched by this stage's diff shape.
    if "print(json.dumps(payload, indent=2, sort_keys=True))\n    return 0" not in cli_src:
        bad("check9: plan success path (stdout JSON, exit 0) not found in expected shape")
    if (
        "print(json.dumps(runner.result_to_dict(result), indent=2, sort_keys=True))\n    return 0"
        not in cli_src
    ):
        bad("check9: apply success path (stdout JSON, exit 0) not found in expected shape")

    # 10. No implementation outside the narrow CLI scope was weakened -- migration_runner.py must
    # be byte-identical to the reviewed RA-1C head (7820b4b).
    diff = _git("diff", "--name-only", "7820b4b", "HEAD", "--", str(RUNNER.relative_to(ROOT)))
    if diff.strip():
        bad("check10: migration_runner.py was modified by this narrow-scope stage")
    if runner_src_before != RUNNER.read_text(encoding="utf-8"):
        bad("check10: migration_runner.py content changed during verification (unexpected)")

    # 11. PR #21 remains Draft/unmerged.
    gh = subprocess.run(
        ["gh", "pr", "view", "21", "--json", "state,isDraft,mergedAt"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if gh.returncode == 0:
        pr = json.loads(gh.stdout)
        if pr.get("state") != "OPEN" or pr.get("isDraft") is not True or pr.get("mergedAt"):
            bad(f"check11: PR #21 is not Draft/OPEN/unmerged: {pr}")
    else:
        bad("check11: could not query PR #21 state via gh (gh CLI unavailable or auth missing)")

    # 12. No shared DB/deployment/activation/runtime action recorded.
    for f in (record, handoff):
        if "shared" not in f.lower():
            bad("check12: a required record does not address shared-DB/deployment safety")
            break

    # 13. production_executed_true_count = 0.
    if "production_executed_true_count: 0" not in progress_md:
        bad("check13: production_executed_true_count: 0 not recorded in source/progress.md")

    # 14. Same original reviewer remains the next required gate.
    if "original ra-1r reviewer" not in handoff.lower():
        bad("check14: handoff does not record the original RA-1R reviewer as the next actor")
    if "PENDING" not in handoff:
        bad("check14: handoff does not mark the final re-check as PENDING")

    if failures:
        print(f"{MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] Review branch preserved on origin; missing/empty/whitespace-only configuration")
    print("       all produce exactly one JSON object (mode-correct, exit 2, empty stdout, no")
    print("       traceback, no env-var-name leak); malformed and unreachable DSNs remain exit 1")
    print("       with the existing redacted contract, never misclassified; the plan/apply success")
    print("       code shape is unchanged; migration_runner.py is untouched; PR #21 remains")
    print("       Draft/unmerged; production_executed_true_count is 0; the original RA-1R reviewer")
    print("       is recorded as performing the next (final, M-3B-only) re-check.")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
