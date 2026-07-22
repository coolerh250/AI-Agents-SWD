# Step 66C.4-BE1-R — Deadline Semantics Independent Review

> **Independent review artifact. No implementation change. No migration change. No merge. No
> deployment. All reproductions were run by the reviewer on an isolated ephemeral test PostgreSQL 16.**

**Deadline verdict: REMEDIATION_REQUIRED**

## Implemented predicate (as committed at d2467f5)

```sql
-- shared/sdk/tasks/workroom_store.py::claim_clarification_answer
UPDATE operator_clarification_requests
SET status='answered', answered_at=now(), updated_at=now()
WHERE id=$1 AND status='open' AND answered_at IS NULL AND due_at > now()
RETURNING *
```

This matches the binding SQL literally quoted in `lifecycle-and-time-contract.md` §7.3A. The four
guard terms (id, status, answered_at, deadline) are all present, and no Python clock is involved.

## now() semantics — measured, not assumed

`now()` in PostgreSQL is an alias for `transaction_timestamp()`: it is fixed at the moment the
current transaction begins and does **not** advance for later statements in the same transaction.
Measured on the isolated ephemeral Postgres 16.14:

```text
due_at              = 2026-07-22 08:58:28.941605+00
txn now()           = 2026-07-22 08:58:25.993359+00   <- transaction_timestamp, frozen
statement_timestamp = 2026-07-22 08:58:25.996215+00
clock_timestamp     = 2026-07-22 08:58:25.996219+00

... transaction held open for 5 s, then re-read in the SAME transaction ...

now()               = 2026-07-22 08:58:25.993359+00   <- UNCHANGED (frozen at txn start)
statement_timestamp = 2026-07-22 08:58:31.001742+00   <- advanced
clock_timestamp     = 2026-07-22 08:58:31.001749+00   <- advanced
```

Semantics summary:

| Function | Advances at | Correct for a claim-time deadline? |
| --- | --- | --- |
| `now()` / `transaction_timestamp()` | transaction BEGIN | **No** — frozen for the whole transaction |
| `statement_timestamp()` | statement start | Yes |
| `clock_timestamp()` | every call | Yes (strictest) |

`lifecycle-and-time-contract.md` §7.1 and §7.3A.6 both assert that "now() is evaluated per statement
at execution time inside the claim transaction". That statement is **factually incorrect for
PostgreSQL**. The implementation faithfully implements the contract's SQL; the defect originates in
the contract's clock-function choice and is inherited by the code and by the code's own docstring
("PostgreSQL database time, evaluated in the same statement").

## Transaction-crossing-deadline reproduction (canonical requirement 5.1)

Procedure: seed an `open` clarification with `due_at = now() + 3s`; on a SEPARATE connection open an
explicit transaction BEFORE `due_at`; hold it open until DB time passes `due_at`; then execute the
exact committed CAS statement inside that same transaction.

```text
txn began BEFORE due_at:                 True
DB clock at claim time (clock_timestamp): 2026-07-22 08:58:31.001749+00
due_at:                                   2026-07-22 08:58:28.941605+00   (already ~2.06 s in the past)

CLAIM RESULT inside cross-deadline txn:   SUCCEEDED (row claimed)
answered_at written:                      2026-07-22 08:58:25.993359+00   (BACKDATED to txn start)
committed status:                         answered
```

Control, matching today's production call path (implicit/autocommit single statement, one dedicated
connection per call, exactly as `claim_clarification_answer` runs today):

```text
CONTROL autocommit claim after deadline:  rejected (correct)
```

### Assessment

1. **Today's code path is not exploitable.** `claim_clarification_answer` opens its own connection,
   issues one statement, and closes it. The implicit transaction begins at that statement, so
   `now()` ≈ statement time and a past-deadline answer is correctly rejected. Confirmed by the
   control run and by the committed test `test_pg_deadline_cas_future_past_boundary`.
2. **The canonical requirement is nevertheless not met.** The requirement is that the deadline be
   evaluated at claim-STATEMENT execution time and that a transaction which merely STARTED before
   the deadline must not be able to answer after it. The reproduction shows it can. Per the review
   rule, this alone is `REMEDIATION_REQUIRED`.
