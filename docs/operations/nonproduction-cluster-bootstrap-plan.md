# Non-production Kubernetes cluster bootstrap plan (Step 55.1)

Brings up a **safe, local-only, throwaway** non-production Kubernetes cluster so the
Step 55 runtime smoke can run for real. Closes the Step 55
`BLOCKED_NO_SAFE_CLUSTER` gap. This is **not** a production action and does **not**
make the platform production-ready.

- Plan: [`infra/kubernetes/nonproduction-cluster-bootstrap-plan.yaml`](../../infra/kubernetes/nonproduction-cluster-bootstrap-plan.yaml)
- Script: [`scripts/bootstrap_nonproduction_kind_cluster.sh`](../../scripts/bootstrap_nonproduction_kind_cluster.sh)
- Verifier: `scripts/verify_nonproduction_cluster_bootstrap.py` → `NONPROD_CLUSTER_BOOTSTRAP_VERIFY`

## Chosen option: kind (Option A)

Docker is available on the test host and kind needs no cloud / production
credential. The cluster is created from
[`infra/kubernetes/kind/nonproduction-kind-cluster.yaml`](../../infra/kubernetes/kind/nonproduction-kind-cluster.yaml)
with node image `kindest/node:v1.31.2`; the resulting context is
`kind-aiagents-smoke` (no `prod`/`production` substring).

## Steps

1. **Tooling** — kubectl + helm + kind installed from official sources
   (see [nonproduction-kubernetes-tooling.md](nonproduction-kubernetes-tooling.md)).
2. **Cluster** — `bootstrap_nonproduction_kind_cluster.sh` creates the kind cluster
   (idempotent).
3. **Images** — already-built local compose images are retagged
   `aiagents/<component>:smoke-local` and `kind load`-ed. **Nothing is pushed; no
   registry login.** postgres/redis use public images pulled on demand.
4. **Namespace + secret** — namespace `aiagents-smoke-dev` and a **non-secret**
   in-cluster `aiagents-runtime-secrets` (in-cluster service URLs with trust auth —
   no password/token/cert) are created. **The secret is never committed.**
5. **Install** — `run_nonproduction_helm_smoke.sh --namespace aiagents-smoke-dev
   --values infra/kubernetes/charts/ai-agents-platform/values-nonprod-smoke-local.yaml`.
6. **Smoke** — `run_nonproduction_runtime_smoke.py` writes the live report; the
   Step 55 verifiers consume it.

```bash
# one-shot from the repo root on the test host
scripts/bootstrap_nonproduction_kind_cluster.sh
scripts/run_nonproduction_helm_smoke.sh --namespace aiagents-smoke-dev \
  --values infra/kubernetes/charts/ai-agents-platform/values-nonprod-smoke-local.yaml
scripts/verify_nonproduction_cluster_ready_for_smoke.sh
```

## Scope

Sized for the non-production host: a control-plane subset — orchestrator,
policy-engine, approval-engine, audit-service, in-cluster postgres + redis. The
remaining platform components stay **disabled** for this smoke (recorded honestly in
the runtime report — not a faked full deploy). See
[nonproduction-kubernetes-runtime-smoke-limitations.md](nonproduction-kubernetes-runtime-smoke-limitations.md).

## Forbidden (enforced by the script + verifiers)

Production cluster / namespace / `default` / `kube-system` / `argocd` namespaces,
public ingress, LoadBalancer, registry login, image push, production secret /
DB / Redis / Vault, ArgoCD sync, cluster-admin expansion. `production_executed`
stays `0`; Claude Code does **not** decide production readiness.
