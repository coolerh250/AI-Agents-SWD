# Non-production ArgoCD install boundary (Step 56)

Hard limits for the local non-production ArgoCD install.

- Boundary: [`infra/gitops/nonproduction-argocd-install-boundary.yaml`](../../infra/gitops/nonproduction-argocd-install-boundary.yaml)
- Verifier: `scripts/verify_nonproduction_argocd_install_boundary.py` → `NONPROD_ARGOCD_INSTALL_BOUNDARY_VERIFY`

- **Namespace:** `argocd-nonprod` (never the production-like `argocd`).
- **Version / source:** ArgoCD `v2.13.3`, official install manifest, applied via
  `kubectl apply -k` with a kustomize namespace override; the ClusterRoleBinding
  subject namespaces are patched to `argocd-nonprod` (kustomize does not rewrite
  them).
- **Exposure:** ClusterIP only — no Ingress, no LoadBalancer, no NodePort, server
  not exposed externally.
- **SSO:** disabled — `argocd-dex-server`, `argocd-applicationset-controller`, and
  `argocd-notifications-controller` are scaled to 0.
- **Credentials:** no admin password / token / kubeconfig / registry credential is
  ever committed; manual sync is triggered via `kubectl patch` (no admin password
  needed).
- **Scope:** no production AppProject / Application / repo credential / secret; no
  auto-sync.

ArgoCD's own controller uses a cluster-scoped ClusterRole (inherent to ArgoCD); the
**AppProject** (not the install) is what confines the app to `aiagents-smoke-dev`
with no cluster-scoped resources — see
[nonproduction-argocd-project-policy.md](nonproduction-argocd-project-policy.md).
