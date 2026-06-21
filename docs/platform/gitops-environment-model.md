# GitOps Environment Model (Step 51.3 / Stage 53F)

Source of truth:
[gitops-environments.yaml](../../infra/gitops/gitops-environments.yaml). The
environment-mapping verifier asserts this catalog matches the Application
manifests and the Helm values files.

## Environment → values → Application

| Environment | Values file | Application | Active | Auto-sync | Destination |
| --- | --- | --- | --- | --- | --- |
| dev | `values-dev.yaml` | `ai-agents-platform-dev` | yes (catalog) | **no** | `kubernetes.default.svc` (placeholder) |
| test | `values-test.yaml` | `ai-agents-platform-test` | yes (catalog) | **no** | `kubernetes.default.svc` (placeholder) |
| staging-placeholder | `values-staging-placeholder.yaml` | `…-staging-placeholder` | **no** | no | `*.invalid` placeholder |
| production-placeholder | `values-prod-placeholder.yaml` | `…-production-placeholder` | **no** (disabled) | no | `*.invalid` placeholder |

"Active" means *eligible to become a controlled target later* — it is **not** an
authorization to sync. Auto-sync is disabled everywhere; nothing is applied in
this stage (`meta.clusterConnected=false`, `meta.syncPerformed=false`).

## Mapping rules (enforced)

* Every Application's `helm.valueFiles` equals its catalog `valuesFile`.
* dev/test never use production values; production uses only
  `values-prod-placeholder.yaml`.
* Every referenced values file exists in the chart.
* `source.path` is the chart path; `repoURL` is exactly this repo;
  `targetRevision` is a fixed ref (never `HEAD`/`*`). **Production must move to an
  immutable tag/digest** before any real rollout — recorded, not done here.

Verifier: `scripts/verify_gitops_environment_mapping.py`
(`GITOPS_ENVIRONMENT_MAPPING_VERIFY: PASS`).
