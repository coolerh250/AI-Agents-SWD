# Step 66C.4-BE2-R1 — Context Receipt

## Shared Context Preflight

```text
Latest main:            ab3c6cc
Feature baseline:       319123b (feature/66c4-be2-reminder-expiry-outbox-relay, clean tree)
Independent review:     c70f205 (review/66c4-be2-poller-relay-transaction-recovery)
Review process marker:  STEP66C4_BE2_INDEPENDENT_REVIEW_VERIFY: PASS
Technical verdict:      BE2_TECHNICAL_VERDICT: REMEDIATION_REQUIRED
```

## Canonical contracts / decisions reviewed

```text
lifecycle-and-time-contract.md (§7.3A expiry semantics; §7.3B/§7.3C added here)
data-model-contract.md (retry semantics; exact schedule added here)
api-and-event-contract.md (§11.2/§11.3 events + delivery model)
rbac-and-safety-contract.md, race-condition-and-failure-analysis.md
be1-source-of-truth-record.md, be2-* implementation records
Independent review artifacts @ c70f205 (B-1, B-2, LOW retry off-by-one, MEDIUM replay RBAC)
PO decisions 1.1 (expiry consistency), 1.2 (retry), 1.3 (Redis timeout), 1.4 (replay boundary)
```

## Understanding

```text
B-1 understood: expiry emitted clarification.expired + expired clarification even when the guarded
    task UPDATE affected 0 rows (terminal/unexpected parent), with no diagnostic -> partial
    consistency. Fixed by locking the parent, branching on status, asserting rowcount==1, and
    making terminal-suppression / reconciliation observable.
B-2 understood: publish ran inside the DB transaction with an unbounded Redis client -> a hung
    broker pins the txn/row lock/connection. Fixed by a bounded socket timeout + asyncio.wait_for
    total cap; timeout is a transient retry; cancellation rolls back and re-raises.
Retry decision understood: MAX_RETRIES=4, MAX_PUBLISH_ATTEMPTS=5, every backoff reached, dead on 5th.
```

## New information / conflicts

```text
New information: operator_tasks CHECK constraint (migration 029) does not permit aborted/completed,
    so those canonical-terminal statuses are covered defensively but tested only DB-less; DB-level
    terminal tests use canceled/rejected/accepted/archived/failed.
Conflict: the relay's only Redis client is RedisStreamEventBus; bounding it required an additive,
    backward-compatible kwarg on that shared module. Resolved within the BE2-R1 "Redis client
    timeout" authorization; the audit producer path is otherwise unchanged. The BE2 verifier's
    transport-unchanged check was narrowed to reflect this single authorized change.
Remediation impact: three previously-committed assertions that encoded the old behavior were
    updated minimally and disclosed; no committed review finding/verdict was changed.
```

## Posture

Remediation only. PR #18 Draft. No merge, deploy, shared activation, BE3, Codex, or Claude Design.

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