3. **This is not hypothetical — the canonical contract mandates the exact wrapping that activates
   the defect.** `api-and-event-contract.md` §11.3 (binding) requires that "the lifecycle CAS UPDATE
   and an INSERT into a durable outbox table commit in the SAME database transaction", and
   `data-model-contract.md` row 3 requires `resume_eligible_at` to be "set in the same transaction as
   the answer-claim". BE2/BE3 must therefore wrap this exact CAS in an explicit multi-statement
   transaction. At that moment `now()` becomes the transaction start time, the deadline predicate
   silently degrades, and the window widens by the full duration of the transaction (task lookup,
   outbox insert, message insert, retries). The safety property is preserved today only by an
   accident of the current call shape, and it is documented nowhere as a precondition.
4. **Secondary effect: `answered_at` backdating.** Inside a wrapping transaction, `answered_at=now()`
   records transaction-start time, not the answer time. In the reproduction it was backdated 5.0 s.
   For an audit-evidence timestamp on a deadline-governed lifecycle this is a correctness defect in
   its own right.

## Exact-boundary result

The committed test's "exact boundary" case seeds `due_at = now()` at INSERT time and then claims
later, so at claim time `now() > due_at` by a few milliseconds. It therefore re-tests the
already-covered past-deadline case rather than the equality case `now() == due_at`. Independently
confirmed: the predicate `due_at > now()` is a strict inequality, so equality is rejected — which is
what PO Decision 1 ("due_at is an exclusive upper bound; answer exactly at due_at is rejected")
requires. The BEHAVIOUR is correct; the TEST for it is a near-tautology (see the test-quality review).

## due_at IS NULL / legacy-row result

```text
information_schema: operator_clarification_requests.due_at is_nullable = NO
INSERT with due_at NULL -> NotNullViolationError (rejected by the schema itself)
SQL three-valued logic:  (NULL::timestamptz > now()) => NULL  (not TRUE)
Simulated legacy NULL row on a scratch copy, real CAS predicate:
  rows matching (status='open' AND answered_at IS NULL AND due_at > now()) = 0
```

`due_at TIMESTAMPTZ NOT NULL` has been in force since migration `030` created the table, and no
earlier migration in `migrations/**` creates or alters `operator_clarification_requests`. There is
therefore no schema version of this table in which a NULL `due_at` could ever have been written —
this is a structural guarantee from the DDL, not the weaker claim "no NULL rows exist today".

Confirmed for completeness: **if** a NULL `due_at` row could exist, the CAS would silently and
permanently lock it out (0 rows match), and the API would report it as
`invalid_state_for_answer:expired`. That failure mode is unreachable under the committed schema.

**due_at NULL verdict: SAFE — no remediation required.** Recommendation (non-blocking): the eventual
remediation should add a regression assertion that `due_at` remains `NOT NULL`, so that a future
migration relaxing it cannot silently introduce permanently unanswerable rows.

## Recommended minimum remediation (Step 66C.4-BE1-R1)

Scope-minimal, no behaviour change to the passing cases:

```text
1. Amend lifecycle-and-time-contract.md §7.1 and §7.3A.6: replace the incorrect claim that "now() is
   evaluated per statement" with the correct PostgreSQL semantics, and make the binding predicate
   `due_at > statement_timestamp()` (or clock_timestamp()) rather than `due_at > now()`.
2. Change the one predicate in shared/sdk/tasks/workroom_store.py::claim_clarification_answer to the
   amended clock function. (Under the current autocommit call shape this is behaviour-identical;
   under BE2's mandated wrapping transaction it is the difference between correct and incorrect.)
3. Decide and record whether `answered_at` should likewise be stamped with statement/clock time so it
   is not backdated to transaction start once the CAS is wrapped.
4. Add the missing regression test: a claim executed inside an explicit transaction that began before
   due_at and executes after due_at must be REJECTED.
```

BE1-R1 is required rather than deferring to BE2, because BE2 is the stage that introduces the
wrapping transaction; deferring means BE2 would silently inherit a broken deadline guarantee.

## Statement

Independent review artifact only. No implementation change. No migration change. No scheduler or
relay activation. No dispatch/resume. No external notification. No shared-runtime migration. No
deployment. No merge.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
