# Production Target Assessment Model (Step 63A)

Source: [`infra/readiness/production-target-assessment-model.yaml`](../../infra/readiness/production-target-assessment-model.yaml).

Assesses whether a real production target exists (cluster, namespace, ArgoCD app, domain,
database, secret store, observability, backup target, rollback target). A kind
non-production cluster is NEVER substituted for a production cluster; non-production ArgoCD
is NEVER a production ArgoCD (`kindNonprodIsProductionCluster: false`,
`nonprodArgocdIsProductionArgocd: false`, `productionTargetExists: false`). Every item is
currently `missing`; nothing is faked.
