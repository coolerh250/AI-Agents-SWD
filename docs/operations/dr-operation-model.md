# DR Operation Model (Step 61)

Source: [`infra/dr/dr-operation-model.yaml`](../../infra/dr/dr-operation-model.yaml).
SDK: `shared/sdk/backup_restore_dr/dr_operation.py`.

A DR operation records governance state only. Operation types: `backup_inventory`,
`backup_validation`, `restore_plan_created`, `restore_validation`, `cleanup_review`,
`dr_readiness_assessment`.

Forbidden (blocked): `production_failover`, `production_restore`, `cross_region_failover`,
`production_data_overwrite`.

## DR readiness
Governance judgement only. `production_ready` / `production_restore_ready` are always false.
Missing required evidence (`backup_inventory`, `backup_target_classification`,
`restore_plan`, `restore_validation_result`) blocks readiness. A production target →
`blocked_by_policy`. DR readiness is **not** production DR ready.
