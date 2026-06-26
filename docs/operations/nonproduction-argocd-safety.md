# Non-production ArgoCD safety (Step 56)

- Verifier: `scripts/verify_nonproduction_argocd_safety.py` → `NONPROD_ARGOCD_SAFETY_VERIFY`
- Safety fields verifier: `scripts/verify_nonproduction_argocd_safety_fields.py` → `NONPROD_ARGOCD_SAFETY_FIELDS_VERIFY`

## Asserted invariants

- No auto-sync / prune / self-heal (committed summary + live Application).
- No production namespace touched; destination is `aiagents-smoke-dev` only.
- No public ingress / LoadBalancer / NodePort in `argocd-nonprod` or
  `aiagents-smoke-dev`; ArgoCD server not exposed.
- No production ArgoCD sync; no production Kubernetes deploy.
- No committed token / admin password / kubeconfig / Secret anywhere under
  `infra/gitops` (scanned).
- No external repo credential used (public repo, read-only clone).
- `production_executed_true_count == 0`.

## Live `/operations/safety` fields (Step 56)

```
nonprod_argocd_enabled=true              nonprod_argocd_auto_sync_enabled=false
nonprod_argocd_namespace=argocd-nonprod  nonprod_argocd_prune_enabled=false
nonprod_argocd_installed=true            nonprod_argocd_self_heal_enabled=false
nonprod_argocd_project_created=true      nonprod_argocd_destination_namespace=aiagents-smoke-dev
nonprod_argocd_application_created=true  nonprod_argocd_production_namespace_touched=false
nonprod_argocd_manual_sync_performed=true   nonprod_argocd_public_ingress_enabled=false
nonprod_argocd_manual_sync_succeeded=true   nonprod_argocd_loadbalancer_enabled=false
argocd_production_sync_performed=false   kubernetes_production_deploy_performed=false
production_executed_true_count=0
```

These are driven by the committed redacted summary (in-image); the live runtime
report is never committed. **Claude Code does not decide production readiness.**
