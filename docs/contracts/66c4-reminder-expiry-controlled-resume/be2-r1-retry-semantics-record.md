# Step 66C.4-BE2-R1 — Retry / Dead Semantics Record (PO decision 1.2)

> **Remediation record. NOT deployed. NOT runtime validated.**

## Finding (independent review, LOW — documentation/behavior mismatch)

`RETRY_BACKOFF_SECONDS[3] = 3600` was dead code: the old threshold `next_attempts >=
MAX_DELIVERY_ATTEMPTS (4)` moved a row to dead at the 4th attempt, so the advertised
`30/120/600/3600` schedule actually ran `30/120/600 -> dead`. PO decision 1.2 makes the semantics
exact and reaches every backoff.

## Remediation

`shared/sdk/tasks/lifecycle_outbox.py`:

```text
RETRY_BACKOFF_SECONDS = (30, 120, 600, 3600)
MAX_RETRIES           = len(RETRY_BACKOFF_SECONDS)  # 4 scheduled retries, every backoff reached
MAX_PUBLISH_ATTEMPTS  = MAX_RETRIES + 1             # 5 total attempts; the 5th failure is terminal

plan_retry_state: dead iff next_attempts >= MAX_PUBLISH_ATTEMPTS.
```

State evolution (verified by test):

```text
attempt 1 fails -> attempts=1, +30s
attempt 2 fails -> attempts=2, +120s
attempt 3 fails -> attempts=3, +600s
attempt 4 fails -> attempts=4, +3600s     <-- previously unreachable, now exercised
attempt 5 fails -> attempts=5, status=dead, dead_at := statement_timestamp()
```

`MAX_DELIVERY_ATTEMPTS` (the vague "attempt budget = 4") is removed; the one reference in
`tests/test_step66c4_be1_r1_remediation.py` was updated to `MAX_PUBLISH_ATTEMPTS`.

## Error classification (PO decision §6)

There is no immediate-dead classification: every failure — transient (timeout, Redis unavailable,
connection reset) or poison (unsupported event type, invalid envelope, serialization failure) —
consumes exactly one attempt. A persistently-failing row therefore cannot tight-loop; it dies after
the bounded schedule with a bounded, secret-free `last_error` and a dead metric. This uniform model
is documented here and asserted by the retry tests (the poison path drives all five attempts).

## Distinction

```text
scheduled retries        = 4  (MAX_RETRIES)
publish attempts performed = 5 (MAX_PUBLISH_ATTEMPTS)
```

## Tests

```text
test_retry_constants_are_exact_and_reach_every_backoff   (30/120/600/3600 then dead at attempts=5)
tests/test_step66c4_be2_reminder_expiry_outbox_relay.py::test_pg_relay_exhausts_to_dead_after_bounded_attempts  (attempts==5)
tests/test_step66c4_be1_r1_remediation.py::test_retry_plan_persists_backoff_then_dies  (updated threshold)
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
