# Step 66C.4-BE2-R — Observability & Security Review

> **Independent review. Reviewer did not implement the code. Evidence gathered on an isolated
> ephemeral PostgreSQL 16 + Redis 7 stack on the internal test runtime. Nothing deployed.**

Reviewed commit: `319123b`.

## 13. Metrics & health — PASS (with one observability gap tied to §6.3)

`shared/sdk/tasks/lifecycle_metrics.py` declares poller and relay collectors, and I traced each to a
real code path:

- Poller: `POLL_CYCLES_TOTAL`, `POLL_CYCLE_FAILURES_TOTAL`, `REMINDER_CLAIMS_TOTAL`,
  `EXPIRY_CLAIMS_TOTAL`, `RECONCILIATION_FAILURES_TOTAL`, `POLL_DURATION_SECONDS`,
  `LAST_SUCCESSFUL_POLL_TIMESTAMP` — all incremented/observed in `_run_cycle`/`_claim_one_*`.
  (`DUPLICATE_SUPPRESSED_TOTAL` is declared but not incremented in the current claim path — minor;
  the claim guard filters duplicates in SQL rather than counting them.)
- Relay: `OUTBOX_PUBLISH_SUCCESS_TOTAL`, `OUTBOX_PUBLISH_FAILURE_TOTAL`,
  `OUTBOX_RETRY_SCHEDULED_TOTAL`, `OUTBOX_DEAD_TOTAL`, `OUTBOX_REPLAY_TOTAL`, `OUTBOX_PENDING_COUNT`,
  `OUTBOX_OLDEST_PENDING_AGE_SECONDS`, `LAST_SUCCESSFUL_PUBLISH_TIMESTAMP`,
  `RELAY_CYCLE_FAILURES_TOTAL` — all updated on the matching outcome.

Checks:

- Success counters do NOT increment on rollback: `published_count` / `OUTBOX_PUBLISH_SUCCESS_TOTAL`
  fire only inside the `result.ok` branch that also writes `published`; a transaction that rolls back
  (e.g. injected commit failure) increments nothing. Verified.
- `OUTBOX_PENDING_COUNT` / `OUTBOX_OLDEST_PENDING_AGE_SECONDS` come from a real DB query
  (`_sample_backlog`), not a guess.
- Health/status: the two entrypoints expose `/health` and `/status`. `/status` returns service name,
  running flag, poll interval, batch size, and counters — **no DSN, no Redis URL, no connection
  string**. Verified by reading `status()`.
- Label cardinality is bounded: `poller ∈ {reminder, expiry}`, `event_type ∈ {reminder_recorded,
  expired}`.
- Logs carry ids and bounded reasons only (see below); no full event dump.

**Observability gap (ties to §6.3, BLOCKING elsewhere):** there is NO metric or log for a
clarification/task mismatch during expiry (a 0-row task update). `RECONCILIATION_FAILURES_TOTAL`
fires only on an outbox idempotency collision. Health cannot distinguish "expired a clarification
whose task diverged" from a clean expiry. This is why the §6.3 partial-consistency outcome is silent.

Health can otherwise distinguish process-alive (`/health`), and the timestamp gauges expose staleness
(last successful poll/publish) and backlog (pending count / oldest age / dead count) for a scraper to
alert on DB-unavailable / Redis-unavailable / stale-worker / backlog / dead-threshold.

## 16. Security & privacy — no critical/high; one MEDIUM tied to a future producer

| # | Severity | Finding |
|---|----------|---------|
| S-1 | Informational | `last_error` is the exception CLASS name only, bounded to 500 chars (`type(exc).__name__[:MAX_LAST_ERROR_CHARS]`); a message containing `dsn=...`/`token=...` is reduced to `ValueError`. Verified by test and by reading `_bounded_error`. No secret/DSN/payload leak. |
| S-2 | Informational | The relay envelope carries only ids, the `idempotency_key`, a bounded result label, and a fixed summary — never raw clarification question/answer content. The BE1 positive allowlist (`assert_safe_outbox_payload`) blocks a raw body / nested payload from reaching the outbox row, and the relay does not add unbounded fields. No raw content reaches Redis. |
| S-3 | Informational | All SQL is parameterized (asyncpg `$n`); the backoff interval uses `($3 || ' seconds')::interval` with `$3` bound to a computed integer string — no interpolation of untrusted input. No injection. |
| S-4 | Informational | `/health` and `/status` do not leak connection details (see §13). |
| S-5 | Low | Metrics label cardinality bounded (see §13). |
| S-6 | **Medium** | `replay_dead` has **no authorization boundary** — it is a bare method that moves a `dead` row back to `pending`. This is acceptable ONLY because it is not exposed (no API route, no console control, no live caller). It is directly tied to a FUTURE live producer: when BE3 (or later) wires an operator replay control, an RBAC/authorization gate MUST be added at that boundary. Flagged openly (NOT hidden under a PASS) per §16. |

No critical or high severity issue. S-6 (medium) is recorded in the open, tied to the future
activation, and is not masked.

---

_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
