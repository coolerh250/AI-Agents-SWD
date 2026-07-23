# Step 66C.4-BE1-R1 Deadline Remediation Record (B-1)

> **Remediation record. No scheduler. No relay. No deployment. No merge. All measurements were
> taken on an isolated ephemeral test PostgreSQL 16 created for this stage and destroyed after.**

## The defect

PostgreSQL `now()` is an alias for `transaction_timestamp()`: it is fixed when the transaction
begins and does not advance for later statements in that transaction. The Step 66C.4-BE1 predicate
`due_at > now()` therefore compared the deadline against the TRANSACTION START time.

The single-statement autocommit call shape used today happened to be safe, but the binding
atomicity model (api-and-event-contract.md 11.3) requires BE2 to wrap this CAS together with the
outbox INSERT in one transaction -- precisely the shape that activates the defect.

The canonical contract was a root cause: lifecycle-and-time-contract.md 7.1 and 7.3A.6 asserted
that "now() is evaluated per statement", which is factually incorrect for PostgreSQL. That claim
had already been merged into main by Step 66C.4-P-M, so the correction had to be made to the
canonical contract as well as to the code.

## The correction

```text
Previous predicate:   WHERE id=$1 AND status='open' AND answered_at IS NULL AND due_at > now()
New predicate:        WHERE id=$1 AND status='open' AND answered_at IS NULL
                        AND due_at > statement_timestamp()

Previous answered_at: answered_at = now()          (transaction start; backdated when wrapped)
New answered_at:      answered_at = statement_timestamp()
Previous updated_at:  updated_at  = now()
New updated_at:       updated_at  = statement_timestamp()
```

`statement_timestamp()` was selected over `clock_timestamp()` because it is CONSTANT within a
single SQL statement: the deadline comparison and the `answered_at` write in the same CAS statement
therefore observe one identical reading. `clock_timestamp()` advances on every call and would let
those two observe different times.

Non-claim scheduler scans (`reminder_at <= ...`, `due_at <= ...`) only select rows for
materialization and do not decide answer eligibility; they are not bound by this rule.

## Evidence (isolated ephemeral PostgreSQL 16)

Negative control -- the same cross-deadline scenario run against BOTH predicates:

```text
Scenario: due_at = statement_timestamp() + 3s; BEGIN before due_at; pg_sleep(4); then claim.

OLD  due_at > now()                  -> claim SUCCEEDED (defect reproduced)
                                        answered_at written and backdated to the transaction start
NEW  due_at > statement_timestamp()  -> claim rejected (correct)
                                        answered_at remains NULL, status remains 'open'
```

This is what makes `test_pg_transaction_crossing_deadline_is_rejected` a genuine regression test
rather than a vacuous one: it fails on the old predicate and passes on the new one.

Additional confirmations inside the test suite:

```text
now() frozen inside the held transaction        : asserted equal to transaction_timestamp()
statement_timestamp() advanced past due_at      : asserted
claim inside the cross-deadline transaction     : REJECTED, answered_at NULL, status 'open'
answered_at is NOT backdated (2s held txn)      : answered_at - transaction_start >= 2s
strict boundary (due_at == compared timestamp)  : `due_at > $ts` evaluates FALSE (exclusive bound)
due_at NOT NULL preserved by migration 031      : information_schema is_nullable = NO;
                                                  a NULL insert raises NotNullViolationError
concurrency, two connections behind a barrier   : exactly one winner
loser blocks on the winner's uncommitted lock   : still blocked after 1.0s; after commit -> None,
                                                  then reads the authoritative 'answered' state
```

## Compatibility

```text
API success response schema:       unchanged
API failure behavior:              unchanged -- 409 invalid_state_for_answer:expired
Behavior under today's call shape: identical (autocommit single statement)
Behavior under BE2's wrapping:     CORRECT instead of silently widened
Task/clarification status values:  unchanged; no clarification_expired materialization added
Outbox writes from the claim:      none
Python clocks in the deadline:     none
```

## Statement

Remediation record only. No scheduler implemented or activated. No relay. No live producer. No
resume/dispatch. No external notification. No shared-runtime migration. No deployment. No merge.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
