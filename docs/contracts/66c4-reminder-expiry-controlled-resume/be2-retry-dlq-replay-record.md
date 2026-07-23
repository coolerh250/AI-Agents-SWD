# Step 66C.4-BE2 Retry / DLQ / Replay Record

> **Implementation record. NOT deployed. No public replay endpoint. No external notification.**

## Retry schedule (BE1-approved, applied by the relay)

```text
Backoff:          30s, 120s, 600s, 3600s   (RETRY_BACKOFF_SECONDS)
Bounded attempts: 4                          (MAX_DELIVERY_ATTEMPTS)
```

Each transient failure:

```text
attempts += 1
available_at = statement_timestamp() + backoff[attempts-1]
last_error   = bounded, secret-free reason (exception class name only)
status       = 'pending'  (persisted backoff; the row is NOT eligible again until available_at)
```

Because `available_at` is persisted and the claim guard is `available_at <= statement_timestamp()`,
a publisher outage cannot burn the whole attempt budget in a tight loop, and a restart resumes from
the persisted schedule (verified: a fresh relay drains the backlog once rows become eligible).

## Dead / DLQ terminal

Retry exhausted:

```text
status       = 'dead'
dead_at      = statement_timestamp()
published_at = NULL
last_error   = the final bounded, secret-free reason (retained for operator diagnosis)
```

A dead row is a diagnosable operator-reconciliation item (dead_at + last_error). The relay does not
retry a dead row. `clarification_outbox_dead_total` and `clarification_outbox_oldest_pending_age_seconds`
surface DLQ/backlog state. Routing dead rows onward to the existing `stream.deadletter` /
retry-scheduler DLQ is a downstream concern and is NOT performed here (no external side effect in
BE2); the persisted `dead` row is the durable record an operator or a later stage reconciles.

## Operator replay foundation (internal only)

`ClarificationOutboxRelay.replay_dead(event_id)` -- an internal repository/service method with NO
public API and NO Admin Console control (verified: neither the orchestrator nor the admin-console
references it).

```text
Transition:   dead -> pending
id:           preserved
idempotency_key: preserved
attempts:     NOT reset (full delivery-attempt history preserved as evidence)
status:       'pending'
available_at: statement_timestamp() (immediately eligible)
dead_at:      NULL
last_error:   NULL (the failure reason is not retained on the live row after replay)
```

Replay audit evidence: once the row is pending again, the relay's normal publication path emits it
with its UNCHANGED idempotency_key, so the replay produces evidence through the existing durable
destination -- `replay_dead` itself performs NO live publication. Verified on ephemeral PostgreSQL
16: a dead row replays to pending with attempts=4 preserved, dead_at/last_error cleared, eligible
immediately, idempotency_key unchanged; replaying a non-dead row is a no-op (returns False).

## Failure and reconciliation coverage (ephemeral PostgreSQL 16 + Redis 7)

```text
state + outbox rollback on injected failure (poller)                  PASS
outbox row exists but publish not yet performed -> stays pending      PASS
publish success but DB ack lost -> re-publish reuses event identity   PASS
poison payload -> terminal dead, not retried forever                  PASS
Redis recovery -> pending backlog drained over cycles                 PASS
stuck-pending age metric + dead metric move                           PASS (gauges/counters set)
operator replay foundation (dead -> pending)                          PASS
```

## Statement

Implementation record only. No deployment. No relay activation in any shared runtime. No public
replay endpoint. No dispatch/resume. No external notification. No production or external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
