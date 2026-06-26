# Non-production ArgoCD manual sync — plan (Step 56)

Real, guard-railed ArgoCD **manual** sync on the local kind cluster from Step 55.
**Not** production GitOps / auto-sync / production-readiness.

- Plan: [`infra/gitops/nonproduction-argocd-manual-sync-plan.yaml`](../../infra/gitops/nonproduction-argocd-manual-sync-plan.yaml)
- Runner: [`scripts/run_nonproduction_argocd_manual_sync.sh`](../../scripts/run_nonproduction_argocd_manual_sync.sh)
- Combined verifier: `scripts/verify_nonproduction_argocd_manual_sync_baseline.sh`
  → `NONPRODUCTION_ARGOCD_MANUAL_SYNC_BASELINE_VERIFY`

| Property | Value |
|----------|-------|
| Cluster | local kind (`kind-aiagents-smoke`) |
| ArgoCD namespace | `argocd-nonprod` |
| Destination namespace | `aiagents-smoke-dev` |
| Project | `aiagents-nonprod` (restricted) |
| Application | `aiagents-smoke` |
| Source | public repo, `infra/kubernetes/charts/ai-agents-platform`, `values-nonprod-smoke-local.yaml` |
| Sync policy | **manual only** (no auto-sync / prune / self-heal) |

## Ordered steps

1. Preflight — safe context + namespace + Step 55 runtime smoke still PASS.
2. Install / verify non-production ArgoCD (`argocd-nonprod`, ClusterIP only).
3. Apply the restricted AppProject.
4. Apply the non-production Application (manual sync).
5. Confirm `spec.syncPolicy.automated` is absent (manual-only).
6. Trigger **one** manual sync (`kubectl patch` of the Application `.operation`).
7. Wait for sync status (`Synced`) + health status (`Healthy`).
8. Collect the redacted sync report (`.runtime/gitops/`, never committed).
9. Confirm no production namespace touched / no auto-sync / no prune / no self-heal.

```bash
# from the repo root on the test host
scripts/run_nonproduction_argocd_manual_sync.sh
scripts/verify_nonproduction_argocd_manual_sync_baseline.sh
```

## Forbidden (enforced by the runner + verifiers)

Production cluster / namespace / `default` / `kube-system` / existing production
ArgoCD; auto-sync / prune / self-heal; production AppProject / Application; wildcard
destination; cluster-wide unrestricted resources; public ingress; LoadBalancer;
external ArgoCD exposure; GitHub write; image push; registry login; production
secret. `production_executed_true_count` stays `0`. **Claude Code does not decide
production readiness.**
