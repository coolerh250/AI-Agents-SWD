# Step 66C.4-BE2-R1 — Expiry Parent-Task Consistency Record (B-1)

> **Remediation record. NOT deployed. NOT runtime validated.**

## Finding (independent review, confirmed)

Expiry set the clarification to `expired` and inserted the `clarification.expired` outbox row
unconditionally, while the parent-task UPDATE was guarded `WHERE status='clarification_needed'` and
its 0-row result was never inspected and never surfaced. A parent in `running` (unexpected) or a
terminal parent (canceled) therefore left the clarification expired and an outbox row committed with
NO task transition and NO diagnostic — a silent partial-consistency state.

## Remediation (PO decision 1.1)

`_claim_one_expiry` now, in one transaction:

```text
1. Claim one due clarification: FOR UPDATE SKIP LOCKED.
2. Lock the parent task and read status: SELECT status FROM operator_tasks WHERE id=$1 FOR UPDATE.
3. Branch on task status:
   - clarification_needed  -> full transition; GUARDED task UPDATE rowcount MUST == 1, else rollback
                              the whole transaction (no expiry, no outbox) -> reconciliation failure.
   - terminal (TERMINAL_TASK_STATUSES) -> suppress: no mutation, no outbox,
                              terminal_parent_suppressed metric, bounded diagnostic.
   - other non-terminal    -> lifecycle-invariant mismatch: no mutation, no outbox,
                              reconciliation_failure metric, bounded diagnostic.
```

Canonical terminal set: `shared/sdk/tasks/models.TERMINAL_TASK_STATUSES` =
{accepted, rejected, canceled, archived, failed, completed, aborted} — a fixed set next to
`TaskStatus`, not ad-hoc string matching. `aborted`/`completed` are canonical-terminal but are not
storable in operator_tasks (its CHECK constraint excludes them); they are covered defensively.

## Lock ordering / deadlock analysis

Order is clarification-then-task. Audit of every writer confirms no other path locks BOTH tables in
one transaction: the answer CAS (`workroom_store.answer`) and all task-status writes
(`store.update_status`, `store.set_clarification_state`) are single-statement autocommit updates.
No opposite-order cross-table cycle exists, so this introduces no new deadlock.

## Observability

```text
clarification_terminal_parent_suppressed_total{poller="expiry"}   -- terminal parent suppressed
clarification_reconciliation_failures_total{poller="expiry"}      -- mismatch OR rowcount!=1 OR outbox collision
```

Diagnostics carry only safe fields: clarification_id, task_id, observed_task_status, reason_code.
No raw clarification or task content is logged.

## Tests (real PostgreSQL 16)

```text
test_pg_b1_expiry_from_clarification_needed_full_transition
test_pg_b1_terminal_parent_suppresses_all_mutations          (canceled/rejected/accepted/archived/failed)
test_pg_b1_unexpected_nonterminal_parent_is_reconciliation_failure  (running)
test_pg_b1_guarded_update_rowcount_zero_rolls_back_everything
test_pg_b1_duplicate_poll_and_two_workers_exactly_one_expiry
plus updated tests/test_step66c4_be2_reminder_expiry_outbox_relay.py suppression assertions.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
