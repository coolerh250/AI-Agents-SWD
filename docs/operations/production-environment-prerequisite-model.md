# Production Environment Prerequisite Model (Step 62)

Source: [`infra/readiness/production-environment-prerequisite-model.yaml`](../../infra/readiness/production-environment-prerequisite-model.yaml).
SDK: `shared/sdk/production_readiness/prerequisites.py`.

The production environment does **not** exist yet. All 12 prerequisites (production cluster,
namespace policy, secrets, ArgoCD application, backup, restore tested, monitoring, alerting,
rollback path, approval channel, incident owner, change window) are currently missing /
not_configured.

A kind non-production cluster is never substituted for production; the non-production ArgoCD
is never treated as production ArgoCD (`kindNonprodIsProduction: false`,
`nonprodArgocdIsProductionArgocd: false`, `productionEnvironmentExists: false`). Nothing is
faked.
