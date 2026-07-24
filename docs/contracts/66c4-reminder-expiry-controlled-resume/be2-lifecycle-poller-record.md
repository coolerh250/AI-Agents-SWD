# Step 66C.4-BE2 Lifecycle Poller Record

> **Implementation record. Evidence gathered on isolated ephemeral PostgreSQL 16. NOT deployed. No
> shared migration. No external notification.**

## Module

`shared/sdk/tasks/lifecycle_poller.py` -- `ClarificationLifecyclePoller`.

```text
Poll interval default:  60 seconds (canonical); configurable.
Batch size default:     50; configurable.
Shutdown timeout:       30 seconds; configurable.
Database clock:         statement_timestamp() (authoritative; same function BE1's answer CAS uses).
Claim model:            SELECT ... FOR UPDATE SKIP LOCKED, ONE row per transaction.
```

## Reminder transition

Claim guard (canonical lifecycle-and-time-contract.md):

```sql
status='open' AND answered_at IS NULL AND reminder_sent_at IS NULL
  AND reminder_at <= statement_timestamp() AND due_at > statement_timestamp()
```

One transaction: `UPDATE ... SET reminder_sent_at=statement_timestamp()` + insert outbox event
`clarification.reminder_recorded` (idempotency key `{clarification_id}:reminder`, payload
`{"reason": "reminder_recorded"}`). A past-due row (`due_at <= statement_timestamp()`) is NOT
reminded -- the `due_at > statement_timestamp()` guard excludes it and expiry handles it. Scheduler
lag only delays materialization; it never extends the deadline (BE1's answer CAS enforces the
window regardless).

Properties verified on ephemeral PostgreSQL 16:

```text
due reminder -> reminder_sent_at + pending outbox row, same transaction          PASS
not-yet-due / answered / expired clarifications skipped                          PASS
past-due row is expired, not reminded                                            PASS
duplicate poll records exactly one reminder (reminder_sent_at guard)             PASS
two concurrent workers -> exactly one claim (results sorted [0, 1])              PASS
injected outbox failure -> reminder_sent_at unchanged, zero outbox rows          PASS
fresh poller instance (restart) processes the due record                        PASS
```

## Expiry transition

Claim guard (canonical): `status='open' AND answered_at IS NULL AND due_at <= statement_timestamp()`.

One transaction:

```sql
UPDATE operator_clarification_requests SET status='expired', expired_at=statement_timestamp(), ...;
UPDATE operator_tasks SET status='clarification_expired', updated_at=now()
  WHERE id=$task AND status='clarification_needed';   -- reuse existing status; guard terminal tasks
INSERT INTO clarification_lifecycle_outbox (...) event_type='clarification.expired' ...;
```

The task update reuses the existing `clarification_expired` `operator_tasks.status` value (no new
global status) and is guarded by `status='clarification_needed'`, so a task that has already moved
to a terminal/other state (canceled, aborted, ...) is NOT clobbered. A task not in
`clarification_needed` simply matches zero task rows -- a valid outcome within the same transaction,
not a partial commit and not a failure.

Properties verified on ephemeral PostgreSQL 16:

```text
due expiry -> clarification expired + task clarification_expired + outbox, one txn  PASS
answered / canceled clarifications skipped; terminal (canceled) task NOT clobbered  PASS
injected task-update failure -> clarification stays open, zero outbox rows (§19.8)  PASS
injected outbox-insert failure -> task + clarification rolled back (§19.9)          PASS
two concurrent workers -> exactly one claim                                         PASS
duplicate expiry poll -> no duplicate event (status guard)                          PASS
```

## Concurrency, restart, shutdown

```text
Multiple workers:      SKIP LOCKED gives exactly-one processing; no lease, no leader election,
                       no Redis lock.
Crash before commit:   the per-row transaction rolls back; the row returns to its pre-claim state.
Re-entrancy:           a cycle re-selects only rows still matching the guard; a per-cycle skip set
                       excludes a row that hit an unexpected outbox collision (reconciliation).
Graceful shutdown:     the run loop stops starting new cycles once stop_event is set; an in-flight
                       transaction commits or rolls back first.
```

## Reconciliation safety

Under the atomic model, if `reminder_sent_at IS NULL` (or clarification `status='open'`) then the
matching outbox row cannot already exist, because state and outbox commit together. A duplicate
`idempotency_key` on insert is therefore a genuine inconsistency: the poller ROLLS BACK the
transaction, increments `clarification_reconciliation_failures_total`, logs a bounded warning
(clarification_id only), and excludes the row for the rest of the cycle -- it is surfaced for
operator attention, never silently skipped.

## Statement

Implementation record only. No deployment. No shared-runtime migration. No scheduler activation in
any shared runtime. No dispatch/resume. No external notification. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
