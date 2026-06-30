# Restore Plan Model (Step 61)

Source: [`infra/dr/restore-plan-model.yaml`](../../infra/dr/restore-plan-model.yaml).
SDK: `shared/sdk/backup_restore_dr/restore_plan.py`.

A restore plan describes an intended **non-production** restore validation. It never
executes a restore (`restore_executed` / `production_restore` always false).

## Restore types
`validate_backup`, `restore_nonproduction_copy`, `dry_run_restore`, `schema_validation`,
`integrity_validation`.

## Forbidden (blocked)
`restore_production`, `overwrite_production`, `failover_production`, `restore_customer_data`,
and any `production` / `prod` target environment.

Validation + a rollback plan are always required. `restore_nonproduction_copy` additionally
requires human approval (still not a production restore).
