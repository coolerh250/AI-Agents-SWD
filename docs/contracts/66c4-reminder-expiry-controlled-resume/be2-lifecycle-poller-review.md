# Step 66C.4-BE2-R — Lifecycle Poller Review

> **Independent review. Reviewer did not implement the code. Evidence gathered on an isolated
> ephemeral PostgreSQL 16 stack on the internal test runtime. Nothing deployed.**

Reviewed commit: `319123b` (feature/66c4-be2-reminder-expiry-outbox-relay).
Module: `shared/sdk/tasks/lifecycle_poller.py`; entrypoint `apps/clarification-lifecycle-worker`.

## 6.1 Reminder predicate — PASS

The reminder claim guard is exactly:

```
status='open' AND answered_at IS NULL AND reminder_sent_at IS NULL
  AND reminder_at <= statement_timestamp() AND due_at > statement_timestamp()
```

which is equivalent to the canonical predicate. Independently verified on ephemeral PG16:

- reminder due → processed once (`reminder_sent_at` set, one outbox row `clarification.reminder_recorded`).
- not-due → not processed.
- answered / canceled / already-expired → excluded.
- past-due (`due_at <= now`) → NOT reminded (expiry owns it); belt-and-braces since `run_once`
  runs expiry first.
- `statement_timestamp()` is the DB clock; scheduler lag delays materialization, never the deadline
  (the BE1 answer CAS already enforces `due_at > statement_timestamp()`).
- two concurrent workers → exactly one reminder (FOR UPDATE SKIP LOCKED); the vendor suite's
  `test_pg_two_workers_*` and my own re-run both show `[0, 1]`.

## 6.2 Expiry predicate — PASS (state machine), with a blocking gap in 6.3

Expiry guard is exactly `status='open' AND answered_at IS NULL AND due_at <= statement_timestamp()`.
The happy-path transaction sets `clarification.status='expired'`, `expired_at=statement_timestamp()`,
`operator_tasks.status='clarification_expired'`, and inserts the `clarification.expired` outbox row —
all in one transaction. Reproduced: clarification=expired + task=clarification_expired + one outbox
row, atomic.

## 6.3 Unexpected task states — REMEDIATION_REQUIRED (BLOCKING)

The task update is guarded `WHERE id=$1 AND status='clarification_needed'`. This correctly protects a
terminal task from being clobbered. **But the clarification update and the outbox insert are
UNCONDITIONAL**, and the task-update result (asyncpg returns `"UPDATE 0"` / `"UPDATE 1"`) is never
inspected. There is no rowcount check and no reconciliation signal for a 0-row task update.

Independent reproduction on PG16 (task seeded in a legal-but-unexpected NON-terminal state `running`,
clarification open and past `due_at`):

```
committed cycle count      : 1
clarification.status       : expired  (expired_at set: True)
TASK.status (was 'running'): running   <-- UNCHANGED, task update matched 0 rows
outbox row emitted         : event_type=clarification.expired status=pending
reconciliation metric delta: 0   <-- NO observable reconciliation failure
```

And with a terminal task (`canceled`):

```
task stays               : canceled (protected - good)
outbox rows for this clar: 1   <-- clarification.expired STILL committed for a canceled task
```

So the clarification transitions to `expired` and a `clarification.expired` event is durably
committed while the task diverges (stays `running` / `canceled`), with **no observable reconciliation
failure** (the `clarification_reconciliation_failures_total` counter fires only on an outbox
idempotency collision, never on a task/clarification mismatch). This is exactly the partial-consistency
condition §6.3 flags: *"a clarification cannot be expired alone while the task is unchanged yet the
outbox is still committed inconsistently."* Per §6.3 the verdict is **REMEDIATION_REQUIRED**.

Note the record does not *loop* forever (once `expired`, the row no longer matches the guard), so the
"fail every 60s" sub-condition is not triggered — but the silent divergence is worse than a loud loop
because nothing surfaces it. The vendor test `test_pg_expiry_skips_answered_and_canceled_and_protects_terminal_task`
asserts the canceled-task case as *correct* and never checks the outbox count, which masks the gap.

Recommended remediation (for BE-owner, NOT performed here): inspect the task-update rowcount; when it
is 0 for a clarification that is being expired, either (a) treat it as an observable reconciliation
event (metric + bounded log, and decide whether the outbox event should still be emitted), or
(b) narrow the expiry claim so a clarification whose task is not `clarification_needed` is not silently
expired-with-event. The Product Owner should decide the intended semantics for a terminal-task
clarification (should `clarification.expired` be emitted at all?).

## 6.4 Lock ordering & deadlock — PASS

Lock order across paths:

- Answer API (`WorkroomStore.claim_answer`): a single-statement CAS `UPDATE operator_clarification_requests`
  in its own autocommit transaction. Touches only the clarification row; never locks a task while
  holding a clarification lock.
- Reminder poller: locks one clarification row (`FOR UPDATE SKIP LOCKED`), updates it, inserts outbox.
  Never touches `operator_tasks`.
- Expiry poller: locks one clarification row, updates it, then updates the task by primary key, then
  inserts outbox → order is **clarification → task**, consistently.
- Create-clarification path updates the task to `clarification_needed` in a separate call, not while
  holding a clarification lock.

No path takes a task lock and then a clarification lock, so there is no lock-order inversion and no
reproducible deadlock. Rollback is safe (each `_claim_one_*` wraps `tx.rollback()` in a suppressed
`except`), and a crash before COMMIT releases the SKIP-LOCKED claim. No Redis/distributed lock is used.

---

_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
