# Step 66C.4-BE1 — Migration and Compatibility Record

> **Planning/implementation record. The migration runs ONLY against isolated ephemeral test
> PostgreSQL. BE1 is not authorized for shared-runtime deployment.**

## Migration

```text
Number/name: 031_clarification_lifecycle_outbox_foundation.sql
Down script: 031_clarification_lifecycle_outbox_foundation_down.sql (matching *_down.sql per the
  repository's Stage 36 down-script convention)
Next legal sequence: 031 (latest pre-existing migration is 030). No existing migration is modified,
  reordered, or renumbered.
Shape: BEGIN; ... COMMIT; -- idempotent / re-runnable (ADD COLUMN IF NOT EXISTS, CREATE TABLE IF
  NOT EXISTS, CREATE INDEX IF NOT EXISTS, guarded ADD CONSTRAINT).
```

### Six lifecycle fields (additive, nullable)

```text
reminder_sent_at     TIMESTAMPTZ NULL
expired_at           TIMESTAMPTZ NULL
resume_eligible_at   TIMESTAMPTZ NULL
resume_requested_at  TIMESTAMPTZ NULL
resume_requested_by  TEXT        NULL  (actor identifier, same TEXT semantics as requested_by_id)
resume_authorized_at TIMESTAMPTZ NULL
```

Not added: a resume-dispatched timestamp, a resume-authorizer column, or an optimistic lock-version
column (canonical contract; dispatch/resumed evidence lives in the outbox + task status).

### Outbox table (exactly the canonical contract's columns)

```text
clarification_lifecycle_outbox(
  id UUID PK, clarification_id UUID FK, task_id UUID FK, event_type TEXT, idempotency_key TEXT,
  payload JSONB, status TEXT DEFAULT 'pending', attempts INT DEFAULT 0,
  created_at TIMESTAMPTZ, published_at TIMESTAMPTZ,
  UNIQUE(idempotency_key), CHECK status IN ('pending','published','dead'), CHECK attempts>=0,
  CHECK event_type/idempotency_key nonempty)
```

### Indexes / constraints

```text
idx_ocr_reminder_due  -- (status, reminder_at) WHERE status='open' AND reminder_sent_at IS NULL
idx_ocr_expiry_due    -- (status, due_at) WHERE status='open'
idx_clo_pending_created -- (created_at) WHERE status='pending'  (future relay pending-claim scan)
idx_clo_clarification_id
uq_clarification_lifecycle_outbox_idempotency_key
chk_ocr_resume_authorized_requires_eligible -- resume_authorized_at IS NULL OR resume_eligible_at
  IS NOT NULL (passes for all legacy rows, whose six columns are NULL)
```

### Lock / rewrite assessment

```text
ADD COLUMN with no default and no NOT NULL is a metadata-only change in PostgreSQL (no table
  rewrite, brief ACCESS EXCLUSIVE lock only). The CHECK constraint validates existing rows, but all
  six new columns are NULL for legacy rows so the predicate is trivially satisfied (no rewrite of
  data). CREATE INDEX is non-CONCURRENT here (acceptable for the tiny table in isolated test DB);
  BE2/deploy planning may switch to CREATE INDEX CONCURRENTLY for shared-runtime rollout. No
  destructive statement, no backfill, no default expression requiring a synchronous fill.
```

## Compatibility matrix (verified)

### Scenario A — Old code + migrated schema
```text
Expected: PASS. Reason: migration is additive and nullable; old code never selects the new columns,
  and the new columns default to NULL. Confirmed by test_pg_existing_rows_remain_intact_after_migration
  (row created before migration remains readable/unmutated after it).
```

### Scenario B — New BE1 code + migrated schema
```text
Expected: PASS. Confirmed by the deadline-CAS and outbox integration tests running against the
  migrated schema.
```

### Scenario C — Migration rollback
```text
Expected: rollback succeeds in isolated test DB and removes only BE1-added objects. Confirmed by
  test_pg_migration_creates_schema_and_rolls_back (down drops the six columns + outbox + indexes +
  constraint; pre-existing due_at/status columns survive).
```

### Scenario D — Existing data
```text
Expected: existing open/answered rows remain readable; no lifecycle value inferred or mutated.
  Confirmed: post-migration the pre-existing row's status/answered_at are unchanged and all six new
  columns are NULL.
```

### Scenario E — Deployment ordering (recorded, NOT executed)
```text
Migration 031 must precede any future code path that requires the new columns/table. BE1 is NOT
authorized for shared-runtime deployment; no deployment ordering was exercised. BE2's deploy stage
must apply 031 to the shared runtime (with CONCURRENTLY-index consideration) before enabling any
producer/relay, and is bound by the BE1 Runtime Compatibility Gate.
```

## Execution evidence

```text
Migration + all integration scenarios executed against an isolated EPHEMERAL Postgres 16 container
(throwaway, separate from the shared aiagents database), applying uuid-ossp + migrations 029 + 030
+ 031 to a fresh database, then 031_down. 15/15 BE1 tests passed. No shared test/staging/production
runtime was migrated.
```

## Statement

Migration/compatibility record. Migration runs only against isolated ephemeral test PostgreSQL. No
shared-runtime migration. No deployment. No scheduler/relay activation. No production/external action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
