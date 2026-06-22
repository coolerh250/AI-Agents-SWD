# Runtime Baseline Visibility (Step 51.4 / Stage 53G)

Read-only visibility over the validated Step 51 static baseline. **No cluster
connected, no deploy, no Helm install, no ArgoCD sync.** This surface NEVER
applies a manifest, runs a verifier, or triggers a sync.

## Aggregation model

`shared/sdk/runtime_baseline` aggregates the **committed** Step 51 baseline
(inventories, catalogs, chart values, GitOps manifests) into a redacted summary
([infra/kubernetes/runtime-baseline-summary.yaml](../../infra/kubernetes/runtime-baseline-summary.yaml),
anti-drift tested). Status enum: `validated_not_deployed` /
`passed_with_non_production_limitations` / `failed` / `unknown` — never
`production_ready`.

## Read-only operations API (GET-only)

```
GET /operations/runtime/kubernetes/baseline      GET /operations/runtime/helm/status
GET /operations/runtime/kubernetes/components     GET /operations/runtime/gitops/status
GET /operations/runtime/kubernetes/security       GET /operations/runtime/argocd/status
GET /operations/runtime/kubernetes/network        GET /operations/runtime/environments
GET /operations/runtime/kubernetes/storage        GET /operations/runtime/readiness
GET /operations/runtime/kubernetes/batch-jobs     GET /operations/runtime/report
```

There is **no** POST/PUT/PATCH/DELETE, and no deploy/sync/apply/install endpoint.
Inputs are never user-provided paths/commands; the API reads only the committed
summary (`unknown` when absent — never a fake PASS). Responses carry
statuses/counts/names only.

## /operations/safety fields

The safety endpoint gains read-only Kubernetes/Helm/GitOps fields
(`kubernetes_runtime_baseline_status`, `kubernetes_cluster_connected=false`,
`helm_*_status`, `kubernetes_*_status`, `gitops_*_status`,
`argocd_auto_sync_enabled=false`, `runtime_production_ready=false`,
`runtime_validated_not_deployed=true`, …). See
[runtime safety fields verifier](../operations/runtime-baseline-verification.md).

## Admin Console

A read-only **Runtime Baseline** view (static fallback + React) shows the
baseline status, per-area status, environments, safety facts, a production
caveat, and the non-production limitations — with **no** deploy/sync/apply/install
control, no cluster-credential/kubeconfig/token input, and no secret display.

Verify: `python scripts/verify_runtime_operations_visibility.py`
(`RUNTIME_OPERATIONS_VISIBILITY_VERIFY: PASS`).
