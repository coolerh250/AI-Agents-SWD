# Scheduler Architecture Decision — Step 66C.4-P

> **Planning document only. No scheduler created or activated. No new service deployed. This
> document recommends an architecture for a later implementation stage (66C.4-BE2) to build — it
> does not build one itself.**

## Problem statement

24h/72h clarification timeout is a **due-timestamp** problem: nothing publishes an event when a
timestamp passes. This is fundamentally different from every existing background loop in this
repository (`retry-scheduler`, `audit-worker`, `notification-worker`), which are all **event-driven
Redis Streams consumers** reacting to messages already published to a stream — confirmed by direct
inspection (current-state-assessment.md §6). A due-timestamp checker requires either periodic
polling or a delayed-message mechanism; it cannot be pure event consumption, since no "24 hours
have passed" event exists to consume.

## Options compared

### Option 1 — Reuse existing scheduler/worker pattern (Redis Streams delayed message)

At clarification-creation time, publish a message to a new stream (e.g. `stream.clarification-
timeout`) carrying `clarification_id`, `reminder_at`, `due_at`. A dedicated consumer reads the
stream and, mirroring `retry-scheduler`'s own `asyncio.sleep(delay)` backoff pattern
(`apps/retry-scheduler/src/scheduler.py`), sleeps until the earlier of `reminder_at`/`due_at`, then
attempts the CAS claim.

### Option 2 — Dedicated clarification-timeout worker with DB polling

A new, small standalone service (deployment shape identical to `retry-scheduler`: its own
container, its own health check) that polls Postgres on a fixed interval (proposed: 60 seconds)
for rows matching `WHERE status='open' AND (reminder_at<=now() AND reminder_sent_at IS NULL OR
due_at<=now())`, claims each match via the existing CAS pattern, and publishes an internal Redis
Streams event for `notification-worker` to consume for each claimed transition.

### Option 3 — Outbox + Redis Streams scheduled processing

Build a new outbox table (write the "check me at time T" intent transactionally alongside the
clarification row), plus a relay process that scans the outbox and publishes to Redis Streams at
the right time. Requires an outbox pattern that **does not exist anywhere in this repository**
(confirmed zero hits, current-state-assessment.md §6).

### Option 4 — Application-local periodic task inside the orchestrator process

An `asyncio` periodic task started at orchestrator process startup, running the same polling query
as Option 2 but embedded in the existing orchestrator service rather than a separate container.

## Comparison

| Criterion | Option 1 (delayed message) | Option 2 (dedicated DB poller) | Option 3 (outbox) | Option 4 (in-process periodic) |
| --- | --- | --- | --- | --- |
| Reliability | Good, but message loss on stream trim/consumer-group misconfiguration is a real risk for a 24-72h-delayed message | High — a poll query against the row's own persisted timestamp is self-healing on every run, no message to lose | High, but adds a new failure surface (the outbox relay itself) | High (same query), but tied to orchestrator's own liveness |
| Horizontal scaling | Requires care: multiple consumers on the same stream/group is fine (Streams handle this natively) | Requires a claim/lock strategy across replicas (the CAS guard already provides this for free) | Requires the same care as Option 2, plus relay-replica coordination | Multiple orchestrator replicas would each run the periodic task — redundant polling, though harmless due to CAS |
| Leader election | Not needed (Streams consumer groups distribute work) | Not needed — CAS guard makes concurrent claims from multiple poller replicas safe by construction (a losing UPDATE simply returns no row, exactly like the existing answer-claim) | Not needed for the same reason as Option 2, plus the relay itself would need one | Not needed, same CAS reasoning, but wasteful duplicate polling across replicas |
| Duplicate execution | Streams consumer groups prevent re-delivery to a different consumer once ack'd, but a 24-72h in-flight delayed message is an unusual Streams usage pattern this project has never exercised | Prevented entirely by the CAS guard (`WHERE reminder_sent_at IS NULL` / `WHERE status='open'`) — the same mechanism already proven correct for the answer-claim race (Step 66C.3 G5) | Same protection as Option 2 at the final claim step, but the outbox-to-stream relay step introduces its own duplicate-publish risk | Same CAS protection, but duplicate polling work across replicas |
| DB load | Low (no polling; message-driven) | Low — a single indexed query every 60s against a small, indexed row set (partial indexes proposed in data-model-contract.md) is negligible load | Low for the query itself, but adds outbox-table writes on every clarification creation | Same as Option 2 |
| Redis dependency | High — depends on a long-lived in-flight message surviving for up to 72 hours, an untested usage pattern for this project's Redis Streams setup | None beyond the existing notification-worker's own stream consumption (only used for the OUTPUT event, not the trigger) | High (same as Option 1) plus an outbox relay | None (same as Option 2) |
| Restart recovery | A consumer restart mid-sleep must re-read its position from the stream — untested for a multi-day sleep window | Trivial — the next poll cycle after restart re-evaluates the same due-timestamp query against the database, which is unaffected by the poller's own restart | Same as Option 2 for the final step, plus the relay's own restart-recovery burden | Trivial, same as Option 2, but tied to orchestrator's own restart cadence |
| Observability | Requires Streams-specific tooling (consumer lag, pending-entries list) that this project has not built dashboards for | Simple: poll-cycle count, rows-claimed count, poll-cycle duration — standard metrics, no new tooling needed | Same as Option 2 plus outbox-lag metrics | Same as Option 2, but bundled into the orchestrator's own health/metrics, less clean isolation |
| Testability | Harder — a 24-72h delayed message is awkward to exercise in a fast test suite (needs message-time-travel or artificially short delays) | Easy — the poll query is a plain SQL statement over rows with arbitrary `created_at`/`due_at` values; tests can insert rows with past-due timestamps directly, no time manipulation needed | Same testability challenge as Option 2 for the query, plus the relay adds another component to test | Same testability as Option 2 |
| Deployment complexity | Medium — reuses existing Redis Streams infra, but the consumer's sleep-based backoff logic for a multi-day delay is new, untested code | Low — a new, small, single-purpose service, structurally identical to the already-proven `retry-scheduler` deployment shape | High — new outbox table, new relay service, new stream, three new moving parts | Lowest deployment footprint (no new service), but couples an operational concern to the orchestrator's own release/restart cycle |
| Failure isolation | A scheduler bug could affect the shared Redis Streams infra other services depend on | A poller bug is isolated to its own container — it cannot affect the orchestrator, retry-scheduler, or any other service, matching this project's existing security-governance principle of isolated failure domains | A relay bug affects only the outbox pipeline, but is still a new failure domain to isolate | A poller bug inside the orchestrator process risks affecting the orchestrator's own primary responsibilities (task/workroom API serving) |

