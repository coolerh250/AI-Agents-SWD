# Step 66C.4-BE2-R1 Remediation Record

> **Remediation record. NOT deployed. NOT runtime validated. No shared-runtime activation. No
> shared migration. No existing producer cutover. No dispatch/resume. No external notification.
> PR #18 remains Draft. BE2 technical closure requires the independent Step 66C.4-BE2-R1-R review.**

## Scope

Closes the two blocking findings the independent Step 66C.4-BE2-R review confirmed against the BE2
implementation (`review/66c4-be2-poller-relay-transaction-recovery @ c70f205`,
`BE2_TECHNICAL_VERDICT: REMEDIATION_REQUIRED`), and implements the Product Owner's binding retry
and replay-boundary decisions. No new feature scope.

```text
B-1  Expiry parent-task consistency (partial-consistency + unobservable mismatch).
B-2  Bounded Redis publish (DB transaction / row lock held across an unbounded publish).
1.2  Exact retry/attempt semantics (the 3600s backoff was dead code).
1.4  replay_dead stays internal-only; RBAC/human-authorization deferred to BE3.
```

## Files changed

```text
shared/sdk/tasks/lifecycle_poller.py    -- B-1: lock parent task, branch on status, guarded
                                           rowcount==1, terminal-suppress / reconcile, observability
shared/sdk/tasks/outbox_relay.py        -- B-2: bounded publish (asyncio.wait_for + bounded bus
                                           socket timeouts), timeout->transient retry, cancellation
                                           rolls back + re-raises; publish-timeout config [1,30]s
shared/sdk/tasks/lifecycle_outbox.py    -- 1.2: MAX_RETRIES=4 / MAX_PUBLISH_ATTEMPTS=5; every
                                           backoff reached; dead on the 5th failure
shared/sdk/tasks/lifecycle_metrics.py   -- terminal_parent_suppressed metric; reconciliation help text
shared/sdk/tasks/models.py              -- canonical TERMINAL_TASK_STATUSES (fixed set, near TaskStatus)
shared/sdk/event_bus/redis_streams.py   -- additive, backward-compatible bounded socket timeouts
                                           (default None preserves every existing caller)
tests/test_step66c4_be2_r1_remediation.py       -- B-1/B-2/retry/replay tests (NEW)
scripts/verify_step66c4_be2_r1_remediation.py    -- 20-check verifier (NEW)
```

No migration was added or changed. The BE1 outbox schema (migration 031, on main) is unchanged and
sufficient. Neither worker is activated in any shared runtime.

## Disclosed changes to previously-committed tests

The PO formally changed two behaviors this remediation implements, so three prior assertions that
encoded the OLD behavior were updated MINIMALLY and are disclosed here for the reviewer to scrutinize:

```text
1. tests/test_step66c4_be2_reminder_expiry_outbox_relay.py
   ::test_pg_expiry_skips_answered_and_canceled_and_protects_terminal_task
   RENAMED -> ::test_pg_expiry_skips_answered_and_suppresses_terminal_parent
   OLD (the B-1 defect): an open past-due clarification on a canceled (terminal) parent was
   EXPIRED and its clarification.expired outbox row EMITTED. NEW (PO decision 1.1): that parent is
   terminal, so the transition is SUPPRESSED -- clarification stays open, task unchanged, no outbox.

2. tests/test_step66c4_be2_reminder_expiry_outbox_relay.py
   ::test_pg_relay_exhausts_to_dead_after_bounded_attempts
   attempts at dead: 4 -> 5 (PO decision 1.2 -- the 5th failure is terminal).

3. tests/test_step66c4_be1_r1_remediation.py::test_retry_plan_persists_backoff_then_dies
   terminal attempts: MAX_DELIVERY_ATTEMPTS-1 -> MAX_PUBLISH_ATTEMPTS-1 (the constant was renamed
   and the dead threshold corrected).
```

No previously-committed independent review finding or verdict was modified. The zero-caller /
non-activation allowlist was NOT broadened further (it still permits exactly the two authorized
worker modules); see be2-safety-and-nonactivation-record.md.

## Authorization posture

```text
Deployment:                     NO
Shared DB migration 031:        NO (unchanged)
Existing producer cutover:      NO (audit producer path unchanged; only an additive bus timeout kwarg)
Runtime outbox writes:          NO (only tests invoke the workers)
Scheduler/relay activation:     NO
Public replay API:              NO (replay_dead internal-only; RBAC deferred to BE3)
Resume/dispatch/workflow resume: NO
External notification:          NO
PR #18:                         Draft / NOT FOR MERGE
Step 66C.4-BE3:                 NOT authorized, NOT started
Codex / Claude Design:          NOT authorized
Independent closure review:     REQUIRED (Step 66C.4-BE2-R1-R) before merge/deploy
production_executed_true_count: 0
```

## Markers

```text
STEP66C4_BE2_R1_REMEDIATION_VERIFY: PASS   -- self-verification only (scripts/verify_step66c4_be2_r1_remediation.py)
STEP66C4_BE2_R1_PG_REDIS_EVIDENCE: PASS    -- real PostgreSQL 16 evidence (see test record)
BE2_TECHNICAL_VERDICT: REMEDIATION_REQUIRED -- unchanged; only the independent closure reviewer may set PASS
```

## Statement

Remediation record only. No deployment. No shared-runtime migration. No scheduler/relay activation.
No live producer cutover. No dispatch/resume. No external notification. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
