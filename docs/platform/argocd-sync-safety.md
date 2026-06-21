# ArgoCD Sync Safety (Step 51.3 / Stage 53F)

Every Application (including the app-of-apps) is **manual-only**. No automated
reconciliation, no destructive auto-operations, nothing applied in this stage.

## Disabled sync settings

| Setting | State | Why |
| --- | --- | --- |
| `syncPolicy.automated` | **absent** | no auto-sync / auto-reconcile |
| `prune` | not enabled | never auto-delete resources |
| `selfHeal` | not enabled | never auto-revert drift |
| `allowEmpty` | not enabled | never sync an empty desired state |
| `CreateNamespace` | `false` | never auto-create namespaces |
| finalizers | none | avoids cascade-delete risk |
| sync hooks (`PreSync`/`PostSync`/…) | none | no hook-driven side effects |
| `argocd-image-updater` annotation | none | no automatic image bumps |
| `notifications.argoproj.io` annotation | none | no outbound webhooks |

Dev and test are **also** manual-only — being "active" in the catalog does not
enable sync.

## Source + revision safety

* Source repo is exactly `https://github.com/coolerh250/AI-Agents-SWD.git` (no
  wildcard, no `user:token@host`, no SSH URL, no external chart repo).
* `targetRevision` is a fixed ref, never `HEAD` or `*`. Production must pin an
  immutable tag/digest before any real rollout (recorded, not done here).

Verifier: `scripts/verify_argocd_manifests.py`
(`ARGOCD_MANIFESTS_VERIFY: PASS`) + the combined
`scripts/verify_gitops_argocd_baseline.sh`
(`GITOPS_ARGOCD_BASELINE_VERIFY: PASS`).
