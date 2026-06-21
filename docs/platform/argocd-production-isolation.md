# ArgoCD Production Isolation (Step 51.3 / Stage 53F)

The production placeholder Application
([production-placeholder.yaml](../../infra/gitops/argocd/applications/production-placeholder.yaml))
is deliberately **disabled and non-deployable**. It exists to prove a safe
production shape — never to deploy.

## Isolation guarantees

* **Disabled annotations**: `disabled-placeholder=true`, `do-not-sync=true`,
  `production-placeholder=true`, `real-deploy-enabled=false`.
* **Future-requirement annotations** (none satisfied here):
  `requires-operator-approval`, `requires-production-oidc`,
  `requires-secret-store`, `requires-image-digest`, `requires-backup-target`,
  `requires-runtime-smoke`.
* **No automated sync**, no prune/selfHeal, no finalizers, no hooks.
* **Obvious placeholder destination**:
  `https://production-cluster-placeholder.invalid` + namespace
  `ai-agents-production-placeholder` (never a real cluster/namespace).
* **Excluded from the app-of-apps** — it can never be pulled into the
  non-production app-of-apps (which includes dev + test only).
* **Project** allows no production/wildcard namespace and no cluster-scoped
  resources / Secret.
* **Production values fail closed**: `realDeployEnabled=false`, internal
  Postgres/Redis disabled (no generated PVC), all batch jobs `renderTemplate=false`,
  external egress disabled, operator actions + production backup schedule off.

## What real production would still require

Operator approval, production OIDC, a production secret store, image-digest
pinning, a real backup target, a real destination cluster, and a runtime smoke
test. Claude Code reports observations only and does **not** decide Kubernetes,
GitOps, or Production readiness.

Verifier: `scripts/verify_gitops_production_isolation.py`
(`GITOPS_PRODUCTION_ISOLATION_VERIFY: PASS`).
