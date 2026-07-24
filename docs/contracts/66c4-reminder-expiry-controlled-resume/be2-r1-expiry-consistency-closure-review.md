# Step 66C.4-BE2-R1-R — B-1 Expiry Parent-Task Consistency Closure Review

> Independent review record. Not deployed. Not a merge authorization. No shared activation.

## Original finding (c70f205, B-1)

Silent partial consistency on an unexpected/terminal task state: the expiry worker updated the
clarification to `expired` and inserted the `clarification.expired` outbox row even when the
guarded task UPDATE matched 0 rows (terminal or unexpected parent), with no diagnostic — a lone
outbox event and an expired clarification with the parent task left inconsistent, unobservable.

## What the code does now (`shared/sdk/tasks/lifecycle_poller.py`, `_claim_one_expiry`)

```text
1. Claim the due clarification: FOR UPDATE SKIP LOCKED (status='open', answered_at IS NULL,
   due_at <= statement_timestamp()).
2. LOCK + READ the parent BEFORE any mutation: SELECT status FROM operator_tasks ... FOR UPDATE.
3. Branch on the authoritative parent status:
   - terminal (TERMINAL_TASK_STATUSES) -> rollback, NO mutation, NO outbox,
     terminal_parent_suppressed +1, INFO diagnostic (reason_code=terminal_parent_suppressed).
   - not clarification_needed and not terminal -> rollback, NO mutation, NO outbox,
     reconciliation_failure +1, WARNING (reason_code=reconciliation_required).
   - clarification_needed -> guarded UPDATE to clarification_expired; _rowcount(tag) MUST == 1,
     else rollback everything (reconciliation_failure). Then clarification 'open'->'expired', then
     outbox INSERT, then COMMIT. UniqueViolation on the outbox -> rollback + reconcile.
```

The old unguarded post-update task write was REMOVED; the guarded update now precedes the
clarification/outbox writes, so a non-matching parent can never leave a lone outbox row.

## Independent verification (real PostgreSQL 16)

```text
clarification_needed full transition          -> expired + task clarification_expired + 1 outbox   PASS
every DB-valid terminal (canceled/rejected/                                                        PASS
   accepted/archived/failed) suppressed         -> clarification open, task unchanged, 0 outbox,
                                                   terminal_parent_suppressed +1
unexpected non-terminal (running/blocked/                                                          PASS
   approved_for_execution)                       -> no mutation, 0 outbox, reconciliation_failure +1
guarded UPDATE rowcount 0 (fault-injection seam) -> whole txn rolls back, clarification open,       PASS
                                                    task clarification_needed, 0 outbox
unreadable/NULL parent status (defensive seam)   -> reconcile, no mutation, 0 outbox                PASS
two workers race on one due row                  -> exactly one commits (results sorted == [0,1])   PASS
duplicate poll after expiry                      -> no-op, still exactly 1 outbox row               PASS
```

`aborted`/`completed` are in the canonical `TERMINAL_TASK_STATUSES` but are NOT permitted by the
migration-029 `chk_operator_tasks_status` CHECK constraint, so they are defensive-only and cannot
misclassify a live non-terminal status. Verified against the migration constraint directly.

## Lock ordering / deadlock

Lock order is clarification-then-task and only the expiry worker locks BOTH tables in one
transaction. Independently confirmed that every other writer is single-statement autocommit and
single-table: the answer CAS (`workroom_store.claim_clarification_answer`) and `set_answer_message`
touch only `operator_clarification_requests`; no `apps/**` path touches
`operator_clarification_requests` at all, and task-status writes touch only `operator_tasks`. No
new deadlock cycle is introduced.

## Repeat-logging assessment

A terminal/reconcile row remains `status='open'` and is re-evaluated once per poll cycle (default
60s): a bounded claim + lock + rollback + one diagnostic with safe identifiers only. This is
observable-not-silent and is not a high-frequency flood or a sensitive-data leak. Informational.

## Verdict

**B-1: CLOSED.**

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
