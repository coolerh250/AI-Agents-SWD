# Backup Artifact Classification (Step 61)

Source: [`infra/dr/backup-artifact-classification.yaml`](../../infra/dr/backup-artifact-classification.yaml).

Classifies every backup / runtime artifact with retention + cleanup handling. Per-class
fields: `retention_days`, `cleanup_allowed`, `cleanup_requires_approval`, `backup_required`,
`restore_validation_required`, `commit_allowed`, `secret_scan_required`.

## Key invariants
- `database_dump` / `redis_snapshot`: `commit_allowed: false` (never committed).
- `temporary_trace` / `temporary_build_cache`: `cleanup_allowed: true`, no approval.
- `scheduled_dr_report`: `cleanup_allowed: false` unless a retained copy exists.
- `cluster_runtime_state`: `cleanup_allowed: false` (kind / ArgoCD never auto-cleaned).
- Runtime evidence cleanup depends on freshness + current verifier needs (requires approval).
