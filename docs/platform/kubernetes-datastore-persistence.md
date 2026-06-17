# Kubernetes Datastore Persistence (Step 51.2C1 / Stage 53D)

In-cluster PostgreSQL and Redis are **Dev/Test only**. Staging/production use
external managed datastores. Values: `storage.postgres` / `storage.redis` in
[values.yaml](../../infra/kubernetes/charts/ai-agents-platform/values.yaml).

## PostgreSQL

| Field | Value |
| --- | --- |
| Dev/Test strategy | `generatedPVC` (RWO) |
| Staging/Production strategy | `externalService` (component disabled) |
| Mount path | `/var/lib/postgresql/data` (official image PGDATA) |
| Requested size | `10Gi` (placeholder) |
| StorageClass | `""` (cluster default; no real name) |
| Generated PVC | dev/test only |
| Production PVC | none |

The in-cluster Postgres Deployment is **not** converted to a production-grade
StatefulSet in this stage. StatefulSet / operator / HA is a **future runtime
engineering decision** and recorded as such — not implemented or implied here.

## Redis

| Field | Value |
| --- | --- |
| Dev/Test strategy | `generatedPVC` (RWO) |
| Staging/Production strategy | `externalService` (component disabled) |
| Persistence | configurable; `persistenceEnabled=true` in dev/test |
| Mount path | `/data` |
| Requested size | `2Gi` (placeholder) |
| Production PVC | none |

The RWO PVC backs `/data`; Redis keeps `readOnlyRootFilesystem=true` (the
storage layer owns `/data`, replacing the 51.2A ephemeral emptyDir when
persistence is enabled). AOF/RDB durability tuning and Redis HA (Sentinel /
cluster) are **not** configured here.

## Safety

* No real database/Redis credential in storage values (schema
  `additionalProperties: false`).
* No hostPath, no NFS, no real storage class, no `StorageClass`/`PersistentVolume`
  resource.
* Production keeps internal datastores disabled (existing fail-closed rules) and
  storage strategy `externalService`.
