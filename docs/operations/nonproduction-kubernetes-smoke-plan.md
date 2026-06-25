# Non-production Kubernetes Runtime Smoke Plan (Step 55)

Source: [`infra/kubernetes/nonproduction-cluster-smoke-plan.yaml`](../../infra/kubernetes/nonproduction-cluster-smoke-plan.yaml)

Takes the Step 51 static Kubernetes/Helm baseline to a **real non-production cluster**
for a smoke validation. **Framework ready, NOT production-enforced.** The smoke runs
ONLY when the preflight confirms a safe non-production cluster; otherwise it is
**BLOCKED_NO_SAFE_CLUSTER** (never faked).

## Preflight gate
Requires: kubectl + helm + kubeconfig + a reachable, **non-production** context +
namespaced create permission. Forbidden: production context/namespace, cluster-admin
creation, default-namespace deploy. On unsafe/missing → blocked.

## Ordered steps (each with a verifier marker)
preflight → namespace → helm → pod_startup → service_health → connectivity →
networkpolicy → storage → securitycontext → batch_jobs → report.

## Forbidden (enforced by runner + verifiers)
production deploy / namespace, ArgoCD sync, GitHub write, PR, image push, registry
login, production secret/OIDC/backup/restore, public ingress, LoadBalancer, ClusterRole/
binding, CRD, destructive job, kubeconfig/token commit.

## Current status (10.0.1.31)
No kubectl/helm/kubeconfig present → **BLOCKED_NO_SAFE_CLUSTER**; framework verified,
no smoke executed. See
[verification](nonproduction-kubernetes-runtime-smoke-verification.md) and
[limitations](nonproduction-kubernetes-runtime-smoke-limitations.md).
