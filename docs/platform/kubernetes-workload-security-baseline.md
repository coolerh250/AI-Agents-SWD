# Kubernetes Workload Security Baseline (Step 51.2A / Stage 53B)

A restricted, values-driven SecurityContext baseline applied to every workload
in the [`ai-agents-platform`](../../infra/kubernetes/charts/ai-agents-platform)
chart. Static manifest baseline only — **no cluster connection, no kubectl, no
helm install**. Runtime non-root / read-only-root start is an observation that
requires a future cluster smoke (deferred).

## Security profile

`global.workloadSecurity` (restricted-baseline), applied to all enabled
components:

| Field | Value |
| --- | --- |
| runAsNonRoot | `true` (not overridable) |
| runAsUser / runAsGroup | `10001` / `10001` (component-overridable, never 0) |
| fsGroup | `10001` (component-overridable) |
| seccompProfile.type | `RuntimeDefault` (only allowed value) |
| allowPrivilegeEscalation | `false` (not overridable) |
| privileged | `false` (not overridable) |
| readOnlyRootFilesystem | `true` (component-overridable for infra) |
| capabilities | `drop: [ALL]`, **no add ever** |
| automountServiceAccountToken | `false` (SA + pod spec) |

Component `security` blocks may override **only** runAsUser/runAsGroup/fsGroup,
readOnlyRootFilesystem and writablePaths. There is no privileged/root/cap-add/
hostPath escape hatch — the schema (`additionalProperties: false`) and
`validate-values.yaml` reject any attempt.

## Component coverage

23 components inventoried in
[`workload-security-inventory.yaml`](../../infra/kubernetes/workload-security-inventory.yaml).

- **20 first-party** (core/governance/communication/worker/agent): restricted
  baseline, runAsUser 10001, read-only root, writable `/tmp` emptyDir.
- **postgres**: official UID/GID 999, read-only root **OFF** (writes PGDATA +
  sockets); persistent storage deferred to 51.2C.
- **redis**: UID/GID 999, read-only root **ON** with writable `/data` emptyDir.
- **vault**: test-only (UID 100), read-only root OFF; baseline drops ALL caps
  (a deployed dev vault would need `VAULT_DISABLE_MLOCK` — not deployed here).

## Pod / Container SecurityContext

Rendered by `templates/_security_helpers.tpl`
(`aiagents.podSecurityContext` + `aiagents.containerSecurityContext`). Pod-level
carries runAsNonRoot/runAsUser/runAsGroup/fsGroup/seccomp; container-level
carries allowPrivilegeEscalation/privileged/readOnlyRootFilesystem/capabilities.

## Read-only root filesystem & writable paths

First-party workloads run with `readOnlyRootFilesystem: true`. Ephemeral writes
go to an `emptyDir` (`/tmp`, sizeLimit 256Mi; 1Gi for the four workspace-writing
agents). `PYTHONDONTWRITEBYTECODE=1` keeps `.pyc` off the read-only root. See
[kubernetes-writable-path-model.md](kubernetes-writable-path-model.md).

## Runtime compatibility caveat

The first-party images are `python:3.12-slim` with **no USER directive** (they
run as root today). The chart imposes non-root at the pod level, but whether
each image actually starts as UID 10001 with a read-only root cannot be
confirmed without a cluster smoke test. Every such component is flagged
`runtimeCompatibility.status: requires_cluster_smoke`. Image USER remediation is
**recorded, not performed**, in this stage.

## No cluster validation

Verified statically by `verify_kubernetes_workload_security.py` against rendered
manifests (helm 3.16.3 via pinned container). No `helm install`, no `kubectl`,
no cluster API call. Deferred: NetworkPolicy (51.2B), storage/PVC + Migration
Job + Backup CronJob (51.2C), ArgoCD (51.3).
