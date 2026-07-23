# Step 66C.4-BE1-R1-R — Migration, Fixture Safety and Test Closure Review

> Independent closure review of the migration up/down/reapply safety, the fail-closed PostgreSQL
> fixture guard, and the mandatory-evidence policy at `0bb9944`. Reproduced on an isolated ephemeral
> test PostgreSQL 16.

## 9. Migration closure

Migration `031_clarification_lifecycle_outbox_foundation.sql` was AMENDED IN PLACE (031 was never
merged to main and never applied to a shared runtime). Reviewer applied 029→030→031 from baseline on
isolated PostgreSQL and confirmed:

- Six additive NULLABLE lifecycle columns on `operator_clarification_requests`
  (`reminder_sent_at`, `expired_at`, `resume_eligible_at`, `resume_requested_at`,
  `resume_requested_by`, `resume_authorized_at`) — nullable, no default ⇒ **no table rewrite**, no
  backfill; legacy rows remain valid (the `chk_ocr_resume_authorized_requires_eligible` constraint
  evaluates to true when all six are NULL).
- `clarification_lifecycle_outbox` created with the durability columns
  (`available_at`/`dead_at`/`last_error`), constraints and indexes.
- `due_at NOT NULL` on `operator_clarification_requests` is preserved (verified by the
  `test_pg_due_at_remains_not_null` regression and by direct inspection of migration 030).
- up → down → reapply is deterministic: the down migration drops ONLY BE1-added objects (the outbox
  table with its indexes/constraints, the two partial indexes, the ordering CHECK, the six columns);
  reapply yields the identical final schema. The remediation suite's
  `test_pg_migration_up_down_reapply_is_deterministic` and the BE1 data-model suite's
  `test_pg_migration_creates_schema_and_rolls_back` / `test_pg_existing_rows_remain_intact_after_migration`
  all pass on real PostgreSQL (0 skipped).

### `DEFAULT statement_timestamp()` on `available_at`

Assessed contract-correct. `available_at` lives on the brand-new `clarification_lifecycle_outbox`
table created fresh by 031, so its DEFAULT applies only to rows inserted after the table exists and
causes **no legacy rewrite** (there are no pre-existing outbox rows). Setting the earliest claim time
to statement time at insert makes a row immediately claim-eligible and is consistent with the
future caller-owned transaction semantics (§7.3A / api-and-event-contract.md 11.3): the value is a
per-statement reading, and BE2's relay pushes it forward by the persisted backoff on transient
failure. It matches `data-model-contract.md` line "available_at TIMESTAMPTZ NOT NULL DEFAULT
statement_timestamp()".

Old code + migrated schema works (additive nullable columns are invisible to pre-R1 readers);
remediated code + migrated schema works (verified by the full R1 PostgreSQL suite).

## 10. PostgreSQL test-fixture safety

`tests/step66c4_pg_safety.py :: destructive_pg_refusal_reason()` is FAIL-CLOSED: it requires
`STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS=1`, a set/parseable `BE1_TEST_DATABASE_URL`, a DB name matching
an isolated-test pattern (`step66c4_*`, `ephemeral_*`, `*_test`), rejection of a
shared/production name list and shared hostnames, and "refuse on unparseable". Reviewer negative
tests (executed via the remediation suite's guard tests, all passing):

```text
(1) no opt-in                    => refuse ("not opted in")
(2) unconventional name 'mydb'   => refuse ("does not match isolated-test naming")
(3) shared-like names (aiagents, aiagents_test, postgres, production, staging, shared) => refuse
(4) invalid DSN 'not-a-dsn' / empty DB name => refuse
(5) approved ephemeral 'step66c4_*' + opt-in => execute
```

The guard "never allows on error" — an unparseable DSN or an unevaluable check refuses rather than
dropping anything. Reviewer's own isolated ephemeral database name matched `step66c4_*`; no shared
runtime database was touched.

### Mandatory evidence policy

The PostgreSQL tier is MANDATORY, not silently skippable in the reviewer's run. With opt-in + an
approved DSN set, the reviewer executed:

```text
tests/test_step66c4_be1_r1_remediation.py                       44 passed, 0 skipped, 0 failed
tests/test_step66c4_be1_data_model_deadline_outbox.py           15 passed, 0 skipped, 0 failed
tests/test_step66c4_be1_r1_independent_closure_review.py (mine) 22 passed, 0 skipped, 0 failed
```

Every `test_pg_*` case executed (verified by `-v` names, not skip markers). Had the mandatory suite
silently skipped, closure would NOT pass; it did not.

## 11 (test quality) Concurrency and boundary tests

The remediation suite includes a real two-connection concurrency barrier
(`test_pg_concurrent_answer_with_barrier_exactly_one_wins`,
`test_pg_loser_blocks_until_winner_commits_then_reads_final_state`), a non-tautological strict-equality
boundary, a transaction-crossing regression, and atomic state+outbox insert. All pass on real
PostgreSQL. The original defect-pinning tests are correctly NOT copied onto the feature branch (they
assert defects PRESENT and remain preserved at `f5417f4`); the R1 tests and the reviewer's closure
tests assert the FIXED state.

## Verdict

**Migration / fixture / test policy: SAFE and sufficient.** Migration is additive with a tested
symmetric rollback and deterministic reapply; `due_at NOT NULL` preserved; the destructive-fixture
guard is fail-closed; mandatory PostgreSQL evidence ran 0-skipped / 0-failed.

_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
