# Step 66C.4-BE2-R — Failure-Recovery, Retry & Dead Review

> **Independent review. Reviewer did not implement the code. Evidence gathered on an isolated
> ephemeral PostgreSQL 16 + Redis 7 stack on the internal test runtime. Nothing deployed.**

Reviewed commit: `319123b`.

## 11. Retry / dead semantics — PASS (no off-by-one), one LOW discrepancy

`plan_retry_state(attempts, error)` in `shared/sdk/tasks/lifecycle_outbox.py`:
`next_attempts = attempts + 1`; if `next_attempts >= MAX_DELIVERY_ATTEMPTS (=4)` → `dead`, else
`pending` with `backoff = RETRY_BACKOFF_SECONDS[next_attempts - 1]`.

Independent reproduction with a real failing publisher (every attempt fails, `available_at` pulled
back each cycle so it re-claims immediately):

```
cycle 0: outcome=retry -> status=pending attempts=1
cycle 1: outcome=retry -> status=pending attempts=2
cycle 2: outcome=retry -> status=pending attempts=3
cycle 3: outcome=dead  -> status=dead   attempts=4
TOTAL real publish attempts before dead: 4
plan_retry_state trace:
  attempts_in=0 -> next=1 status=pending backoff=30
  attempts_in=1 -> next=2 status=pending backoff=120
  attempts_in=2 -> next=3 status=pending backoff=600
  attempts_in=3 -> next=4 status=dead    backoff=None
RETRY_BACKOFF_SECONDS=(30, 120, 600, 3600) MAX_DELIVERY_ATTEMPTS=4
```

Explicit answers to the §11 questions:

- `attempts` initial value: **0** (DB default).
- `attempts` after first failure: **1**.
- Does the 4th failure schedule a 3600s retry or go straight to dead? **Straight to dead.** The 4th
  failure (from `attempts=3`) yields `next_attempts=4 >= 4` → `dead`; no backoff is scheduled.
- Which failure enters dead: the **4th** publish failure.
- How many actual publish attempts total: **exactly 4** (verified above).

There is **no off-by-one**: the attempt budget is respected (4 attempts, bounded, terminal `dead`
with `dead_at` set and a bounded `last_error`). Restart resumes by `available_at` (verified: a fresh
instance picks up a due row).

**LOW discrepancy (not blocking):** `RETRY_BACKOFF_SECONDS[3] = 3600` is **dead code** — the index
only ever reaches `0..2`, so the effective schedule is `30 / 120 / 600 → dead`, not
`30 / 120 / 600 / 3600`. The module comment *"the LAST entry is not a cap on time but the final
delay"* is inaccurate: the last entry is never applied. This does not violate "4 bounded attempts"
(4 attempts do occur), but it does not match the stated `30/120/600/3600` schedule either. Product
Owner should confirm the intent: either the tuple should have 3 entries, or 3600 should be documented
as intentionally reserved / the budget widened to 5. Recorded for PO decision; it does not by itself
change the verdict.

### Error classification

- Transient (Redis unavailable / timeout / connection reset): the transport raises → `_bounded_error`
  → `PublishResult(False)`, or the publisher returns `None` → `PublishResult(False, "publish_dropped")`.
  Either way it schedules a FUTURE `available_at`, so a single outage cannot burn the whole budget in
  a tight loop (the row is not re-eligible until the backoff elapses). Verified: "Redis unavailable →
  persisted retry; nothing lost."
- Permanent/poison (invalid schema, payload rejected, unsupported type): these are rejected at INSERT
  time by the BE1 positive allowlist, so a poison payload never reaches the relay as a pending row.
  A publish that keeps failing still terminates in `dead` after 4 attempts — it does not retry
  forever.
- `last_error` is bounded to the exception CLASS name only (`type(exc).__name__[:500]`), free of raw
  payload/DSN/secret (see the observability & security review).
- `dead_at`/`published_at` constraints: enforced by the DB `chk_clo_status_timestamps` CHECK; a dead
  row has `dead_at` set and `published_at` NULL.

## 17 (relay half) — mandatory recovery reproductions

Reproduced on the ephemeral stack: publish success; future `available_at` exclusion; transient retry;
bounded dead transition; retry (no off-by-one); permanent handling; acknowledgment loss with
same-identity resend; two-worker single claim; Redis unavailable → persisted retry; Redis recovery →
publish; restart recovery; replay mapping. Plus the §9 Redis-hang (`docker pause`) reproduction. All
behaved as recorded; the vendor suite (28 tests) also passes green against the same stack with
0 skipped.

---

_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
