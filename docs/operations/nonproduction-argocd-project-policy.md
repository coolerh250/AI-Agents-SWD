# Non-production ArgoCD project policy (Step 56)

- Policy descriptor: [`infra/gitops/nonproduction-argocd-project-policy.yaml`](../../infra/gitops/nonproduction-argocd-project-policy.yaml)
- AppProject manifest: [`infra/gitops/nonproduction/aiagents-nonprod-project.yaml`](../../infra/gitops/nonproduction/aiagents-nonprod-project.yaml)
- Verifier: `scripts/verify_nonproduction_argocd_project_policy.py` → `NONPROD_ARGOCD_PROJECT_POLICY_VERIFY`

The `aiagents-nonprod` AppProject is **restricted**:

- **Single destination:** `aiagents-smoke-dev` @ `https://kubernetes.default.svc`
  (no wildcard namespace/server).
- **Single source repo:** the public repo only (no wildcard `sourceRepos`).
- **No cluster-scoped resources:** `clusterResourceWhitelist: []`.
- **Namespaced kinds only:** Deployment, StatefulSet, Service, ConfigMap, Secret,
  ServiceAccount, PersistentVolumeClaim, Job, CronJob, NetworkPolicy (the kinds the
  non-production chart renders).
- **Forbidden namespaces:** default, kube-system, argocd, production, prod.
- **No auto-sync** at the project level (sync policy is manual, on the Application).

The verifier asserts the committed manifest matches this descriptor.
