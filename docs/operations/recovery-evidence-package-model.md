# Recovery Evidence Package Model (Step 61)

Source: [`infra/dr/recovery-evidence-package-model.yaml`](../../infra/dr/recovery-evidence-package-model.yaml).
SDK: `shared/sdk/backup_restore_dr/evidence.py`.

A redacted recovery evidence package referencing existing platform evidence:
`backup_inventory`, `backup_target_classification`, `cleanup_review`, `restore_plan`,
`restore_validation_result`, `audit_event_refs`, `known_limitations`, `operator_decisions`,
`production_blocking_status`.

## Invariants
- No secret, raw DB dump, raw Redis dump, kubeconfig, token, or chain-of-thought
  (forbidden keys are redacted to `[redacted]`).
- `production_ready` / `production_restore_ready` always false.
- Missing required evidence is reported and blocks DR readiness.
- `production_blocking_status` explicitly records production restore + failover blocked.
