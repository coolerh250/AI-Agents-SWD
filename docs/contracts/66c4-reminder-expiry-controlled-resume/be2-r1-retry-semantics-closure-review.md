# Step 66C.4-BE2-R1-R — Retry / Dead Semantics Closure Review

> Independent review record. Not deployed. Not a merge authorization. No shared activation.

## Original finding (c70f205, LOW)

`RETRY_BACKOFF_SECONDS[3]=3600` was dead code — the effective schedule was `30/120/600 -> dead`,
the final 3600s backoff never reached. Attempt budget was otherwise correct (no lost events).

## What the code does now (`shared/sdk/tasks/lifecycle_outbox.py`, `plan_retry_state`)

```text
RETRY_BACKOFF_SECONDS = (30, 120, 600, 3600)
MAX_RETRIES           = 4   (len of the schedule)
MAX_PUBLISH_ATTEMPTS  = 5   (MAX_RETRIES + 1; the 5th failure is terminal)

next_attempts = attempts + 1
if next_attempts >= MAX_PUBLISH_ATTEMPTS: -> dead (set_dead_at, backoff None)
else: -> pending, backoff = RETRY_BACKOFF_SECONDS[next_attempts - 1]
```

Drive from attempts=0:

```text
attempt 1 fails -> attempts=1, +30s
attempt 2 fails -> attempts=2, +120s
attempt 3 fails -> attempts=3, +600s
attempt 4 fails -> attempts=4, +3600s   <-- the previously-dead-code branch, now REACHED
attempt 5 fails -> attempts=5, dead
```

Index range for the retry branch is `next_attempts-1` ∈ [0,3] (next_attempts ≤ 4 when pending), so
no `IndexError`; the 3600 entry (index 3) is reached exactly at attempt 4.

## Poison vs transient

R1's binding decision (PO 1.2) is that **poison and transient failures both consume the same
bounded 5-attempt schedule** — there is no immediate-dead classification. A persistently failing
row therefore cannot tight-loop; each failure schedules a FUTURE `available_at` and the row dies
only after the 5th attempt. This is documented consistently across:
`data-model-contract.md` (exact schedule + "no immediate-dead classification"),
`lifecycle-and-time-contract.md §7.3C`, `outbox_relay.py`/`lifecycle_outbox.py` docstrings, and
`be2-r1-retry-semantics-record.md`. No document asserts immediate-dead anywhere — checked by
grep across the contract set.

## Independent verification (real PostgreSQL 16)

```text
planner sequence (unit)                  -> [(pending,30,1),(pending,120,2),(pending,600,3),
                                            (pending,3600,4),(dead,None,5)]                       PASS
poison row driven through 5 real failures -> retry x4 then dead; attempts=5; dead_at set;
   (always-fail bus)                        published_at NULL; last_error bounded 'publish_dropped'
                                            (no message/DSN/payload)                              PASS
restart gating                            -> a fresh poll BEFORE the persisted backoff elapses is a
                                            no-op (publish_one returns None); the row is only
                                            re-eligible once available_at passes -> a restart
                                            continues from persisted available_at, never tight-loops PASS
historical BE2 dead-attempts assertion    -> updated 4 -> 5 (MAX_PUBLISH_ATTEMPTS), still asserts
                                            no 'redis' substring in last_error                    PASS
```

Attempt vs retry terminology is consistent: `MAX_RETRIES=4` scheduled retries across
`MAX_PUBLISH_ATTEMPTS=5` total attempts; metrics (`outbox_retry_scheduled_total`,
`outbox_dead_total`) and diagnostics agree. `MAX_DELIVERY_ATTEMPTS` survives only in a test comment
(no code reference) — informational.

## Verdict

**Retry/dead: CLOSED.**

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
