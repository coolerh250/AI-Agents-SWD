# Step 66C.4-BE2-R1 — Bounded Relay Publish Record (B-2)

> **Remediation record. NOT deployed. NOT runtime validated.**

## Finding (independent review, confirmed)

`publish_one` held the DB transaction and the claimed row's `FOR UPDATE SKIP LOCKED` lock across the
Redis `XADD`, and the Redis client was built with `socket_timeout=None` /
`socket_connect_timeout=None` with no `asyncio.wait_for`. A hung broker (reproduced with
`docker pause`: publish still blocked after 14.1s holding the txn/lock) risked pinning the DB
transaction, row lock, and connection — a connection-exhaustion vector under multiple workers.

## Remediation (PO decision 1.3)

```text
- Redis client (relay's default bus) is built with non-None socket_timeout and
  socket_connect_timeout (RedisStreamEventBus gained optional, backward-compatible kwargs;
  default None preserves every existing caller).
- The publish await is capped by asyncio.wait_for(publish_audit_event(...),
  timeout=self.publish_timeout_seconds).
- publish_timeout_seconds: default 5s, configurable in [1, 30]s (env
  CLARIFICATION_OUTBOX_PUBLISH_TIMEOUT_SECONDS or constructor). Out-of-range is REJECTED at
  construction (_resolve_publish_timeout raises ValueError) -- never silently clamped.
- Timeout -> TRANSIENT failure: PublishResult(False, "redis_publish_timeout"); the row gets
  attempts += 1, a persisted future available_at, and status stays pending. NEVER marked published.
- asyncio.CancelledError (shutdown) is re-raised, NOT swallowed as transient. publish_one's
  `except BaseException` rolls the transaction back first, so the row stays pending and the lock is
  released -- recoverable later with the same event_id/idempotency_key.
```

`last_error` for a timeout is the fixed safe label `redis_publish_timeout` — never a DSN, host,
password, payload, or raw exception repr.

## Why additive on RedisStreamEventBus

The relay publishes via the existing `publish_audit_event(event_bus=...)`, whose only Redis client
is `RedisStreamEventBus`. Bounding the client therefore requires a bounded-timeout bus. The kwargs
are additive and default to None, so no existing producer's behavior changes (regression suite
confirms). This is the authorized "Redis client timeout" fix (BE2-R1 §2 item 4), not a transport
rewrite or producer cutover; the audit producer path (`shared/sdk/audit/`) is unchanged.

## Tests (real PostgreSQL 16 + injected fake bus; no live Redis needed)

```text
test_pg_b2_broker_hang_times_out_to_retry_without_pinning_txn   (bounded; row lock released; not published)
test_pg_b2_shutdown_cancellation_rolls_back_and_reraises        (row stays pending, attempts=0)
test_pg_b2_multiple_rows_all_processable_under_broker_hang      (no pinned rows / pool pressure)
DB-less: default 5s, range [1,30] rejected out of range, bus socket timeouts not None, wait_for present.
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
