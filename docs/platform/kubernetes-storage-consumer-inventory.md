# Kubernetes Storage Consumer Inventory (Step 51.2C1 / Stage 53D)

Evidence-backed inventory of every filesystem / storage consumer in the actual
runtime, produced *before* any PVC template was written. Machine-readable source:
[storage-consumer-inventory.yaml](../../infra/kubernetes/storage-consumer-inventory.yaml).

## Method

Parsed `infra/docker-compose/docker-compose.yml` (named volumes + bind mounts)
and cross-checked `runtime-inventory.yaml`, `workload-security-inventory.yaml`,
and `apps/* agents/* shared/sdk/* scripts/` disk-write behaviour. Only field
*names* / paths are recorded — never any value or credential.

## Consumers by category

| Category | Consumer(s) | Path | Strategy |
| --- | --- | --- | --- |
| database | postgres | `/var/lib/postgresql/data` | generatedPVC (dev/test) → externalService |
| redis | redis | `/data` | generatedPVC (dev/test) → externalService |
| workspace | development / qa / workspace-operator / mini-delivery-pilot agents | `/tmp/aiagents-workspaces` | ephemeralEmptyDir (per-pod) |
| scratch | all first-party services | `/tmp` | ephemeralEmptyDir |
| reports | orchestrator (read-only) | `/app/source/regression-reports`, `/app/source/dr-reports` | unresolved |
| audit_evidence | orchestrator (read-only) | `/app/source/audit-forensics` | unresolved (canonical records in PostgreSQL) |
| delivery_artifacts | delivery-package-agent | PostgreSQL | externalService |
| static_asset | admin-console | container image layer | imageContained |
| backup | backup-dr-run | runtime dir + off-host | unresolved (**deferred to 51.2C2**) |

## Key findings

* Only `postgres-data` is a durable named compose volume. Redis is ephemeral in
  compose today (no named volume).
* Workspace is **per-pod**, not a shared filesystem — no RWX required (the
  mini-delivery pilot runs workspace execution in-process).
* Report/evidence directories are written by **host one-shot scripts** and
  mounted read-only into the orchestrator; their in-cluster distribution medium
  is genuinely `unresolved` (writers are deferred jobs), recorded with blockers.
* Admin Console static assets are baked into the image — no PVC.
* Backup artifacts are separate from active workspace and deferred to Step
  51.2C2.

See [storage baseline](kubernetes-storage-baseline.md) and
[data lifecycle](kubernetes-data-lifecycle.md).
