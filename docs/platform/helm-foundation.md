# Helm Foundation (Step 51.1 / Stage 53A)

A lint-able, render-able Helm **foundation** chart for the AI-Agents-SWD
platform. This is a foundation only — it performs **no cluster connection**, is
**not** intended for `helm install`, and its production values are a
fail-closed, non-deployable placeholder.

Chart: [`infra/kubernetes/charts/ai-agents-platform`](../../infra/kubernetes/charts/ai-agents-platform)
(version `0.1.0`, appVersion `step-51.1-baseline`).

## Chart purpose

Turn the evidence-backed [runtime inventory](runtime-service-inventory.md) into
a values-driven set of generic Kubernetes manifests across four environments,
so later sub-stages can layer security, storage and GitOps on a stable base.

## Chart structure

```
charts/ai-agents-platform/
├── Chart.yaml                       # v2, version 0.1.0, production-ready=false
├── values.yaml                      # authoritative components map + safe defaults
├── values.schema.json               # JSON Schema (environment enum, required fields)
├── values-dev.yaml                  # dev overrides
├── values-test.yaml                 # test overrides (mirrors controlled test baseline)
├── values-staging-placeholder.yaml  # staging placeholder (not deployable)
├── values-prod-placeholder.yaml     # production placeholder (fail-closed, not deployable)
├── component-catalog.yaml           # inventory -> chart bridge / classification record
└── templates/
    ├── _helpers.tpl                 # labels, image ref, names
    ├── deployments.yaml             # generic Deployment (values loop)
    ├── services.yaml                # generic ClusterIP Service
    ├── configmaps.yaml              # shared non-secret config
    ├── serviceaccounts.yaml         # one SA per component (token automount off)
    ├── validate-values.yaml         # fail-closed validation (emits no resource)
    └── NOTES.txt
```

## Component catalog

`component-catalog.yaml` lists only services that are candidates to become
Kubernetes long-running workloads (the 20 first-party services + optional
postgres/redis + test-only vault). One-shot jobs and observability backends are
recorded as **deferred**, never as Deployments. `values.yaml` carries the
authoritative `components:` map the templates consume; the catalog is kept in
sync and asserted complete by `verify_kubernetes_runtime_inventory.py` and the
`tests/test_kubernetes_component_catalog.py` suite.

## Generic template model

One Deployment + one Service per *enabled* component, driven by a values loop —
no per-service copy/paste YAML. Each Deployment renders: labels/selector,
replicas, RollingUpdate strategy, image, container port, `envFrom` shared
ConfigMap, inline non-secret env, secret env via `secretKeyRef`, liveness +
readiness probes, resource requests/limits, terminationGracePeriodSeconds.

## Image placeholders

First-party images use `aiagents/<service>:step-51-1-placeholder` with an empty
digest — **not** wired to any registry and **not** a real digest. Infrastructure
images are real pinned upstream tags (`postgres:16`, `redis:7`,
`hashicorp/vault:1.17`). `:latest` is forbidden and enforced by both
`validate-values.yaml` and tests.

## Service model

ClusterIP only. Service name == component name so in-cluster DNS used by env
URLs (`http://orchestrator:8000`, etc.) resolves. **No** NodePort, LoadBalancer
or Ingress. Postgres/Redis Services are internal-only and never publicly
exposed.

## ConfigMap / Secret reference model

The shared ConfigMap holds only non-sensitive config + safety flags. The chart
**never creates a Secret** (`secrets.create` must be false). Credentials are
referenced from an existing Secret by name + key (`commonSecretRefs` →
`secretKeyRef`); no values appear anywhere.

## Health probes & resources

HTTP `/health` liveness+readiness for all first-party services; `exec` probes
(`pg_isready`, `redis-cli ping`) for postgres/redis. Every enabled component
carries resource requests and limits (schema-required).

## ServiceAccount foundation

One ServiceAccount per enabled component, `automountServiceAccountToken: false`.
No Role/RoleBinding/ClusterRole/ClusterRoleBinding — Kubernetes API access is
deferred to a future stage with an explicit need.

## Current limitations

- Not deployable: `global.realDeployEnabled` is false in every shipped file.
- No SecurityContext hardening (opt-in, off).
- No persistent storage; postgres/redis dev/test components are ephemeral.
- Observability and one-shot jobs are not packaged.

## Explicit Step 51.2 boundary

Deferred to Step 51.2 and later: SecurityContext hardening, NetworkPolicy /
default-deny, RBAC Role/ClusterRole, PVC/StorageClass, workspace RWX, Migration
Job, Backup CronJob, HPA, PodDisruptionBudget, manifest/secret policy
validators, and (Step 51.3+) ArgoCD / GitOps.
