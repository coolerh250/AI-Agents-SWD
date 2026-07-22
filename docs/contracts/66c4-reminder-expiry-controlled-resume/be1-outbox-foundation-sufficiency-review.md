# Step 66C.4-BE1-R — Outbox Foundation Sufficiency Independent Review

> **Independent review artifact. No implementation change. No migration change. No merge. No
> deployment.**

**Foundation verdict: FOUNDATION_REMEDIATION_REQUIRED_BEFORE_MERGE**

## Actual schema as created by migration 031 (read back from the isolated ephemeral Postgres 16.14)

```text
column             type                        null  default
id                 uuid                        NO    uuid_generate_v4()
clarification_id   uuid                        NO    -
task_id            uuid                        NO    -
event_type         text                        NO    -
idempotency_key    text                        NO    -
payload            jsonb                       NO    '{}'::jsonb
status             text                        NO    'pending'::text
attempts           integer                     NO    0
created_at         timestamptz                 NO    now()
published_at       timestamptz                 YES   -

CONSTRAINT clarification_lifecycle_outbox_pkey                  PRIMARY KEY (id)
CONSTRAINT uq_clarification_lifecycle_outbox_idempotency_key    UNIQUE (idempotency_key)
CONSTRAINT chk_clo_status                CHECK (status = ANY (ARRAY['pending','published','dead']))
CONSTRAINT chk_clo_attempts_nonnegative  CHECK (attempts >= 0)
CONSTRAINT chk_clo_event_type_nonempty   CHECK (length(btrim(event_type)) > 0)
CONSTRAINT chk_clo_idempotency_key_nonempty CHECK (length(btrim(idempotency_key)) > 0)
FOREIGN KEY (clarification_id) REFERENCES operator_clarification_requests(id)   -- NO ACTION
FOREIGN KEY (task_id)          REFERENCES operator_tasks(id)                    -- NO ACTION

INDEX idx_clo_pending_created   ON (created_at) WHERE status = 'pending'
INDEX idx_clo_clarification_id  ON (clarification_id)
```

This is column-for-column the table proposed in the canonical `data-model-contract.md`. BE1 did not
self-expand the contract, which was the correct stage discipline.

## Capability matrix

| # | Capability | Classification | Evidence / reasoning |
| --- | --- | --- | --- |
| 1 | Pending ordering (oldest-first) | `SUPPORTED_BY_CURRENT_SCHEMA` | `idx_clo_pending_created ON (created_at) WHERE status='pending'` matches the §11.3 failure-mode-6 drain order exactly. |
| 2 | Multiple concurrent relay workers | `SUPPORTED_WITHOUT_SCHEMA_CHANGE` | `SELECT ... WHERE status='pending' ORDER BY created_at FOR UPDATE SKIP LOCKED` needs no extra column. |
| 3 | Safe claim (no double-claim) | `SUPPORTED_WITHOUT_SCHEMA_CHANGE` | Row-lock + `SKIP LOCKED` within the relay transaction; the same row-lock serialisation independently verified for the answer CAS in this review. |
| 4 | Worker-crash recovery | `SUPPORTED_WITHOUT_SCHEMA_CHANGE` | If the relay claims inside a transaction, a crash rolls the claim back and the row returns to `pending`. No lease column is needed **provided** the relay never holds a claim across a process boundary. This constraint is not written down anywhere and must be stated in the contract before BE2. |
| 5 | Persisted retry schedule | `REQUIRES_SCHEMA_CHANGE` | There is no `available_at` / `next_attempt_at`. A failed attempt cannot record when it may next be tried; the row is immediately re-eligible on the very next relay pass. |
| 6 | Retry backoff | `REQUIRES_SCHEMA_CHANGE` | Same missing column. Backoff cannot be persisted; an in-memory backoff dies with the worker and is not shared between the multiple workers of capability 2. |
| 7 | Bounded retry | `SUPPORTED_WITHOUT_SCHEMA_CHANGE` | `attempts` + a code-level cap. **But see the conflict below** — bounded retry without backoff actively breaks binding failure mode 1. |
| 8 | Published terminal state | `SUPPORTED_BY_CURRENT_SCHEMA` | `status='published'` + `published_at`. |
| 9 | Dead / DLQ terminal state | `SUPPORTED_BY_CURRENT_SCHEMA` (state) / `REQUIRES_SCHEMA_CHANGE` (timestamp) | `status='dead'` exists and is CHECK-allowed. There is no `dead_at`, so the time of death is unrecoverable — DLQ age, alerting thresholds and reconciliation SLAs cannot be computed. `created_at` is the enqueue time, not the death time. |
| 10 | Bounded, safe error diagnosis | `REQUIRES_SCHEMA_CHANGE` | There is no `last_error`. §11.3 binding failure mode 7 requires a dead row to become "an explicit operator-reconciliation item"; with no persisted failure reason the operator receives an item with no diagnosis. |
| 11 | Stuck-event detection | `SUPPORTED_BY_CURRENT_SCHEMA` | `max(age(now(), created_at)) WHERE status='pending'` via the partial index. |
| 12 | Operator replay | `SUPPORTED_WITHOUT_SCHEMA_CHANGE` (mechanically) / `UNRESOLVED` (governance) | A `dead` row can be reset to `pending` by an UPDATE. There is no replay actor/timestamp field and no defined replay audit trail, and §11.3 failure mode 8 defers to "the existing DLQ replay tooling" without stating how an outbox row enters it. Must be resolved in the contract before BE2. |
| 13 | Reconciliation metrics | `SUPPORTED_BY_CURRENT_SCHEMA` | Counts and oldest-age grouped by `status` are derivable. Metrics about failure CAUSES are not (see 10). |
| 14 | Idempotency | `SUPPORTED_BY_CURRENT_SCHEMA` | `UNIQUE (idempotency_key)`, independently exercised: the duplicate insert raises `UniqueViolationError`. |
| 15 | Transaction atomicity | `SUPPORTED_BY_CURRENT_SCHEMA` | `insert_lifecycle_outbox_event` runs in the caller's transaction and never begins/commits/closes; independently verified — rollback leaves 0 rows, commit leaves exactly 1. |

