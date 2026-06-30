# Controlled Cleanup Review Model (Step 61)

Source: [`infra/dr/controlled-cleanup-review-model.yaml`](../../infra/dr/controlled-cleanup-review-model.yaml).
SDK: `shared/sdk/backup_restore_dr/cleanup_review.py`.

A cleanup review is a **review**, never an execution (`cleanup_executed` is always false).

## Rules
- Only paths under allowlisted runtime roots (`.runtime/…`) are eligible; arbitrary /
  traversal / absolute paths are rejected.
- `temporary_trace` / `temporary_build_cache` → allowed.
- `runtime_evidence` / `scheduled_dr_report` / `regression_report` / `orphan_volume` →
  requires operator approval.
- `database_dump` / `redis_snapshot` / `audit_export` / `security_summary` /
  `release_evidence` / `cluster_runtime_state` → blocked.
- Scopes `kind_cluster` / `argocd` / `active_database` / `active_redis` /
  `active_runtime_state` → the whole review is blocked.
- A disk-pressure signal only **recommends** an operator action; it never auto-executes.
