# infra/gitops — ArgoCD & Environment GitOps Baseline (Step 51.3)

GitOps **manifests + static validation only**. These manifests are **validated,
not applied**: no cluster connection, no `argocd` CLI, no `argocd app sync`, no
`kubectl`, no Helm install. **No ArgoCD is installed.**

## Contents

| Path | Purpose |
| --- | --- |
| `gitops-environments.yaml` | Environment → values file → Application mapping (catalog) |
| `argocd/project.yaml` | `AppProject` — restricted source/destinations/resources |
| `argocd/applications/dev.yaml` | Dev Application (active in catalog, **no auto-sync**) |
| `argocd/applications/test.yaml` | Test Application (active in catalog, **no auto-sync**) |
| `argocd/applications/staging-placeholder.yaml` | Staging placeholder (**inactive**) |
| `argocd/applications/production-placeholder.yaml` | Production placeholder (**disabled**) |
| `argocd/app-of-apps/non-production.yaml` | app-of-apps referencing **dev + test only** |
| `policies/*.yaml` | Machine-readable policy summaries for the verifiers |

## Safety model

* **No auto-sync anywhere.** Every Application omits `syncPolicy.automated`; no
  `prune`, no `selfHeal`, no `allowEmpty`, no `CreateNamespace`, no finalizers,
  no hooks, no image-updater/notifications annotations.
* **Source restricted** to this repo (no wildcard, no credential URL).
* **Destinations are placeholders** (`https://kubernetes.default.svc` for
  dev/test marked placeholder in the catalog; `*.invalid` for staging/prod).
  A placeholder destination is **not** an authorization to deploy.
* **Project denies cluster-scoped resources** (empty `clusterResourceWhitelist`)
  and **denies `Secret`**; namespaced kinds limited to what the chart renders.
* **Production is disabled** (`disabled-placeholder` + `do-not-sync`), never in
  any app-of-apps, and declares NO production readiness. Real production needs
  future operator approval, OIDC, a secret store, image-digest pinning, a backup
  target, a real destination, and a runtime smoke.

## Verify (no cluster)

```bash
python scripts/verify_argocd_manifests.py             # ARGOCD_MANIFESTS_VERIFY: PASS
python scripts/verify_gitops_environment_mapping.py   # GITOPS_ENVIRONMENT_MAPPING_VERIFY: PASS
python scripts/verify_gitops_production_isolation.py   # GITOPS_PRODUCTION_ISOLATION_VERIFY: PASS
./scripts/verify_gitops_argocd_baseline.sh            # GITOPS_ARGOCD_BASELINE_VERIFY: PASS
```

## Not created (by design)

`infra/gitops/credentials/`, `infra/gitops/secrets/`, `infra/gitops/clusters/` —
no credentials, no secrets, no real cluster definitions. ApplicationSet, Image
Updater, Notifications and Rollouts are out of scope.
