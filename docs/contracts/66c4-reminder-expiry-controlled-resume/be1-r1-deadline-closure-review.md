# Step 66C.4-BE1-R1-R — B-1 Deadline Semantics Closure Review

> Independent closure review of blocking finding **B-1** (transaction-time deadline defect).
> Judged only from the canonical contract, the code at `0bb9944`, and the reviewer's own
> reproductions on an isolated ephemeral test PostgreSQL 16. Nothing was fixed here; no
> implementation file was modified.

## Finding under review

B-1 (BLOCKING, from `f5417f4`): the answer-claim CAS read `due_at > now()`. PostgreSQL `now()` /
`transaction_timestamp()` are frozen at transaction BEGIN, so a transaction opened before `due_at`
could commit a claim after `due_at`, and `answered_at` would be backdated to the transaction start.
The atomicity model binding BE2 (api-and-event-contract.md 11.3) wraps the CAS with an outbox
INSERT in one transaction — exactly the shape that activates the defect.

## Code inspected (remediated branch `0bb9944`)

`shared/sdk/tasks/workroom_store.py :: claim_clarification_answer` now executes:

```sql
UPDATE operator_clarification_requests
SET status='answered',
    answered_at=statement_timestamp(),
    updated_at=statement_timestamp()
WHERE id=$1 AND status='open' AND answered_at IS NULL
  AND due_at > statement_timestamp()
RETURNING *
```

Residual-clock scan of the module: no `due_at > now()`, no `due_at > transaction_timestamp()`,
no `answered_at=now()`, no `answered_at=transaction_timestamp()`, and no Python `datetime.now()`
participates in the deadline decision (the only Python `datetime.now(timezone.utc)` remaining is in
`create_clarification`, which computes the *stored* `due_at`/`reminder_at` at row creation — not the
claim decision, and out of scope for B-1). The post-answer `set_answer_message` still uses `now()`
for `updated_at`, but that runs after a successful claim and takes no part in the deadline predicate.

## 6.1 MANDATORY transaction-crossing reproduction (reviewer's own)

Method: on an isolated ephemeral test PostgreSQL 16, apply migrations 029/030/031, seed an open
clarification with `due_at = statement_timestamp() + interval '3 seconds'`, `BEGIN`, confirm the
transaction start is before `due_at`, `pg_sleep(4)` so DB statement time passes `due_at`, then run
the remediated CAS in the same transaction. A **negative control** runs the identical scenario with
the OLD predicate `due_at > now()` in isolated test SQL (production code never modified).

Raw evidence:

```text
[NEW predicate statement_timestamp()]  txn_start<due_at=True  stmt_now>due_at=True  now()==txn_start=True  CLAIMED=False
[OLD predicate now() NEGATIVE CONTROL] txn_start<due_at=True  stmt_now>due_at=True  now()==txn_start=True  CLAIMED=True
RESULT B-1: new_rejects=True  old_control_succeeds=True  non_vacuous=True
```

Interpretation: with the remediated predicate the cross-deadline claim is REJECTED (`answered_at`
stays NULL). The negative control proves the OLD predicate would have SUCCEEDED under exactly the
same timing — so the fixed assertion is not vacuous. In both runs `now()` is frozen at the
transaction start (`now()==txn_start` and `now()<due_at`), confirming the frozen-clock mechanism the
finding described.

## 6.2 Timestamp consistency

Reproduced independently: a within-deadline claim inside a transaction that BEGAN one second earlier
returns `answered_at > transaction_timestamp()`, i.e. `answered_at` reflects the claim statement
time, not the transaction BEGIN time. Because the predicate and the `answered_at` write both read
`statement_timestamp()`, they share a single reading within the statement.

```text
[answered_at] txn_start=01:25:53.645  answered_at=01:25:54.653  answered_at>txn_start=True
```

## 6.3 Strict equality boundary

The finding requires proving that at exact equality `due_at == statement_timestamp()` the strict `>`
is FALSE (a real equality test, not merely "already in the past"). Reviewer evidence:

```text
[strict-equality] (due_at > due_at) is False => True; claim_with_equal_bound=False
```

An `UPDATE ... WHERE due_at > due_at` (an unarguable exact-equality comparison of the column against
itself, evaluated inside one statement) matches zero rows. Equality is therefore rejected: the answer
window is `[created_at, due_at)`, half-open with `due_at` excluded, as the contract specifies.

## 6.4 Contract closure

`lifecycle-and-time-contract.md` now states: `now()` and `transaction_timestamp()` are the SAME
function and return the transaction-start time (§16), and the authoritative claim-execution deadline
uses `statement_timestamp()` (§7.3A, "BINDING, corrected in Step 66C.4-BE1-R1"), with `due_at` an
EXCLUSIVE upper bound and equality REJECTED. The contract and the code agree.

## Verdict

**B-1: CLOSED.** The predicate and the `answered_at` write use `statement_timestamp()`; the
transaction-crossing claim is rejected with a non-vacuous negative control; the strict-equality
boundary has real evidence; the canonical contract is consistent with the code.

_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
