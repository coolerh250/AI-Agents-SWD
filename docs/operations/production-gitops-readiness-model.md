# Production GitOps Readiness Model (Step 63A)

Source: [`infra/readiness/production-gitops-readiness-model.yaml`](../../infra/readiness/production-gitops-readiness-model.yaml).

Model / evidence check only. No production ArgoCD application is created, no sync is
triggered, no manifest is applied (`creates_production_argocd_app: false`,
`triggers_sync: false`, `applies_manifest: false`). The non-production ArgoCD
(`aiagents-smoke`) is a REFERENCE only and is never marked production ready
(`nonprodArgocdIsProductionReady: false`). Production GitOps items are currently `missing` →
contributes to `no_go`.
