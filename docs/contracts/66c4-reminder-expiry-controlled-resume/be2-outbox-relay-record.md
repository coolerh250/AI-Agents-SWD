# Step 66C.4-BE2 Outbox Relay Record

> **Implementation record. Evidence gathered on isolated ephemeral PostgreSQL 16 + Redis 7. NOT
> deployed. Existing audit/event transport unchanged. No external notification.**

## Module

`shared/sdk/tasks/outbox_relay.py` -- `ClarificationOutboxRelay`.

## Single durable destination (BE2 decision, per stage prompt §11)

The stage prompt required resolving the delivery destination BEFORE implementing, and preferring a
single canonical durable destination with downstream projection over a multi-destination fan-out
that the single-status outbox schema cannot track per-destination.

```text
Question 1 (Redis Streams + existing consumer for the audit projection?):  YES -- chosen.
Question 2 (relay calls audit publisher AND event bus separately?):        NO -- rejected.
Question 3 (how does the schema record partial success?):                  it cannot, and it does
  not need to, because there is exactly ONE destination.
```

Decision: the relay publishes each outbox row to the canonical audit stream via the existing
`shared/sdk/audit/publisher.py::publish_audit_event`. That entry point returns the Redis XADD id on
success and `None` on a drop -- a reliable per-publish success/failure signal, which is exactly what
a relay needs and what the best-effort publisher cannot give a synchronous hot path. The existing
`audit-worker` consumes `stream.audit` and produces the durable audit projection (`audit_logs`)
DOWNSTREAM. This is one durable destination with downstream projection; there is no per-destination
partial-success state to track, and NO transport implementation is rewritten.

The `event_id` (outbox row id) and the deterministic `idempotency_key` travel in `artifact_refs`,
so a downstream consumer can deduplicate. `workflow_id` is empty (no workflow-engine integration
exists yet, per the canonical contract).

This is NOT a fan-out to multiple independent destinations, so the "publish A succeeds / B fails ->
mark published" hazard the stage prompt forbids cannot occur, and audit failure is never silently
dropped: a `None` return is treated as a definite failure and scheduled for persisted retry.

## Claim model (canonical, binding)

```sql
SELECT * FROM clarification_lifecycle_outbox
WHERE status='pending' AND available_at <= statement_timestamp()
ORDER BY available_at, created_at
FOR UPDATE SKIP LOCKED
LIMIT 1
```

The claim is held only inside the relay's own transaction and never across a process/transaction
boundary, so no claim-owner/lease column is needed and a worker crash rolls the claim back. The
publication happens inside the claiming transaction; a definite success commits `published`, a
definite failure commits the retry/dead update.

## Success / failure transitions

```text
Success:  status='published', published_at=statement_timestamp(), last_error=NULL.
Failure (transient, attempts+1 < cap):
          attempts+1; available_at=statement_timestamp() + backoff; last_error=bounded reason;
          status stays 'pending' (persisted backoff -- NOT retried in a tight loop).
Failure (attempts+1 >= cap): status='dead', dead_at=statement_timestamp(), published_at=NULL,
          last_error retained (bounded, secret-free).
```

Backoff/dead are computed by BE1's `plan_retry_state`; the relay only applies the returned values.
`last_error` is the exception CLASS name only (never a message that could echo a DSN/payload/token),
bounded to the BE1 500-char limit and the DB CHECK.

## Delivery semantics

AT-LEAST-ONCE with a deterministic idempotency identity (idempotency_key + event_id). EXACTLY-ONCE
is explicitly NOT claimed. Publish-succeeds-but-DB-ack-fails is allowed to re-publish; the re-publish
carries the SAME event_id and idempotency_key, so downstream dedupes.

## Evidence (ephemeral PostgreSQL 16 + Redis 7)

```text
pending + eligible -> published (real Redis); published_at set, last_error cleared   PASS
future available_at -> not claimed                                                   PASS
transient failure -> one retry scheduled, attempts=1, future available_at,
  last_error='publish_dropped' (bounded); budget NOT exhausted in one cycle          PASS
retry then success (real Redis); attempts preserved across the retry                 PASS
attempts exhausted -> dead, dead_at set, published_at NULL, attempts=4,
  last_error bounded and free of raw transport text                                  PASS
two concurrent relays -> exactly one claim (real Redis)                              PASS
crash before commit -> row remains pending/attempts=0/recoverable                    PASS
Redis unavailable -> persisted retry; nothing lost                                   PASS
restart drains the pending backlog once eligible (3 rows published)                  PASS
ack-failure re-publish reuses the SAME event_id + idempotency_key                    PASS
```

## Statement

Implementation record only. No deployment. No relay activation in any shared runtime. No existing
producer cutover. No audit/event transport change. No external notification. No production or
external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
