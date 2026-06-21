# ArgoCD & Environment GitOps Baseline (Step 51.3 / Stage 53F)

GitOps **manifests + static validation only**. Validated, **not applied**: no
cluster connection, no `argocd` CLI, no `argocd app sync`, no `kubectl`, no Helm
install. **No ArgoCD is installed.** This stage declares NO production readiness.

## What this stage adds

* An ArgoCD `AppProject` ([infra/gitops/argocd/project.yaml](../../infra/gitops/argocd/project.yaml))
  that restricts source repo, destinations, and resource kinds.
* Four `Application` manifests — dev, test, staging-placeholder,
  production-placeholder — each pinned to a Helm values file.
* A non-production app-of-apps that references **dev + test only**.
* An environment catalog ([gitops-environments.yaml](../../infra/gitops/gitops-environments.yaml))
  and three machine-readable policy summaries.

## Safety model

| Property | Baseline |
| --- | --- |
| Auto-sync | **disabled** (no `syncPolicy.automated` anywhere) |
| Prune / selfHeal / allowEmpty | none |
| CreateNamespace | false |
| Finalizers / hooks / image-updater / notifications | none |
| Source repo | exactly this repo (no wildcard, no credential URL) |
| Destinations | placeholders only (`kubernetes.default.svc` marked placeholder; `*.invalid`) |
| Cluster-scoped resources | denied (empty `clusterResourceWhitelist`) |
| Secret resource | denied (blacklisted) |
| Production | disabled placeholder, excluded from app-of-apps |

## Verify (no cluster)

```bash
python scripts/verify_argocd_manifests.py             # ARGOCD_MANIFESTS_VERIFY: PASS
python scripts/verify_gitops_environment_mapping.py   # GITOPS_ENVIRONMENT_MAPPING_VERIFY: PASS
python scripts/verify_gitops_production_isolation.py   # GITOPS_PRODUCTION_ISOLATION_VERIFY: PASS
./scripts/verify_gitops_argocd_baseline.sh            # GITOPS_ARGOCD_BASELINE_VERIFY: PASS
```

See also: [environment model](gitops-environment-model.md),
[production isolation](argocd-production-isolation.md),
[sync safety](argocd-sync-safety.md).

## Remaining limitations

A real GitOps rollout needs a real ArgoCD install, real destination clusters,
repo credentials, production OIDC, a production secret store, image-digest
pinning, a backup target, operator sync approval, and a runtime cluster smoke —
**none** of which exist here.
