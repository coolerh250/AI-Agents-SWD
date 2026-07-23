# Step 66C.4-BE1-R1-R — B-2 Outbox Durability Closure Review

> Independent closure review of blocking finding **B-2** (outbox durability foundation
> insufficient for BE2). Judged from migration 031 at `0bb9944`, the repository model, and the
> reviewer's own constraint probes on an isolated ephemeral test PostgreSQL 16.

## Finding under review

B-2 (BLOCKING, from `f5417f4`): the outbox lacked a persisted next-attempt time, a terminal death
timestamp, and a bounded failure reason. Without a PERSISTED backoff, binding failure mode 1 ("no
loss during a publisher outage") and failure mode 7 ("bounded retries end in dead") are mutually
unsatisfiable — a bounded-attempt relay burns its cap within seconds of an outage and dead-letters
healthy rows.

## Final outbox schema (migration 031, remediated)

`clarification_lifecycle_outbox` columns: `id`, `clarification_id` (FK), `task_id` (FK),
`event_type`, `idempotency_key`, `payload` (JSONB), `status`, `attempts`, `created_at`,
**`available_at` (TIMESTAMPTZ NOT NULL DEFAULT statement_timestamp())**, `published_at`,
**`dead_at`**, **`last_error`**. The three bold columns are the R1 additions. All seven durability
fields the review demanded are present with clear semantics: `available_at`, `dead_at`, `last_error`,
`published_at`, `attempts`, `status`, `idempotency_key`.

## 7.1 Constraint review (reviewer's own probes)

Constraints in the migration: `chk_clo_status IN ('pending','published','dead')`,
`chk_clo_attempts_nonnegative (attempts >= 0)`, `chk_clo_event_type_nonempty`,
`chk_clo_idempotency_key_nonempty`, `chk_clo_last_error_bounded (length <= 500)`,
`uq_...idempotency_key UNIQUE`, and the coherence constraint `chk_clo_status_timestamps`:

```text
pending    => published_at IS NULL     AND dead_at IS NULL
published  => published_at IS NOT NULL AND dead_at IS NULL
dead       => dead_at IS NOT NULL      AND published_at IS NULL
```

Indexes: `idx_clo_pending_available (available_at, created_at) WHERE status='pending'` supports the
future relay's oldest-first claim honoring the persisted backoff; `idx_clo_pending_created`,
`idx_clo_dead_at WHERE status='dead'` (DLQ age/reconciliation), `idx_clo_clarification_id`.

Reviewer inserted contradictory rows directly on isolated PostgreSQL and confirmed each is rejected:

```text
pending + published_at set   => CheckViolationError
published + no published_at  => CheckViolationError
dead + published_at set      => CheckViolationError
attempts = -1                => CheckViolationError
status = 'weird'             => CheckViolationError
event_type = '  '            => CheckViolationError
last_error length 501        => CheckViolationError
duplicate idempotency_key    => UniqueViolationError
valid pending row            => available_at NOT NULL (defaulted), attempts=0
```

No contradictory status/timestamp combination is representable; `last_error` is DB-bounded;
`attempts >= 0`; idempotency uniqueness holds; the pending+available_at claim index exists.

## 7.2 Capability matrix

Each classified SUPPORTED_BY_CURRENT_SCHEMA / SUPPORTED_WITHOUT_SCHEMA_CHANGE /
REQUIRES_SCHEMA_CHANGE / UNRESOLVED:

| # | Capability | Classification | Basis |
|---|------------|----------------|-------|
| 1 | pending ordering | SUPPORTED_BY_CURRENT_SCHEMA | `idx_clo_pending_available (available_at, created_at)` |
| 2 | available-at scheduling | SUPPORTED_BY_CURRENT_SCHEMA | `available_at` NOT NULL + index |
| 3 | persisted retry backoff | SUPPORTED_BY_CURRENT_SCHEMA | `available_at` pushed forward; `RETRY_BACKOFF_SECONDS` model |
| 4 | bounded retry | SUPPORTED_BY_CURRENT_SCHEMA | `attempts` column + `MAX_DELIVERY_ATTEMPTS` |
| 5 | published terminal evidence | SUPPORTED_BY_CURRENT_SCHEMA | `published_at` + status coherence constraint |
| 6 | dead terminal evidence | SUPPORTED_BY_CURRENT_SCHEMA | `dead_at` + status coherence constraint |
| 7 | bounded safe failure diagnosis | SUPPORTED_BY_CURRENT_SCHEMA | `last_error` bounded (DB CHECK 500) |
| 8 | restart recovery | SUPPORTED_BY_CURRENT_SCHEMA | pending rows persist; `available_at` drives re-claim |
| 9 | crash recovery w/ future SKIP LOCKED claim | SUPPORTED_BY_CURRENT_SCHEMA | `status='pending' AND available_at<=statement_timestamp()` + index; SKIP LOCKED is a query clause, no schema change |
| 10 | stuck-event detection | SUPPORTED_BY_CURRENT_SCHEMA | `created_at`/`available_at`/`status` queryable |
| 11 | operator replay | SUPPORTED_BY_CURRENT_SCHEMA | `dead_at`/`last_error`/`status` mutable; `plan_replay_state` maps dead→pending |
| 12 | reconciliation metrics | SUPPORTED_BY_CURRENT_SCHEMA | status counts; `idx_clo_dead_at` for DLQ age |
| 13 | idempotency | SUPPORTED_BY_CURRENT_SCHEMA | `UNIQUE(idempotency_key)` |
| 14 | atomic state+outbox transaction | SUPPORTED_BY_CURRENT_SCHEMA | insert runs in caller's connection/transaction |

All 14 are SUPPORTED_BY_CURRENT_SCHEMA. **BE2 need NOT modify the BE1 foundation schema** to
implement relay / retry / DLQ / replay. No new foundation column is required.

## 7.3 Retry helper boundary

`plan_retry_state` (and `plan_replay_state`) in `lifecycle_outbox.py` are pure functions: given
`attempts` and an optional bounded `error` they return the next persisted state as a dict. Source
inspection of the function region shows no `await`, no `asyncpg`, no `conn.`, no `while`, no
`Thread`, no `asyncio` — no DB/network I/O, no loop, no worker, no startup registration. There is no
live caller (only isolated tests import the module). `insert_lifecycle_outbox_event` is
transaction-aware: it takes the caller's `asyncpg.Connection`, never opens/commits/closes, so a
lifecycle state mutation and its outbox insert commit atomically under the caller's boundary. No
relay semantics are activated.

## Verdict

**B-2: CLOSED.** The schema carries `available_at` (persisted backoff), `dead_at` (terminal death),
and bounded `last_error`; coherence and bound constraints are enforced at the DB; all 14 BE2
capabilities are supported without a foundation schema change; the retry helper is a pure model with
no live producer or relay.

_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
