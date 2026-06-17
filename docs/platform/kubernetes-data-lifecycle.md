# Kubernetes Data Lifecycle (Step 51.2C1 / Stage 53D)

Every storage path is classified along five axes. Source of truth:
[storage-ownership-catalog.yaml](../../infra/kubernetes/storage-ownership-catalog.yaml).

## Classification axes

* **Lifecycle**: request_scoped · workflow_scoped · project_scoped ·
  release_scoped · audit_retained · infrastructure_state
* **Durability**: ephemeral · restart_durable · deployment_durable ·
  externally_managed
* **Rebuildability**: fully_rebuildable · partially_rebuildable · not_rebuildable
* **Confidentiality**: public · internal · confidential · secret_prohibited
* **Integrity**: low · standard · high · audit_critical

## Stores

| Store | Lifecycle | Durability | Rebuildable | Integrity | Strategy (dev/test → staging/prod) |
| --- | --- | --- | --- | --- | --- |
| postgres-data | infrastructure_state | deployment_durable | not_rebuildable | audit_critical | generatedPVC → externalService |
| redis-data | infrastructure_state | restart_durable | partially | standard | generatedPVC → externalService |
| workspace-scratch | workflow_scoped | ephemeral | fully | standard | ephemeralEmptyDir (all envs) |
| runtime-reports | release_scoped | externally_managed | fully | standard | unresolved |
| dr-reports | audit_retained | externally_managed | partially | high | unresolved |
| audit-evidence-export | audit_retained | externally_managed | not_rebuildable | audit_critical | unresolved |
| delivery-artifacts | release_scoped | deployment_durable (PostgreSQL) | partially | standard | externalService |

## Enforced rules

* Infrastructure state is **never** ephemeral; database state is **never**
  fully_rebuildable.
* Audit-retained / audit-evidence stores keep **high / audit_critical**
  integrity (canonical audit records remain in **PostgreSQL**, not a generic
  artifact store).
* Workspace declares explicit create/destroy boundaries, `durableAcrossRestart:
  false`, and `persistenceSolved: false` — **no fake durability**.
* Delivery evidence is separate from cache/Redis; backup is separate from active
  workspace and deferred to Step 51.2C2.
* `unresolved` stores record a blocker + a future target and stay
  `productionConfigured: false` (fail closed) — they never become a fake PVC.

Verifier: `scripts/verify_kubernetes_data_lifecycle.py`
(`KUBERNETES_DATA_LIFECYCLE_VERIFY: PASS`).