## Explicit assessment of the columns named in the review scope

```text
available_at / next_attempt_at  -- MISSING. Required for capabilities 5 and 6.
published_at                    -- PRESENT.
dead_at                         -- MISSING. Required for the timestamped half of capability 9.
last_error                      -- MISSING. Required for capability 10.
claim owner (locked_by)         -- MISSING, but NOT required if the relay uses transaction-scoped
                                   FOR UPDATE SKIP LOCKED. Required only if a lease outlives a txn.
claim / lease expiry            -- MISSING, same conditional as above.
```

## The blocking conflict

Binding failure mode 1 in `api-and-event-contract.md` §11.3 states: *"DB commit succeeds but publisher
unavailable: the outbox row is durably 'pending'; the relay publishes it when the publisher recovers.
No loss."* Binding failure mode 7 states that a row failing bounded retries is marked `dead`.

With no persisted next-attempt time, these two binding requirements cannot both hold. A relay polling
every few seconds with a bounded `attempts` cap will exhaust the cap within seconds of a publisher
outage and mark healthy, non-poison rows `dead` — the exact "loss" that failure mode 1 forbids. The
only way to satisfy both is a persisted backoff schedule, i.e. an `available_at` column. This is a
schema gap, not an implementation choice available to BE2.

## Why this returns BE1-R1 rather than deferring to BE2

BE2 cannot build the relay described by the binding contract without adding durability columns. Doing
so inside BE2 would mean adding schema that the canonical contract does not define — the exact
"self-expansion" prohibition that BE1 correctly honoured. The gap must be closed by amending the
canonical `data-model-contract.md` §outbox and extending migration 031 (or adding a paired 032) under
a scoped BE1-R1, before the foundation is merged as "sufficient".

The BE1 implementer flagged `available_at`, `dead_at` and `last_error` honestly and accurately in
`be1-disabled-outbox-foundation-record.md` as a forward contract-refinement item. This review agrees
with the finding and disagrees only with its classification as non-blocking: because the missing
columns are what make the *binding* §11.3 failure modes implementable, they are a merge-blocking
foundation gap rather than a BE2 concern.

## Statement

Independent review artifact only. No implementation change. No migration change. No relay built. No
relay activated. No scheduler. No deployment. No merge.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
