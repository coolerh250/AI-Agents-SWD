# Kubernetes Non-Production Limitations (Step 51 / Stage 53G)

The Step 51 Kubernetes / Helm / ArgoCD baseline is **validated, not deployed**.
The following are deliberately out of scope and remain open before any real
production rollout. None is a security or audit failure; all are recorded
limitations.

## Open limitations

* No Kubernetes cluster connected; no `kubectl`.
* No Helm install / upgrade; no ArgoCD installed; no `argocd app sync`.
* No real destination cluster; no repo credentials.
* No production OIDC; no production secret store.
* No image-digest pinning (placeholder tags only).
* No real cloud backup target; no production backup schedule; no production
  restore approval.
* No workspace production RWX / object storage (ephemeral per-pod only).
* First-party images still require a non-root **cluster smoke**.
* Job images still require a container-native pg_dump/psql **runtime smoke**.
* No runtime cluster smoke; no real pager / escalation.

## Not allowed (hard safety)

Security failure, audit failure, tamper residue, production execution, secret
leak, cluster action, GitHub write, PR creation, deployment action, ArgoCD sync,
auto-sync enabled, production app active, or a runtime write endpoint. Any of
these is a FAIL, not a limitation.

## Next recommended phase

Install a real ArgoCD against a real (non-production) destination, provision
production OIDC + secret store + image digests, and run cluster smokes for the
non-root first-party images and the container-native batch-job images — each
behind explicit operator approval. Claude Code reports observations only and
does not decide Kubernetes, GitOps, or Production readiness.
