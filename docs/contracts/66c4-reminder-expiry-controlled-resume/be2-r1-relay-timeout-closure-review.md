# Step 66C.4-BE2-R1-R — B-2 Bounded Relay Publish Closure Review

> Independent review record. Not deployed. Not a merge authorization. No shared activation.

## Original finding (c70f205, B-2)

Unbounded Redis publish inside the open DB transaction / row lock: the relay awaited the publish
with a default Redis client (no socket timeout) while holding `FOR UPDATE SKIP LOCKED` on the
outbox row inside a live transaction. A hung broker could pin the transaction, the row lock, and
the connection indefinitely.

## What the code does now

`shared/sdk/tasks/outbox_relay.py`:
- `publish_timeout_seconds` config: default 5s (or `CLARIFICATION_OUTBOX_PUBLISH_TIMEOUT_SECONDS`),
  range [1, 30]; `_resolve_publish_timeout` REJECTS out-of-range at construction (raises
  `ValueError`) — no silent clamp.
- The default bus is built as `RedisStreamEventBus(socket_timeout=..., socket_connect_timeout=...)`
  (both non-None) so the transport cannot block forever.
- `_publish` wraps the publish in `asyncio.wait_for(publish_audit_event(...),
  timeout=self.publish_timeout_seconds)` — a TOTAL await bound on top of the socket timeout.
- `asyncio.TimeoutError` -> `PublishResult(False, PUBLISH_TIMEOUT_REASON='redis_publish_timeout')`
  (transient retry, never `published`).
- `asyncio.CancelledError` -> re-raised (NOT swallowed as transient).
- `publish_one` wraps `_process_claimed` in `except BaseException: rollback; raise` so a
  cancellation during publish rolls the transaction back (releasing the row lock) then propagates.

`shared/sdk/event_bus/redis_streams.py`: the change is purely additive — two keyword-only optional
kwargs (`socket_timeout`, `socket_connect_timeout`, default None). When None the `from_url` call is
byte-for-byte the prior behaviour; `publish_event`/XADD is unchanged (zero diff lines).

## Independent verification

Real PostgreSQL 16 + fake hanging bus (PG-side lock evidence) AND real Redis 7:

```text
real-Redis normal publish (5s bound)     -> row 'published', published_at set, last_error NULL,
                                            event lands on stream.audit (xlen +1)                PASS
real-Redis broker hang (docker pause,                                                            PASS
   socket=2s, total=2s)                   -> publish returns < 10s (not forever), outcome 'retry',
                                            row pending, attempts=1, no published_at/dead_at,
                                            last_error in {redis_publish_timeout, publish_dropped},
                                            no "://" in reason
fake broker hang (60s sleep), total=1s    -> returns < 5s, 'retry', pending, attempts=1,
                                            available_at future, last_error redis_publish_timeout;
                                            a SEPARATE connection updates the row within 5s
                                            (row lock released)                                   PASS
shutdown cancellation mid-publish         -> CancelledError re-raised, txn rolled back, row pending
                                            attempts=0, no published_at/dead_at                   PASS
3 rows all hang, single cycle             -> {published:0, retry:3, dead:0}, each attempts=1,
                                            connection reusable afterwards (no pin/leak)          PASS
publish timeout range                     -> 1/5/30 accepted; 0/0.9/31/100/-1 rejected           PASS
default bus socket+connect timeouts set   -> both non-None                                        PASS
```

## Ambiguous XADD outcome (ack loss)

On a total-timeout the coroutine is cancelled; if the XADD had actually reached the broker the row
is still treated as a transient retry and re-published later from the SAME persisted outbox row —
identical `event_id` (`id`), `idempotency_key`, `event_type`, and `payload`. The delivery model
remains at-least-once (documented in `api-and-event-contract.md §11` and the relay docstring); a
duplicate is possible and acceptable, a lost event is not.

## Pool saturation note

Each hung publish holds exactly one connection for at most the bounded timeout, then releases it;
`SKIP LOCKED` lets other rows/workers proceed. Under the default 5s bound and normal batch sizing
this does not saturate the pool. No additional operational limit is required at BE2 (nothing is
activated); should a shared deployment run many relay workers, the standard connection-pool sizing
+ the existing backlog/last-success health signals apply.

## Verdict

**B-2: CLOSED.**

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
