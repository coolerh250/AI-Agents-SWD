# Step 66C.4-BE2-R — Transaction & Concurrency Review

> **Independent review. Reviewer did not implement the code. Evidence gathered on an isolated
> ephemeral PostgreSQL 16 + Redis 7 stack on the internal test runtime. Nothing deployed.**

Reviewed commit: `319123b`.

## 7. State/outbox transaction atomicity — PASS (except the 6.3 partial-consistency gap)

Independently on PG16:

1. Reminder state + outbox commit together — PASS (one transaction; both or neither).
2. Expiry clarification + task + outbox commit together — PASS on the happy path.
3. Task-update failure → all rollback — PASS. Injected a failure on the `operator_tasks` UPDATE;
   the clarification stayed `open` and zero outbox rows existed.
4. Outbox-insert failure → all rollback — PASS (the `UniqueViolationError` path rolls back and is
   surfaced as a reconciliation outcome, not swallowed as success).
5. Process termination before commit → no partial data — PASS. A crash before `tx.commit()` leaves
   the row unclaimed (SKIP LOCKED) and no state/outbox write.
6. Duplicate idempotency collision NOT silently success — PASS. The poller returns a `reconcile`
   outcome, rolls back, increments `clarification_reconciliation_failures_total`, and skips the row
   for the rest of the cycle.
7. State changed but outbox missing → explicit reconciliation — PARTIAL. For the outbox-collision
   case this is explicit. For the §6.3 task/clarification mismatch it is NOT explicit (see below).

The BE1 repository (`insert_lifecycle_outbox_event`) is transaction-aware: it never opens its own
connection, never commits, never closes, and surfaces integrity errors to the caller. The relay's
`_process_claimed` runs inside the claiming transaction and does not autocommit or retry across the
caller boundary. Confirmed by reading and by the injected-failure reproductions.

**Carried gap from the poller review §6.3 (BLOCKING):** the expiry transaction commits
clarification=`expired` + outbox `clarification.expired` while a task in an unexpected state is left
unchanged with no observable reconciliation. That is a partial-consistency outcome and drives the
technical verdict.

## 9. DB transaction across the Redis publish — REMEDIATION_REQUIRED (BLOCKING)

The relay's `publish_one` does exactly the pattern §9 flags:

```
tx.start()                              # BEGIN
SELECT ... FOR UPDATE SKIP LOCKED       # row locked
await publish_audit_event(...)          # Redis XADD, awaited INSIDE the open txn
UPDATE clarification_lifecycle_outbox   # mark published/retry/dead
tx.commit()
```

The Redis XADD is awaited **while the DB transaction is open and the outbox row is locked**. The
critical question is whether that await is time-bounded. It is not:

```
redis socket_timeout        : None
redis socket_connect_timeout: None
```

`RedisStreamEventBus` builds its client with `aioredis.from_url(url, decode_responses=True)` — no
`socket_timeout`, no `socket_connect_timeout` — and neither `publish_audit_event` nor the relay wraps
the publish in `asyncio.wait_for`. On an established connection to a hung/black-holed broker there is
no read timeout, so the await blocks until the OS TCP stack gives up (can be minutes).

Independent reproduction (Redis 7, `docker pause` to simulate a hung broker on an already-open
connection):

```
first publish (redis up)    : published
redis PAUSED (hung broker on an established connection)
[t+2s] row B: {'row_status': 'pending', 'claimable_by_other_worker': False}
publish_one STILL BLOCKED after 14.1s holding the DB txn + row lock
=> NO bounded Redis timeout
redis UNPAUSED
blocked publish finally returned after 14.5s
```

At t+2s a second connection's `FOR UPDATE SKIP LOCKED` could not claim row B
(`claimable_by_other_worker=False`) and the row was still `pending` — proving the DB transaction and
the row lock are held for the entire hang. Per §9 the absence of a bounded timeout is
**REMEDIATION_REQUIRED**.

Assessment of the sub-questions:

- Row-lock hold time / DB-transaction hold time: unbounded (= Redis hang duration).
- Redis publish timeout: none (no `socket_timeout`, no `wait_for`).
- Other workers can still `SKIP LOCKED` OTHER rows — mitigates single-row blocking, but every relay
  worker shares one Redis; a real Redis hang blocks ALL workers at once, each holding an open DB
  transaction and connection → **DB-side connection exhaustion is possible** (each stuck worker holds
  a dedicated `asyncpg.connect` with an open transaction; there is no shared pool cap to protect the
  server's `max_connections`).
- Shutdown: bounded only at process stop — the lifespan does
  `wait_for(loop_task, shutdown_timeout=30s)` then `loop_task.cancel()`, which raises
  `CancelledError` at the XADD await. So a hung publish is torn down at shutdown, but during normal
  running there is no 30s (or any) bound; the worker is stuck until Redis recovers or the process is
  restarted.

Recommended remediation (NOT performed here): give the publish a bounded upper limit — either a
`socket_timeout`/`socket_connect_timeout` on the Redis client or an `asyncio.wait_for` around the
publish — so a hung broker rolls the transaction back and persists a retry instead of pinning the
transaction, row lock, and DB connection.

## Concurrency summary

FOR UPDATE SKIP LOCKED gives correct exactly-one claiming for both the poller and the relay (verified
two-worker reproductions: `[0, 1]`). The claim is never held across a process boundary, so no
lease/owner column is needed and a crash rolls the claim back. The concurrency model is sound; the
blocking issue is the *duration* a claim can be held when Redis hangs (§9), not the claiming
mechanism.

---

_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
