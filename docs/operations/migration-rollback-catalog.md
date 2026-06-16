# Migration Rollback Catalog (Stage 51)

## Classification method

`shared/sdk/backup_dr/migration_catalog.py` scans `migrations/*.sql` and
classifies every non-`*_down.sql` migration deterministically:

1. A migration with a matching `*_down.sql` → **reversible** (low risk).
2. A migration whose body contains a destructive change
   (`DROP TABLE` / `DROP COLUMN` / `TRUNCATE` / `DELETE FROM` / `DROP TYPE` /
   `ALTER TABLE ... DROP` / `DROP CONSTRAINT`) with no down script →
   **manual_rollback_required** (high risk) with explicit rollback notes.
3. Any other (purely additive: `CREATE ... IF NOT EXISTS`, `ALTER ... ADD`,
   `INSERT ... ON CONFLICT`) → **forward_only** (low risk) with a note on how to
   roll back by dropping the created objects.

## reversible / forward-only / manual rollback

| Reversibility              | Meaning                                            |
| -------------------------- | -------------------------------------------------- |
| `reversible`               | matching down script present; apply it to roll back |
| `forward_only`             | additive-only; roll back by dropping created objects |
| `manual_rollback_required` | destructive; manual schema + data restoration needed |
| `unknown`                  | **not permitted** — the catalog must be complete    |

## unknown_count = 0 requirement

`migration_down_gap_closed` is true when the catalog is **complete**: zero
`unknown` entries **and** every `forward_only` / `manual_rollback_required`
migration carries rollback notes. It does **not** require every migration to be
reversible.

```bash
./scripts/verify_migration_rollback_catalog.sh   # MIGRATION_ROLLBACK_CATALOG_VERIFY: PASS
```

Read-only view: `GET /operations/backup-dr/migration-rollback-catalog`
(`unknown_count`, `complete`, per-migration classification).

## Risk notes

Destructive migrations are marked `high` risk with a note that rollback requires
manual restoration from the latest verified backup; additive and reversible
migrations are `low` risk. The catalog never fabricates a down script.
