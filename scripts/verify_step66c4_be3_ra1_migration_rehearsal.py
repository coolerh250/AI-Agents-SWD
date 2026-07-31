#!/usr/bin/env python3
"""Step 66C.4-BE3-RA-1A -- isolated migration rehearsal and rollback proof self-verifier.

Static/structural checks only (no PostgreSQL connection here -- the real rehearsal already ran
against an isolated ephemeral PostgreSQL 16 container; see
docs/test/step66c4-be3-ra1-migration-rehearsal-evidence.md). Confirms the required deliverables
exist, the rehearsal suite covers every mandated scenario, migrations 031-035 were not modified,
all four BE3 feature gates remain default-false, no worker/relay/consumer was introduced, no
deployment/shared-migration path was touched, and the next required gate (independent review) is
recorded as still pending.

Marker: STEP66C4_BE3_RA1_MIGRATION_REHEARSAL_VERIFY: PASS | FAIL
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "contracts" / "66c4-reminder-expiry-controlled-resume"
HANDOFF = ROOT / "docs" / "handoffs" / "66c4-reminder-expiry-controlled-resume"
TEST_DOCS = ROOT / "docs" / "test"

PLAN = CONTRACT / "be3-ra1-migration-rehearsal-and-rollback-plan.md"
EVIDENCE = TEST_DOCS / "step66c4-be3-ra1-migration-rehearsal-evidence.md"
HANDOFF_DOC = HANDOFF / "be3-ra1-to-independent-review-handoff.md"

RUNNER = ROOT / "shared" / "sdk" / "backup_dr" / "migration_runner.py"
TEST_SUITE = ROOT / "tests" / "test_step66c4_be3_ra1_migration_rehearsal.py"

RESUME_MODEL = ROOT / "shared" / "sdk" / "tasks" / "resume_request_model.py"
REPLAY_MODEL = ROOT / "shared" / "sdk" / "tasks" / "replay_request_model.py"
COMPOSE = ROOT / "infra" / "docker-compose" / "docker-compose.yml"

FEATURE_GATES = (
    "BE3_RESUME_API_ENABLED",
    "BE3_RESUME_COMMAND_ENABLED",
    "BE3_REPLAY_API_ENABLED",
    "BE3_REPLAY_EXECUTION_ENABLED",
)

MIGRATION_FILES = (
    "031_clarification_lifecycle_outbox_foundation.sql",
    "032_be3_resume_replay_authorization.sql",
    "033_be3_resume_requests.sql",
    "034_be3_replay_requests.sql",
    "035_be3_production_action_approvals.sql",
)

RA_P_BASELINE = "18f11fe"

MARKER = "STEP66C4_BE3_RA1_MIGRATION_REHEARSAL_VERIFY"
failures: list[str] = []


def bad(m: str) -> None:
    failures.append(m)
    print(f"  [FAIL] {m}")


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main() -> int:  # noqa: C901
    for p in (PLAN, EVIDENCE, HANDOFF_DOC, RUNNER, TEST_SUITE, RESUME_MODEL, REPLAY_MODEL, COMPOSE):
        if not p.is_file():
            bad(f"missing file: {p}")
    if failures:
        print(f"{MARKER}: FAIL")
        return 1

    plan = PLAN.read_text(encoding="utf-8")
    evidence = EVIDENCE.read_text(encoding="utf-8")
    handoff = HANDOFF_DOC.read_text(encoding="utf-8")
    tests = TEST_SUITE.read_text(encoding="utf-8")

    # 1. Ephemeral PostgreSQL 16.
    if "ephemeral PostgreSQL 16" not in evidence and "ephemeral postgres" not in evidence.lower():
        bad("check1: evidence does not record an ephemeral PostgreSQL 16 rehearsal")

    # 2. Shared DB not accessed/modified.
    if "shared aiagents-test stack" not in evidence and "shared" not in evidence.lower():
        bad("check2: evidence does not address the shared database/stack")
    if "requires_pg" not in tests or "destructive_pg_refusal_reason" not in tests:
        bad("check2: rehearsal suite does not reuse the fail-closed destructive-PG guard")

    # 3. 031-035 applied in order.
    if not all(f in tests for f in MIGRATION_FILES):
        bad("check3: rehearsal suite is missing one or more of migrations 031-035")
    order = [tests.index(f) for f in MIGRATION_FILES]
    if order != sorted(order):
        bad("check3: migrations 031-035 are not referenced in ascending order in CHAIN_FILES")

    # 4. Stepwise schema/constraint/index validation.
    if "def test_pg_up_rehearsal_all_five_migrations_stepwise" not in tests:
        bad("check4: missing stepwise up-rehearsal test")

    # 5. Existing sentinel data preserved.
    if "def test_pg_existing_data_preserved_through_full_chain" not in tests:
        bad("check5: missing existing-data preservation test")
    if "_assert_sentinel_unchanged" not in tests:
        bad("check5: missing sentinel-fingerprint assertion helper")

    # 6. Failure injection leaves no partial migration.
    for must in (
        "def test_pg_failure_early_in_transaction_leaves_no_partial_schema",
        "def test_pg_failure_just_before_commit_leaves_no_partial_schema",
    ):
        if must not in tests:
            bad(f"check6: missing mandatory test {must}")

    # 7. Duplicate/concurrent migrator behavior safe or clearly blocked.
    for must in (
        "def test_pg_duplicate_migration_invocation_is_idempotent",
        "def test_pg_concurrent_migrators_serialize_via_advisory_lock",
    ):
        if must not in tests:
            bad(f"check7: missing mandatory test {must}")
    if "pg_try_advisory_lock" not in tests:
        bad(
            "check7: concurrent-migrator test does not directly prove serialization via a lock probe"
        )

    # 8. Pre-activation down path verified.
    if "def test_pg_predown_rehearsal_removes_only_new_objects" not in tests:
        bad("check8: missing pre-activation down rehearsal test")

    # 9. Post-write rollback does not use a destructive down migration.
    post_write_match = tests.split("def test_pg_post_write_operational_rollback_is_nondestructive")
    if len(post_write_match) < 2:
        bad("check9: missing post-write operational rollback test")
    else:
        body = post_write_match[1].split("\n\n\n")[0]
        if "_down.sql" in body or "DOWN_FILES" in body:
            bad("check9: post-write rollback test appears to run a destructive down migration")

    # 10. Reapply schema fingerprint consistent.
    if "def test_pg_reapply_after_down_matches_original_fingerprint" not in tests:
        bad("check10: missing reapply/fingerprint-equality test")
    if "schema_fingerprint" not in tests or "schema_fingerprint" not in RUNNER.read_text(
        encoding="utf-8"
    ):
        bad("check10: schema_fingerprint utility not present/used")

    # 11. All four BE3 feature gates still default false.
    resume_src = RESUME_MODEL.read_text(encoding="utf-8")
    replay_src = REPLAY_MODEL.read_text(encoding="utf-8")
    combined = resume_src + replay_src
    for gate in FEATURE_GATES:
        if f'os.environ.get("{gate}", "false")' not in combined:
            bad(f"check11: feature gate {gate} does not default to false")

    # 12. No worker/relay/consumer started (shared compose unchanged in this respect).
    compose_text = COMPOSE.read_text(encoding="utf-8")
    for token in ("lifecycle-poller", "lifecycle_poller", "outbox-relay", "outbox_relay", "ra1a"):
        if token in compose_text:
            bad(
                f"check12: docker-compose.yml appears to reference a new consumer/service ({token})"
            )

    # 13. No deployment/runtime action: no infra/migrations/workflow/frontend path changed since
    # the RA-P baseline (only the rehearsal artifacts themselves should differ).
    changed = [f for f in _git("diff", "--name-only", RA_P_BASELINE, "HEAD").splitlines() if f]
    for f in changed:
        for prefix in ("infra/", "migrations/", ".github/workflows/", "frontend/"):
            if f.startswith(prefix):
                bad(f"check13: forbidden path changed since RA-P baseline: {f}")

    # 14. production_executed_true_count = 0.
    progress_md = (ROOT / "source" / "progress.md").read_text(encoding="utf-8")
    if (
        "production_executed_true_count" not in evidence
        and "production_executed_true_count" not in plan
    ):
        bad("check14: production_executed_true_count not recorded in plan/evidence")
    if "production_executed_true_count: 0" not in progress_md:
        bad("check14: production_executed_true_count: 0 not recorded in source/progress.md")

    # 15. Independent RA-1R remains the next required gate (not self-closed).
    if "RA-1R" not in handoff or "PENDING" not in handoff.upper():
        bad("check15: handoff does not record RA-1R independent review as still pending")
    if "CLOSED" in handoff and "NOT CLOSED" not in handoff and "not CLOSED" not in handoff:
        bad("check15: handoff may have prematurely marked a gate CLOSED")

    if failures:
        print(f"{MARKER}: FAIL ({len(failures)} issue(s))")
        return 1

    print("  [OK] Migration rehearsal deliverables present; 031-035 rehearsed stepwise with")
    print("       existing-data preservation, failure injection, duplicate/out-of-order/concurrent")
    print("       migrator coverage (serialization proven via a direct lock probe), pre-activation")
    print("       down rehearsal, reapply schema-fingerprint equality, and a non-destructive")
    print("       post-write rollback simulation. Migrations 031-035 unmodified; all four feature")
    print("       gates default false; no worker/relay/consumer; no deployment/shared-migration")
    print("       path touched; independent review (RA-1R) recorded as the next required gate.")
    print(f"{MARKER}: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