## Recommended architecture: **Option 2 — Dedicated clarification-timeout worker with DB polling**

```text
Rationale:
1. It is the only option requiring NO new infrastructure pattern (no outbox, no untested
   long-delay Streams usage) — it reuses only what already exists proven-correct: the CAS
   guard (Step 66C.3 G5) and the existing service-per-container deployment shape
   (retry-scheduler as direct precedent).
2. Reliability and restart-recovery are trivial because the query re-derives its own correctness
   from persisted state every cycle — there is no in-flight state to lose.
3. It is the most testable option by a wide margin, which matters directly for
   test-and-validation-plan.md's unit/integration test requirements.
4. Failure isolation matches this project's established governance principle (isolated services,
   no shared-blast-radius background jobs) better than Option 4, and with far less new-infra risk
   than Options 1/3.
5. DB load is provably negligible given the current data volume (read-only evidence: 6 total
   clarification rows in the test environment; even at much larger production scale, an
   indexed poll every 60s over an `open`-status partial index is cheap).

Service ownership: Claude Code (new, small standalone service — deployment shape identical to
  retry-scheduler; a new container, e.g. `apps/clarification-scheduler/`).
Polling/trigger interval: 60 seconds (matches the project's tolerance for "up to several minutes
  of delay" stated in lifecycle-and-time-contract.md §7.1; far more frequent than needed for an
  hour-granularity human-facing deadline, chosen for responsiveness margin, not because tighter
  precision is required).
Batch size: recommend up to 100 rows per poll cycle (generous headroom over current/foreseeable
  volume; a LIMIT clause on the poll query prevents an unbounded single-cycle query if row counts
  grow unexpectedly).
Locking strategy: the existing CAS-via-WHERE-clause guard, no new locking primitive.
Retry policy: a claimed-but-failed-to-process row (e.g. DB commit succeeds but the follow-on audit
  write fails) is handled by the same two-phase pattern the existing answer-claim already uses —
  claim first (cheap, atomic), then perform side effects; if a side effect fails, the row is
  already in its terminal claimed state and the failure is logged/retried at the notification-
  event level (see race-condition-and-failure-analysis.md scenarios 10-11), not by re-attempting
  the claim.
Dead-letter behavior: a side-effect failure (e.g. notification-event publish failure) reuses the
  EXISTING `retry-scheduler`/DLQ infrastructure (`stream.deadletter`) rather than inventing a new
  one — the clarification-timeout worker publishes its notification event the same way any other
  service does, and if that publish fails, existing DLQ/retry mechanics apply unchanged.
Metrics: poll-cycle count, poll-cycle duration, rows-claimed-per-cycle (split by reminder/expiry),
  claim-conflict count (rows where the CAS lost the race, expected to be near-zero but useful as a
  correctness signal).
Health checks: standard container healthcheck (matches every other service in this project) plus
  a "last successful poll cycle timestamp" metric to detect a stalled worker (see
  observability-and-audit-plan.md).
Shutdown behavior: graceful — finish the in-flight poll cycle's already-claimed rows' side effects
  before exiting; a mid-cycle unclaimed row is picked up by the next poll cycle after restart with
  no special handling needed (idempotent by construction).
```

## Statement

Planning document only. No scheduler created or activated. No new service deployed. This document
recommends an architecture for a later implementation stage to build — it does not build one
itself.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
