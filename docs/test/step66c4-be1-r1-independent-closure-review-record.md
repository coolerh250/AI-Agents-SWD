# Step 66C.4-BE1-R1-R — Independent Closure Review Test Record

> Raw verification evidence for the independent closure review. All PostgreSQL work ran against an
> isolated ephemeral test PostgreSQL 16 on the internal test runtime, created and destroyed by the
> reviewer. No shared or production database was touched.

## Environment

```text
Reviewer worktree tip:      0bb9944
Reviewer branch:            review/66c4-be1-r1-remediation-closure
Database:                   isolated ephemeral test PostgreSQL 16 (own container, own port), destroyed after use
Guard env:                  STEP66C4_ALLOW_DESTRUCTIVE_PG_TESTS=1, BE1_TEST_DATABASE_URL=<isolated step66c4_* DSN>
```

## Mandatory PostgreSQL suites (0 skipped / 0 failed)

```text
pytest tests/test_step66c4_be1_r1_remediation.py -v                     => 44 passed in 13.61s
  (incl. test_pg_transaction_crossing_deadline_is_rejected,
         test_pg_strict_boundary_equality_is_rejected,
         test_pg_answered_at_is_statement_time_not_transaction_start,
         test_pg_due_at_remains_not_null,
         test_pg_concurrent_answer_with_barrier_exactly_one_wins,
         test_pg_loser_blocks_until_winner_commits_then_reads_final_state,
         test_pg_migration_up_down_reapply_is_deterministic,
         test_pg_outbox_durability_semantics,
         test_pg_outbox_insert_is_atomic_with_state_mutation)
pytest tests/test_step66c4_be1_data_model_deadline_outbox.py -v          => 15 passed in 1.65s
pytest tests/test_step66c4_be1_r1_independent_closure_review.py -v       => 22 passed in 10.01s  (reviewer's own)
```

## Verifiers

```text
python scripts/verify_step66c4_be1_data_model_deadline_outbox.py  => STEP66C4_BE1_DATA_MODEL_DEADLINE_OUTBOX_VERIFY: PASS  (exit 0)
python scripts/verify_step66c4_be1_r1_remediation.py              => STEP66C4_BE1_R1_REMEDIATION_VERIFY: PASS
                                                                     STEP66C4_BE1_R1_PG_EVIDENCE: PASS  (exit 0)
python scripts/verify_step66c4_be1_r1_independent_closure_review.py => STEP66C4_BE1_R1_INDEPENDENT_CLOSURE_REVIEW_VERIFY: PASS  (exit 0)
```

## Reviewer's independent reproduction (not the author's tests)

```text
[NEW predicate statement_timestamp()]  txn_start<due_at=True stmt_now>due_at=True now()==txn_start=True CLAIMED=False
[OLD predicate now() NEGATIVE CONTROL] txn_start<due_at=True stmt_now>due_at=True now()==txn_start=True CLAIMED=True
RESULT B-1: new_rejects=True  old_control_succeeds=True  non_vacuous=True
[strict-equality] (due_at > due_at) is False; claim_with_equal_bound=False
[answered_at] answered_at > transaction_timestamp() (statement time, not transaction BEGIN)

Outbox constraint probes (direct INSERT on isolated PostgreSQL):
  pending+published_at        => CheckViolationError
  published+no published_at   => CheckViolationError
  dead+published_at           => CheckViolationError
  attempts = -1               => CheckViolationError
  status = 'weird'            => CheckViolationError
  event_type = '  '           => CheckViolationError
  last_error length 501       => CheckViolationError
  duplicate idempotency_key   => UniqueViolationError
  valid pending row           => available_at NOT NULL, attempts=0

M-1 bypass probes (assert_safe_outbox_payload):
  meta/items/answer_body/question_text/TOKEN/unknown_key => rejected (key not allowed), leak=False
  due_at:{nested}            => rejected (bounded scalar), leak=False
  reason:"x"*600             => rejected (max length), leak=False
  reason:1.5 (float)         => rejected (bounded scalar), leak=False
  reason:[1,2] (list)        => rejected (bounded scalar), leak=False
  clarification_id (col-own) => rejected (column-owned key), leak=False
  event_type made_up         => rejected (unknown event_type)
  legit canonical payload    => accepted
```

## Regression (repo-wide, files R1 did not touch)

```text
pytest test_step66c1_operator_api_validation, test_step66c1_workroom_clarification_api,
       test_step66c2_clarification_ui_remediation, test_step66c2_remediation_operator_validation,
       test_step66c2_workroom_ui, test_step66c3_operator_validation,
       test_step66c3_workroom_audit_visibility, test_step66c4_contract_source_of_truth_merge
       => 126 passed
pytest test_discord_clarification_api, test_operator_rbac, test_step66b1_task_api_foundation,
       test_step66b3_rbac_audit_safety, test_step66c4_reminder_expiry_controlled_resume_planning,
       test_step66c4_planning_contract_remediation
       => 96 passed
```

No regression failure was observed. No pre-existing failure was attributed to R1; the R1 change set
touches only `workroom_store.py`, `lifecycle_outbox.py`, migration 031 (up/down), contracts, tests
and verifiers.

## Quality

```text
black --check (lifecycle_outbox.py, workroom_store.py, R1 tests, pg_safety, R1 verifier, closure tests/verifier) => clean
ruff check (same set)                                                                                            => All checks passed
mypy shared/sdk/tasks/lifecycle_outbox.py                                                                        => Success: no issues
mypy shared/sdk/tasks/workroom_store.py                                                                          => Success: no issues
git diff --check d2467f5..0bb9944                                                                                => clean
```

_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
