# infra/kubernetes — Runtime Inventory & Helm Foundation (Step 51.1)

Foundation only. **No cluster connection, no `kubectl`, no `helm install`.**

## Contents

| Path | Purpose |
| --- | --- |
| `runtime-inventory.yaml` | Evidence-backed inventory of every Compose service + one-shot jobs |
| `runtime-dependency-matrix.yaml` | Service-to-service dependency edges, each with evidence |
| `workload-security-inventory.yaml` | Step 51.2A per-component runtime security requirements |
| `rbac-safety-catalog.yaml` | Step 51.2A RBAC safety record (no Kubernetes API access) |
| `charts/ai-agents-platform/` | Multi-environment Helm foundation chart (v0.1.0) |

Docs: [runtime-service-inventory](../../docs/platform/runtime-service-inventory.md),
[helm-foundation](../../docs/platform/helm-foundation.md),
[environment-values-foundation](../../docs/platform/environment-values-foundation.md).

## Verify (no cluster)

```bash
python scripts/verify_kubernetes_runtime_inventory.py        # KUBERNETES_RUNTIME_INVENTORY_VERIFY: PASS
./scripts/verify_helm_foundation.sh                          # HELM_FOUNDATION_VERIFY: PASS
python scripts/verify_kubernetes_workload_security.py        # KUBERNETES_WORKLOAD_SECURITY_VERIFY: PASS
python scripts/verify_kubernetes_rbac_safety.py              # KUBERNETES_RBAC_SAFETY_VERIFY: PASS
./scripts/verify_kubernetes_security_rbac_baseline.sh        # KUBERNETES_SECURITY_RBAC_BASELINE_VERIFY: PASS
```

`verify_helm_foundation.sh` prefers a local `helm`, otherwise runs a pinned
official Helm container image (`alpine/helm:3.16.3`) via docker. It lints +
renders dev/test/staging/prod into the gitignored `.runtime/kubernetes-rendered/`
and scans the output for `:latest`, inline secrets, `kind: Secret`,
NodePort/LoadBalancer, Ingress and RBAC objects. It never connects to a cluster.

## Render manually (optional)

```bash
helm template ai-agents-platform charts/ai-agents-platform \
  -f charts/ai-agents-platform/values-dev.yaml
```

Rendered manifests are runtime artifacts and must never be committed.

## Scope boundary

In scope (Step 51.1): inventory, component catalog, generic
Deployment/Service/ConfigMap/ServiceAccount templates, four environment values,
schema, fail-closed production placeholder, lint + render verification.

In scope (Step 51.2A): restricted workload SecurityContext baseline (runAsNonRoot,
RuntimeDefault seccomp, no privesc, drop ALL, read-only root, size-limited
emptyDir writable paths), ServiceAccount hardening (token automount off), and
RBAC safety (no Role/ClusterRole, no Kubernetes API access).

Deferred (Step 51.2B+): NetworkPolicy (51.2B); PVC/StorageClass, Migration Job,
Backup CronJob (51.2C); HPA, PDB; and ArgoCD/GitOps (51.3).
