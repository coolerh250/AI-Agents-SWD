# infra/kubernetes — Runtime Inventory & Helm Foundation (Step 51.1)

Foundation only. **No cluster connection, no `kubectl`, no `helm install`.**

## Contents

| Path | Purpose |
| --- | --- |
| `runtime-inventory.yaml` | Evidence-backed inventory of every Compose service + one-shot jobs |
| `runtime-dependency-matrix.yaml` | Service-to-service dependency edges, each with evidence |
| `workload-security-inventory.yaml` | Step 51.2A per-component runtime security requirements |
| `rbac-safety-catalog.yaml` | Step 51.2A RBAC safety record (no Kubernetes API access) |
| `network-connectivity-catalog.yaml` | Step 51.2B canonical connectivity model (49 internal edges) |
| `storage-consumer-inventory.yaml` | Step 51.2C1 filesystem/storage consumer inventory |
| `storage-ownership-catalog.yaml` | Step 51.2C1 typed stores + data lifecycle + per-env strategy |
| `batch-operation-inventory.yaml` | Step 51.2C2 migration/backup/restore inventory + risk |
| `batch-command-catalog.yaml` | Step 51.2C2 fixed, shell-free batch commands |
| `fixtures/` | Step 51.2C2 verifier-only render fixtures (e.g. restore scaffold) |
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
python scripts/verify_kubernetes_network_topology.py         # KUBERNETES_NETWORK_TOPOLOGY_VERIFY: PASS
python scripts/verify_kubernetes_network_policy.py           # KUBERNETES_NETWORK_POLICY_VERIFY: PASS
python scripts/verify_kubernetes_service_connectivity.py     # KUBERNETES_SERVICE_CONNECTIVITY_VERIFY: PASS
./scripts/verify_kubernetes_network_baseline.sh              # KUBERNETES_NETWORK_BASELINE_VERIFY: PASS
python scripts/verify_kubernetes_storage_inventory.py        # KUBERNETES_STORAGE_INVENTORY_VERIFY: PASS
python scripts/verify_kubernetes_data_lifecycle.py           # KUBERNETES_DATA_LIFECYCLE_VERIFY: PASS
python scripts/verify_kubernetes_storage_manifest.py         # KUBERNETES_STORAGE_MANIFEST_VERIFY: PASS
./scripts/verify_kubernetes_storage_baseline.sh             # KUBERNETES_STORAGE_BASELINE_VERIFY: PASS
python scripts/verify_kubernetes_batch_operation_inventory.py # KUBERNETES_BATCH_OPERATION_INVENTORY_VERIFY: PASS
python scripts/verify_kubernetes_migration_job.py            # KUBERNETES_MIGRATION_JOB_VERIFY: PASS
python scripts/verify_kubernetes_backup_cronjob.py           # KUBERNETES_BACKUP_CRONJOB_VERIFY: PASS
python scripts/verify_kubernetes_restore_job.py              # KUBERNETES_RESTORE_JOB_VERIFY: PASS
python scripts/verify_kubernetes_batch_job_policy.py         # KUBERNETES_BATCH_JOB_POLICY_VERIFY: PASS
./scripts/verify_kubernetes_batch_jobs_baseline.sh          # KUBERNETES_BATCH_JOBS_BASELINE_VERIFY: PASS
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

In scope (Step 51.2B): default-deny NetworkPolicy baseline (ingress + egress),
scoped DNS egress, per-target ingress / per-source egress from the connectivity
catalog (49 internal edges), Postgres/Redis isolation, external egress disabled.

In scope (Step 51.2C1): storage consumer inventory + data lifecycle, typed store
ownership, generated RWO PVCs for in-cluster Postgres/Redis in dev/test only,
Deployment volume integration, fail-closed environment storage rules. No
StorageClass/PV resource, no hostPath/NFS, no real storage class/claim. See
[kubernetes-storage-baseline](../../docs/platform/kubernetes-storage-baseline.md).

In scope (Step 51.2C2): controlled migration Job, disabled+suspended backup
CronJob, disabled restore Job scaffold — fixed shell-free commands (catalogued),
advisory-lock migration, secretKeyRef-only credentials, restricted security,
dedicated token-off ServiceAccounts, minimal DB-only NetworkPolicy, all
disabled-by-default and fail-closed in staging/production. Templates validated,
NOT executed; no cluster. See
[kubernetes-batch-job-policy](../../docs/platform/kubernetes-batch-job-policy.md).

In scope (Step 51.3): ArgoCD GitOps baseline (AppProject + dev/test/staging/
production Application manifests + non-production app-of-apps + environment
catalog), under `infra/gitops/` — validated, NOT applied (no ArgoCD, no sync, no
cluster). See [infra/gitops/README.md](../gitops/README.md) and
[argocd-gitops-baseline](../../docs/platform/argocd-gitops-baseline.md).

Deferred (51.4): runtime visibility. HPA/PDB and production
migration/backup/restore execution + real GitOps rollout also deferred.
