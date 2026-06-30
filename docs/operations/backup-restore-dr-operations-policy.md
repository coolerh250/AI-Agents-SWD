# Backup / Restore / DR Operations Policy (Step 61)

Source of truth: [`infra/dr/backup-restore-dr-operations-policy.yaml`](../../infra/dr/backup-restore-dr-operations-policy.yaml).

A controlled, **non-production** backup / restore / disaster-recovery governance boundary.
It governs backup inventory, retention / cleanup, restore planning, non-production restore
validation, DR operation modelling and recovery evidence. It does **not** perform a
production restore, a production failover, a production data mutation, a cleanup execution,
a restore execution, a kind / ArgoCD teardown, or an external / cloud upload.

## Permanently blocked
- Production restore, production failover, production backup mutation
- External backup upload, cloud provider write
- ArgoCD production sync, Kubernetes production mutation
- Cleanup execution, restore execution, kind teardown, ArgoCD teardown
- `productionReady` is always `false`

## Required guards
- `requireInventoryBeforeCleanup: true` — no cleanup review without an inventory
- `requireRestoreValidation: true`
- `requireHumanApprovalForProductionRestore: true` (a future production phase only)

## Environments
Allowed: `local`, `dev`, `test`, `nonprod`. Forbidden: `production`, `prod`.

DR readiness visibility is **not** production DR ready. Claude Code does not decide
production readiness.
