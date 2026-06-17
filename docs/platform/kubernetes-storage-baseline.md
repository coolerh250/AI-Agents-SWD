# Kubernetes Storage Baseline (Step 51.2C1 / Stage 53D)

Evidence-backed storage ownership + a fail-closed, environment-safe PVC baseline.
**No cluster connection, no `kubectl`, no `helm install`.** Static manifests only.

## What this stage does

1. Inventories every filesystem / storage consumer in the real runtime
   ([storage-consumer-inventory.yaml](../../infra/kubernetes/storage-consumer-inventory.yaml)).
2. Normalises them into typed **stores** with owner / writers / readers /
   lifecycle / durability / per-environment strategy
   ([storage-ownership-catalog.yaml](../../infra/kubernetes/storage-ownership-catalog.yaml)).
3. Generates **RWO PVCs for in-cluster Postgres/Redis in dev/test only**
   ([templates/persistentvolumeclaims.yaml](../../infra/kubernetes/charts/ai-agents-platform/templates/persistentvolumeclaims.yaml)).
4. Mounts those claims in the Deployment template (PVC-backed paths replace the
   ephemeral emptyDir for that path; everything else stays emptyDir).
5. Enforces all of it with schema + `validate-values.yaml` + three verifiers.

## Storage strategies

| Strategy | Meaning | Where |
| --- | --- | --- |
| `ephemeralEmptyDir` | rebuildable scratch; discarded on restart | workspace, /tmp |
| `generatedPVC` | RWO PVC rendered by this chart | postgres/redis, **dev/test only** |
| `existingClaim` | pre-provisioned claim (NO real name here) | future staging/prod |
| `externalService` | external managed datastore | postgres/redis staging/prod |
| `externalObjectStorePlaceholder` | future object store; no endpoint, disabled | reports/artifacts |
| `unresolved` | blocker recorded; never becomes a fake PVC | report/audit-export sharing |

## Hard guarantees (fail-closed)

* `generatedPVC` renders **only** for dev/test; staging/production disable the
  datastore components *and* override the strategy to `externalService`.
* No `StorageClass` resource, no `PersistentVolume` resource, no hostPath, no
  NFS endpoint, no raw CSI config, no real storage-class name, no real claim
  name, no `ReadWriteOncePod`.
* Generated PVCs are **ReadWriteOnce** and single-writer. `ReadWriteMany` is an
  inert placeholder only (never an active generated claim).
* Forbidden mount paths (`/`, `/app`, `/etc`, `/bin`, `/sbin`, `/usr`, `/proc`,
  `/sys`, `/dev`, docker socket) are rejected at render time.
* Production placeholders keep `productionConfigured=false`; workspace/artifact
  persistence cannot be marked configured without an approved (non-sample)
  existing claim / external store — which does not exist this stage.

## Verify (no cluster)

```bash
python scripts/verify_kubernetes_storage_inventory.py    # KUBERNETES_STORAGE_INVENTORY_VERIFY: PASS
python scripts/verify_kubernetes_data_lifecycle.py       # KUBERNETES_DATA_LIFECYCLE_VERIFY: PASS
python scripts/verify_kubernetes_storage_manifest.py     # KUBERNETES_STORAGE_MANIFEST_VERIFY: PASS
./scripts/verify_kubernetes_storage_baseline.sh          # KUBERNETES_STORAGE_BASELINE_VERIFY: PASS
```

## Deferred (Step 51.2C2)

Migration Job, Backup CronJob, off-host target + encryption-key reference,
Restore Job, production scheduling. Backup storage stays **separate** from
active workspace and is recorded as deferred — never mixed in.

See also: [data lifecycle](kubernetes-data-lifecycle.md),
[workspace storage model](kubernetes-workspace-storage-model.md),
[datastore persistence](kubernetes-datastore-persistence.md).
