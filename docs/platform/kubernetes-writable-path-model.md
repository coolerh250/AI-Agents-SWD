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

## Persistent paths — deferred to Step 51.2C

NOT faked as emptyDir here:

- **postgres** PGDATA (`/var/lib/postgresql/data`) — marked
  `type: deferred_to_51_2C`;
- redis persistence; workspace RWX (cross-pod) for the workspace agents;
  reports/artifacts storage for the orchestrator.

These are recorded under `deferred.persistentStorage` in the inventory.

## Safety rules (enforced)

- **No hostPath** anywhere (schema has no hostPath field; `validate-values.yaml`
  fails on a `hostPath` key; the verifier fails on a rendered hostPath volume).
- **No writable `/`, `/app`, `/etc`**, no docker-socket mount.
- Mount paths must be absolute; every writable path has a `sizeLimit`.
- The production placeholder uses only inventory-recorded writable paths.
