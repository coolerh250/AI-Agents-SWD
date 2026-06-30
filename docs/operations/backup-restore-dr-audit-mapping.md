# Backup / Restore / DR Audit Mapping (Step 61)

Source: [`infra/dr/backup-restore-dr-audit-mapping.yaml`](../../infra/dr/backup-restore-dr-audit-mapping.yaml).
SDK: `shared/sdk/backup_restore_dr/audit.py`.

## Events
`backup_inventory_generated`, `cleanup_review_created`, `restore_plan_created`,
`restore_validation_completed`, `dr_readiness_evaluated`, `recovery_evidence_collected`,
`cleanup_execution_blocked`, `production_restore_blocked`, `production_failover_blocked`.

## Metadata
Always includes `actor`, `role`, `reason`, `operation_id`, `target`, `target_environment`,
`policy_decision`, and `production_restore=false` / `production_failover=false` /
`production_executed=false`. Never includes a token, secret, raw dump, kubeconfig, or
chain-of-thought.
