# Step 66C.4-BE1-R — Migration Independent Review

> **Independent review artifact. All migration runs were performed by the reviewer against an
> isolated ephemeral test PostgreSQL 16 created for this review and destroyed afterwards. No shared
> test, staging or production database was migrated. No implementation or migration file was changed.**

**Migration verdict: PASS**

## Environment

```text
PostgreSQL 16.14 (Debian 16.14-1.pgdg13+1) on x86_64-pc-linux-gnu
Isolated ephemeral test PostgreSQL container, created for this review only, torn down at the end.
Baseline applied: migrations 029 -> 030, then 031 (up), 031 (reapply), 031_down, 031 (up) again.
```

## Six lifecycle fields

Independently read back from `information_schema.columns` after applying 031:

```text
reminder_sent_at      TIMESTAMPTZ  is_nullable=YES  default=NULL
expired_at            TIMESTAMPTZ  is_nullable=YES  default=NULL
resume_eligible_at    TIMESTAMPTZ  is_nullable=YES  default=NULL
resume_requested_at   TIMESTAMPTZ  is_nullable=YES  default=NULL
resume_requested_by   TEXT         is_nullable=YES  default=NULL
resume_authorized_at  TIMESTAMPTZ  is_nullable=YES  default=NULL

Absent, as the canonical contract requires: resume_dispatched_at, resume_authorized_by,
  policy_decision_id, resume_dispatch_event_id, lock_version, reminder_due_at, expires_at,
  reminder_count, answered_by.
CONSTRAINT chk_ocr_resume_authorized_requires_eligible
  CHECK (resume_authorized_at IS NULL OR resume_eligible_at IS NOT NULL)
INDEX idx_ocr_reminder_due ON (status, reminder_at) WHERE status='open' AND reminder_sent_at IS NULL
INDEX idx_ocr_expiry_due   ON (status, due_at)      WHERE status='open'
```

Exactly six columns, all nullable with no default, matching `data-model-contract.md` line for line.
The ordering CHECK is written so that a legacy row (all six NULL) evaluates to TRUE and is never
rejected — independently confirmed by migrating a table that already contained seeded rows.

## Outbox schema

See `be1-outbox-foundation-sufficiency-review.md` for the full read-back and the capability matrix.
Structurally the table, its two indexes, its UNIQUE constraint and its four CHECK constraints are
created correctly and idempotently. The *sufficiency* concern recorded there is a contract/schema
completeness finding, not a migration-safety finding.

## Up / down / reapply

```text
031 up          -> 0.015 s   (six ADD COLUMN + 1 CHECK + 3 indexes + 1 CREATE TABLE)
031 reapply     -> 0.003 s   no error, no duplicate object (IF NOT EXISTS throughout, and the CHECK
                             is guarded by a pg_constraint existence probe in a DO block)
031_down        -> succeeds; all six columns gone, outbox table gone (to_regclass NULL),
                   idx_ocr_reminder_due / idx_ocr_expiry_due gone,
                   chk_ocr_resume_authorized_requires_eligible gone
031 up (again)  -> succeeds; schema is byte-identical to the first application (deterministic)
031_down twice  -> succeeds (IF EXISTS throughout)
```

Only BE1-added objects are removed by the down script. Independently checked after rollback: `due_at`,
`reminder_at`, `status`, `answered_at`, `answer_message_id`, `question`, and every other pre-existing
column survive; `operator_tasks` and `task_messages` are untouched; the pre-existing indexes
`idx_operator_clarification_requests_task_id` / `_status` survive.

Both scripts are wrapped in a single `BEGIN; ... COMMIT;` block, so a partial application cannot be
left behind.

## Existing rows

Representative rows were seeded BEFORE 031 was applied (an `open` clarification and, in a second run,
an `answered` one), then 031 was applied on top:

```text
status        unchanged   ('open' / 'answered')
answered_at   unchanged
due_at        unchanged
reminder_at   unchanged
new columns   all NULL, as designed ("absence of a value IS the state")
```

No backfill, no `UPDATE`, no `DELETE`, no `ALTER COLUMN` appears anywhere in the up script. Old data
is bit-for-bit preserved.

## Lock and rewrite behaviour

```text
relfilenode of operator_clarification_requests before 031 : 16461
relfilenode after a full down + up cycle                  : 16461
=> NO TABLE REWRITE.
```

`ALTER TABLE ... ADD COLUMN <nullable, no default>` is a catalog-only operation on PostgreSQL 11+; it
takes an `ACCESS EXCLUSIVE` lock for the duration of the catalog update only (measured at 15 ms for
all six columns plus every other object on a populated table). `CREATE INDEX` (non-concurrent) also
takes a build lock on `operator_clarification_requests`; on a table of this expected size (hour-scale
human clarifications) this is negligible, but it is worth recording that the two partial indexes are
NOT built `CONCURRENTLY`, so on a large table the migration would block writes for the index build.
This is informational only — BE1 is not authorized to migrate any shared runtime.

Observation (informational, no action required): each down+up cycle leaves dropped-attribute
tombstones in `pg_attribute` (12 observed after two full cycles). PostgreSQL never reclaims dropped
column slots against the 1600-column budget without a table rewrite. Irrelevant for one or two
rollbacks; worth knowing before scripting repeated rollback loops against a long-lived database.

## Compatibility matrix

```text
old code + un-migrated schema : baseline, unaffected.
old code + migrated schema    : SAFE. Every added column is nullable with no default; the pre-BE1
  `SELECT *` mappers ignore unknown keys, and the pre-BE1 answer CAS (`WHERE id=$1 AND status='open'`)
  still matches. Nothing old reads or writes the new columns or the new table.
new code + un-migrated schema : BREAKS, expected and acceptable. The BE1 CAS references `due_at`
  (pre-existing, fine) but `_clar_row` and the outbox module reference the new columns/table; the
  outbox insert would fail with UndefinedTableError. The ordering is migration-then-code, which is
  the normal forward-only order for an additive migration. Recorded here as an explicit deploy
  ordering constraint for whoever eventually deploys this (not BE1, not this review).
new code + migrated schema    : verified working — 15/15 BE1 tests and 229 regression tests pass
  against the migrated isolated ephemeral database.
```

## Findings

```text
No migration-safety defect found. The migration is additive, idempotent, non-rewriting, reversible,
deterministic on reapply, and preserves all pre-existing data and objects.
Informational: indexes are not created CONCURRENTLY; dropped-column tombstones accumulate across
  repeated rollback cycles; new-code-before-migration is an ordering hazard to record for deployment.
```

## Statement

Independent review artifact only. No migration file changed. No shared test, staging or production
database migrated. Isolated ephemeral test PostgreSQL only, destroyed after the review. No deployment.
No merge.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
