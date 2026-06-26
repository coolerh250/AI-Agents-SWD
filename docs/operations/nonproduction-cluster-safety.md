# Non-production cluster safety (Step 55.1)

Safety guarantees asserted against the live smoke cluster before/after the runtime
smoke.

- Verifier: `scripts/verify_nonproduction_cluster_safety.py` → `NONPROD_CLUSTER_SAFETY_VERIFY`

## What it asserts (live)

- The namespace (`aiagents-smoke-dev`) contains no `prod`/`production` substring.
- A safe non-production context (no `prod`/`production`); otherwise **BLOCKED** (never
  a faked PASS).
- **No Service of type `LoadBalancer` or `NodePort`** in the smoke namespace.
- **No `Ingress`** in the smoke namespace.
- The runtime smoke report's production invariants are false:
  `productionExecuted=false`, `kubernetesProductionDeployPerformed=false`,
  `argocdSyncPerformed=false`.

## Credential safety

The verifier never prints a kubeconfig, token, certificate, or context name. The
in-cluster `aiagents-runtime-secrets` holds only non-secret in-cluster service URLs
(trust auth, no password) and is **never committed**. No kubeconfig / token / cert /
secret is committed to the repository.

## Forbidden actions (whole stage)

Production deploy, production namespace, ArgoCD sync, GitHub write, image push,
registry login, public ingress, LoadBalancer, destructive/restore/backup jobs.
`production_executed_true_count` stays `0`. **Claude Code does not decide production
readiness.**
