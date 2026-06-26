# Non-production ArgoCD Application (Step 56)

- Manifest: [`infra/gitops/nonproduction/aiagents-smoke-application.yaml`](../../infra/gitops/nonproduction/aiagents-smoke-application.yaml)
- Verifier: `scripts/verify_nonproduction_argocd_application.py` → `NONPROD_ARGOCD_APPLICATION_VERIFY`

The `aiagents-smoke` Application:

- **Project:** `aiagents-nonprod` (restricted).
- **Destination:** `aiagents-smoke-dev` only.
- **Source:** the public repo, path `infra/kubernetes/charts/ai-agents-platform`,
  Helm `valueFiles: [values-nonprod-smoke-local.yaml]` — read-only clone, **no
  credential** (public repo).
- **Sync policy:** **manual only** — there is no `spec.syncPolicy.automated` block,
  so auto-sync / prune / self-heal are all disabled. `CreateNamespace` is not
  enabled.

ArgoCD renders the chart with `helm template` and applies it directly (no Helm
release). Because Step 55 deployed the same chart via Helm, the Helm release is
uninstalled first so ArgoCD is the sole owner of the resources; the out-of-band
non-secret `aiagents-runtime-secrets` (created at bootstrap, never committed)
persists and is referenced by the synced Deployments.

Triggering a sync: `kubectl patch application aiagents-smoke -n argocd-nonprod
--type merge -p '{"operation":{"sync":{...}}}'` — no exposed server, no admin
password.
