# Non-production ArgoCD manual sync — result (Step 56)

The verified non-production manual sync result. Recorded (redacted) in the committed
summary [`infra/gitops/nonproduction-argocd-manual-sync-summary.yaml`](../../infra/gitops/nonproduction-argocd-manual-sync-summary.yaml);
the live runtime report (`.runtime/gitops/nonproduction-argocd-manual-sync-report.json`)
is **never committed**.

- Report generator: `scripts/run_nonproduction_argocd_manual_sync_report.py` → `NONPROD_ARGOCD_SYNC_REPORT_RUN`
- Verifier: `scripts/verify_nonproduction_argocd_manual_sync.py` → `NONPROD_ARGOCD_MANUAL_SYNC_VERIFY`

| Field | Value |
|-------|-------|
| Sync status | `Synced` |
| Health status | `Healthy` |
| Operation phase | `Succeeded` |
| Manual only | true (no auto-sync) |
| Prune / self-heal | false / false |
| Destination namespace | `aiagents-smoke-dev` |
| Synced kinds | ConfigMap, CronJob, Deployment, Job, NetworkPolicy, PersistentVolumeClaim, Service, ServiceAccount |
| Resource namespaces | `aiagents-smoke-dev` only |
| Production namespace touched | false |

The synced resources are the Step 55 scoped control-plane subset (orchestrator +
policy-engine + approval-engine + audit-service + postgres + redis); 6/6 pods Ready,
migration Job Complete. The Step 55 runtime smoke remains PASS against the
ArgoCD-managed resources.

The verifier reads the live report and PASSes only on a real `Synced` + `Healthy`,
manual-only, non-production sync. With no report it is **BLOCKED** (the sync has not
run) — never a faked PASS.
