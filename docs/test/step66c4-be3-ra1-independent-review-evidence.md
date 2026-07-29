# Step 66C.4-BE3-RA-1R — Independent Review Test & Evidence Record

> **Independent evidence record. All PostgreSQL work ran on an isolated ephemeral PostgreSQL 16.14
> container on an internal test runtime, on a container name and port distinct from the
> implementation session's, destroyed after the review. No shared database was touched. NOT FOR
> MERGE / NOT deployed / NOT activated.**

## Markers

```text
STEP66C4_BE3_RA1_INDEPENDENT_REVIEW_VERIFY: PASS      (process/artifacts complete)
RA1_TECHNICAL_VERDICT: REMEDIATION_REQUIRED           (independent technical judgment)
```

## Environment

```text
Runtime:      internal test runtime; isolated ephemeral PostgreSQL 16.14 container on a dedicated
              port (distinct from the implementation session's), created for this review and
              destroyed afterward. Isolated DB name matches the fail-closed guard's
              *_test/ephemeral_* convention (never committed).
Guard opt-in: STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS=1 with an isolated DSN (never committed); the same
              fail-closed guard (tests/step66c4_pg_safety.py) every Step 66C.4 PG test uses.
Worktrees:    two detached worktrees on the internal test runtime — one at the reviewed feature head
              27184b5, one at the reviewed baseline 18f11fe — separate from the implementation
              session's tree; removed after the review.
Reviewer:     did NOT participate in RA-1A. Conclusions re-derived from committed SQL, the runner
              source, and direct PostgreSQL experiments — not from RA-1A's self-verifier or records.
```

## Independent test suite

`tests/test_step66c4_be3_ra1_independent_review.py` — **14 passed, 0 skipped, 0 failed** on real
PostgreSQL 16. This suite is a faithful characterization: it asserts the ACTUAL observed behavior,
including behavior the review flags as a defect for future shared-apply, so it passes against the
code under review while the review document interprets it.

```text
test_rev_full_chain_stepwise_and_data_preserved              PASS
test_rev_apply_chain_locked_success_releases_lock            PASS
test_rev_apply_chain_locked_failure_path_characterization    PASS  (characterizes H-1)
test_rev_failed_migration_then_explicit_rollback_reuses_connection  PASS
test_rev_session_lock_released_on_all_teardown_paths         PASS  (Python exc / cancellation / forced kill / close)
test_rev_concurrent_migrators_delay_and_midchain_failure     PASS  (injected pg_sleep + mid-chain failure, per spec §8)
test_rev_out_of_order_fails_closed                           PASS
test_rev_duplicate_invocation_idempotent_and_ambiguous_reapply  PASS
test_rev_foreign_wrong_shaped_object_not_silently_accepted   PASS
test_rev_fingerprint_mutation_detection                      PASS  (5/6 detected; FK-action + CHECK-expr blind spots characterized as M-1)
test_rev_predown_reapply_fingerprint_equal                   PASS
test_rev_post_write_nondestructive_and_old_version_compat    PASS
test_rev_guard_not_bypassed                                  PASS
test_rev_runner_source_has_no_credential_logging             PASS
```

## Independent re-derivation of RA-1A's own suite

`tests/test_step66c4_be3_ra1_migration_rehearsal.py` re-run unchanged on this review's independent
ephemeral database: **12 passed, 0 skipped**. RA-1A's own 12-pass claim reproduces.

## Key empirical results (raw)

Runner failure path (`apply_chain_locked` on a deliberately failing chain, no real file modified):

```text
propagated exception                       = InFailedSQLTransactionError   (the finally-unlock's own error)
real migration error surfaced?             = NO (masked)
advisory lock still held (conn open)?      = YES (runner did not release it on failure)
connection reusable w/o external ROLLBACK? = NO (left aborted)
partial half-built table survived?         = NO (file's own txn rolled back)
lock released after connection close?      = YES (session teardown only)
```

Fingerprint mutation detection:

```text
drop index                         -> DETECTED
change partial-index predicate     -> DETECTED
change column nullability          -> DETECTED
add CHECK (new constraint name)    -> DETECTED
change column DEFAULT              -> DETECTED
change FK ON DELETE (same name)    -> NOT DETECTED   (M-1)
change CHECK expression (same name)-> NOT DETECTED   (M-1)
determinism (recompute same schema)-> byte-structurally identical
```

Data preservation through full 031-035 chain: sentinel task full-row equality; ctid unchanged (no
physical rewrite); all six 031-added columns NULL on the legacy row (no backfill); pre-031
clarification columns unchanged. Foreign wrong-shaped `resume_replay_authorizations (id int)` makes
real 032's index creation fail with `UndefinedColumnError` (never silently accepted). Blind reapply
of a real migration file twice -> identical fingerprint (ambiguous-commit safe).

## Regression (independently re-run on both commits)

```text
baseline 18f11fe (step66c4-tagged):  3 failed / 314 passed / 5 skipped
feature  27184b5 (step66c4-tagged):  3 failed / 340 passed / 5 skipped   (314 + 12 RA-1A + 14 review)
```

The three failures are identical (byte-for-byte signatures) on both commits and none bear on RA-1A
migration correctness (details, including the independently-evaluated PATH-dependent `python`
failure, in the review document's Regression section). No skip/xfail marker was weakened.

## Quality gates (this review's two added Python files)

```text
ruff check:            PASS
black --check:         PASS
mypy:                  PASS (no issues)
git diff --check:      PASS (no whitespace errors)
secret / internal-identifier scan of committed review files: PASS (neutral labels only)
scripts/verify_step66c4_be3_ra1_independent_review.py: PASS (process marker)
```

## Safety boundary

```text
Shared database applied:            NONE
Deployment:                         NONE
Feature gates enabled:              NONE (all four BE3 gates remain default-false)
Worker/relay/consumer started:      NONE
Runtime resume/replay executed:     NONE
Files under review modified:        NONE (migration_runner.py, migrations/*, RA-1A suite unchanged)
PR #21:                             Draft/OPEN/unmerged before and after (unchanged)
production_executed_true_count: 0
```

---
_Non-production only. No production action. No production data. Neutral labels only — no internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets ("internal test runtime", "isolated ephemeral PostgreSQL 16")._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
