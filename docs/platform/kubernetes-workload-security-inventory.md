# Kubernetes Workload Security Inventory (Step 51.2A / Stage 53B)

Evidence-backed per-component runtime requirements, produced **before** applying
Helm SecurityContext settings. Machine-readable source:
[`workload-security-inventory.yaml`](../../infra/kubernetes/workload-security-inventory.yaml).

## Method

Inspected each component's Dockerfile, base image, USER directive, startup
command, and source disk-write behaviour (`apps/*`, `agents/*`,
`docker-compose.yml`). Recorded names + classification + evidence only — no
secret values.

## Key findings

- All 20 first-party services: `python:3.12-slim`, WORKDIR `/app`, **no USER
  directive** → currently run as root. Image USER remediation is **recorded,
  not changed** in this stage.
- Only disk writes in first-party source are under `/tmp` (workspace roots +
  tempfile). No `/var`, `/data`, `/app`, SQLite, or file-logging writes.
- postgres/redis/vault are official upstream images with their own UID/GID and
  writable-path needs → documented per-component overrides (not the first-party
  fixed-UID assumption).

## Coverage

| Classification | Count | Profile | Notes |
| --- | --: | --- | --- |
| Core application | 1 | restricted | orchestrator |
| Governance | 3 | restricted | |
| Communication | 3 | restricted | |
| Worker | 3 | restricted | |
| Agent | 10 | restricted | 4 workspace-writing agents get 1Gi `/tmp` |
| postgres | 1 | override | UID 999, read-only root off, storage deferred |
| redis | 1 | override | UID 999, read-only root on, `/data` emptyDir |
| vault | 1 | override (test-only) | UID 100, not deployed |

## runtimeCompatibility status

- `requires_cluster_smoke` — baseline applied, but non-root / read-only-root
  start cannot be confirmed without a cluster (deferred). Applies to all
  first-party (root images) + postgres/redis/vault.

## Observability

Out of scope for this stage; recorded as deferred (Step 51.4).

## Deferred

- Persistent storage (PVC / workspace RWX) → Step 51.2C.
- NetworkPolicy → Step 51.2B.

See [kubernetes-workload-security-baseline.md](kubernetes-workload-security-baseline.md)
for the applied profile and [kubernetes-rbac-safety-baseline.md](kubernetes-rbac-safety-baseline.md)
for the RBAC posture.
