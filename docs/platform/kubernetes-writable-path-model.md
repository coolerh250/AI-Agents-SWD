# Kubernetes Writable Path Model (Step 51.2A / Stage 53B)

With `readOnlyRootFilesystem: true` for first-party workloads, every required
write goes through an explicit, size-limited `emptyDir`. This stage handles
**ephemeral** runtime writable paths only; persistent storage is deferred to
Step 51.2C.

## Evidence method

Source-derived (not assumed). A scan of `apps/*` + `agents/*` found that the
only disk writes are under `/tmp`:

- workspace roots default to `/tmp/aiagents-workspaces`
  (development-agent, workspace-operator-agent, mini-delivery-pilot-agent);
- qa-agent uses `tempfile.TemporaryDirectory` (=> `/tmp`).

No `/var`, `/data`, `/app`, SQLite, or file-logging writes exist. Logs go to
stdout. Recorded per component in
[`workload-security-inventory.yaml`](../../infra/kubernetes/workload-security-inventory.yaml).

## Ephemeral paths (this stage)

| Component(s) | Mount | Type | sizeLimit |
| --- | --- | --- | --- |
| all first-party (default) | `/tmp` | emptyDir | 256Mi |
| development/qa/workspace-operator/mini-delivery-pilot agents | `/tmp` | emptyDir | 1Gi |
| redis | `/data` | emptyDir | 256Mi |

The deployment template applies a default `/tmp` (256Mi) emptyDir to any
component without an explicit `security.writablePaths`; components needing more
(or a different mount) declare it in values. Every `emptyDir` carries a
`sizeLimit` (schema-required).

## Persistent paths — resolved in Step 51.2C1

This 51.2A inventory recorded these as deferred; **Step 51.2C1 now resolves the
datastore persistence** (the 51.2A `deferred.persistentStorage` record is kept
as the historical hand-off point):

- **postgres** PGDATA (`/var/lib/postgresql/data`) and **redis** `/data` are now
  backed by **generated RWO PVCs in dev/test** (when the storage layer replaces
  the ephemeral emptyDir). See
  [datastore persistence](kubernetes-datastore-persistence.md).
- **workspace** stays **ephemeral per-pod** (not shared, no RWX) — see
  [workspace storage model](kubernetes-workspace-storage-model.md).
- **reports / audit-forensic exports** remain `unresolved` (writers are deferred
  one-shot jobs) — see [data lifecycle](kubernetes-data-lifecycle.md).

Backup storage stays deferred to **Step 51.2C2**.

## Safety rules (enforced)

- **No hostPath** anywhere (schema has no hostPath field; `validate-values.yaml`
  fails on a `hostPath` key; the verifier fails on a rendered hostPath volume).
- **No writable `/`, `/app`, `/etc`**, no docker-socket mount.
- Mount paths must be absolute; every writable path has a `sizeLimit`.
- The production placeholder uses only inventory-recorded writable paths.
