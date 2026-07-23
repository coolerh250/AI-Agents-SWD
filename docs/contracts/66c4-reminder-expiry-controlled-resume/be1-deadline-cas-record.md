# Step 66C.4-BE1 — Authoritative Answer Deadline CAS Record

> **Implementation record. The only API behavior change is the canonical past-deadline 409.**

## Change

```text
File: shared/sdk/tasks/workroom_store.py :: claim_clarification_answer
Previous predicate: WHERE id=$1 AND status='open'
New predicate:      WHERE id=$1 AND status='open' AND answered_at IS NULL AND due_at > now()
```

```text
DB authoritative time: the predicate uses PostgreSQL now() evaluated inside the same UPDATE
  statement. No Python datetime.now() participates in the authoritative decision.
Exclusive deadline: due_at is an EXCLUSIVE upper bound. An answer at or after due_at
  (now() >= due_at) matches zero rows and the claim returns None, EVEN WHEN status is still 'open'
  (the future timeout worker has not materialized 'expired'). Scheduler lag therefore cannot extend
  the answer window (canonical lifecycle-and-time-contract.md 7.3A).
```

## Post-deadline API result

```text
File: apps/orchestrator/src/workroom_api.py :: answer_clarification
On a lost claim (claimed is None), the endpoint re-reads the authoritative row and maps the reason
using the EXISTING 409 response shapes -- no new shape:
  - row status still 'open'  -> 409 invalid_state_for_answer:expired  (lost to the deadline)
  - row status 'expired'/'canceled' -> 409 invalid_state_for_answer:{status}
  - otherwise (concurrent winner already answered) -> 409 clarification_already_answered
The re-read reflects authoritative DB state; no Python clock is used to decide expiry.
```

## Concurrent answer behavior

```text
Two concurrent answer claims on the same open clarification resolve to EXACTLY ONE winner
(Postgres row-level locking serializes the two UPDATEs; the loser's WHERE no longer matches).
Confirmed by test_pg_concurrent_answer_exactly_one_wins (real Postgres, asyncio.gather).
This is a single-state CAS guarantee only; no exactly-once event delivery is claimed (no event is
emitted by the claim at all).
```

## Existing response compatibility

```text
Success response schema is unchanged (same fields, plus the pre-existing dispatch_enabled=false /
  resume_dispatch_enabled=false flags, unchanged).
Existing 401/403/404/422 behavior is unchanged.
Existing 409 clarification_already_answered (answered-twice / concurrent race) is unchanged --
  regression-verified by the Step 66C.3 answered-twice guard tests (still green).
```

## Task status

```text
No global task status added. clarification_expired is NOT materialized by BE1 (that is BE2's
timeout worker). The claim writes NO outbox row and triggers NO scheduler/event/notification on
either success or failure.
```

## Tests

```text
test_answer_cas_sql_enforces_authoritative_deadline (static: predicate present),
test_pg_deadline_cas_future_past_boundary (real PG: future succeeds; past/open fails and stays
  'open'; boundary fails; answered fails), test_pg_concurrent_answer_exactly_one_wins,
test_past_deadline_answer_returns_409_expired + test_within_deadline_answer_succeeds (API).
Step 66C.3 answered-twice regression: green.
```

## Statement

Deadline CAS record. The only API behavior change is the canonical past-deadline 409. No new
endpoint. No success-schema change. No scheduler/relay/dispatch/resume. No external notification. No
deployment.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
