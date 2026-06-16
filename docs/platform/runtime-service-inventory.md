# Runtime Service Inventory (Step 51.1 / Stage 53A)

Evidence-backed inventory of the platform's actual runtime, produced *before*
any Helm chart was written. It is the source for the Kubernetes component
catalog and the multi-environment Helm foundation.

## Inventory method

1. Parsed `infra/docker-compose/docker-compose.yml` (project `aiagents-test`) —
   the authoritative runtime definition.
2. Cross-checked each service against `apps/*`, `agents/*`, `shared/sdk/*`
   source: confirmed every first-party service is a FastAPI app exposing
   `/health` (compose healthcheck) and `/metrics`
   (`shared.sdk.observability.metrics.install_metrics_endpoint`, present in all
   20 build services' `main.py`).
3. Recorded names + classification only — **no environment-variable values**.
   `secretReferences` list variable *names* only.

Machine-readable outputs:

- [`infra/kubernetes/runtime-inventory.yaml`](../../infra/kubernetes/runtime-inventory.yaml)
- [`infra/kubernetes/runtime-dependency-matrix.yaml`](../../infra/kubernetes/runtime-dependency-matrix.yaml)

## Service classification

27 Compose services + 3 non-service one-shot jobs.

| Classification | Count | Services |
| --- | --: | --- |
| Core application | 1 | orchestrator |
| Governance | 3 | policy-engine, approval-engine, audit-service |
| Communication | 3 | communication-gateway, github-automation, discord-gateway |
| Worker | 3 | audit-worker, notification-worker, retry-scheduler |
| Agent | 10 | intake, requirement, development, qa, devops, project-planner, design-review, workspace-operator, mini-delivery-pilot, delivery-package |
| Infrastructure | 3 | postgres, redis, vault (test-only) |
| Observability | 4 | tempo, prometheus, alertmanager, grafana |

## Long-running services (Kubernetes Deployment targets)

The 20 first-party FastAPI services (core + governance + communication + worker
+ agent) are the Deployment targets — all `longRunning: true`, all expose
`/health` + `/metrics`. Ports 8000–8020 (see inventory).

## One-shot jobs (NOT Deployments)

| Job | Evidence | Target |
| --- | --- | --- |
| database-migrations | `migrations/*.sql` via `psql`; no compose service | Migration **Job** — deferred to Step 51.2 |
| backup-dr-run | `shared/sdk/backup_dr/cli.py` + `run_encrypted_backup.sh`; host-run | Backup **CronJob** — deferred to Step 51.2 |
| verification-scripts | `scripts/verify_*.sh`; CI/operator-run | Not a workload |

These are recorded explicitly so they are not lost, and are **excluded** from
the component catalog so they are never accidentally turned into Deployments.

## Test-only services

- **vault** runs `server -dev` (in-memory, unsealed). Flagged `testOnly: true`,
  enabled only for dev/test, and forbidden for staging/production by the chart's
  fail-closed validation.

## Dependency evidence

Every edge in the dependency matrix carries `evidence` — either
`compose_depends_on` and/or an explicit `env:<VAR>` service URL. Edges are not
inferred from name similarity. `required: false` marks best-effort edges
(OTLP trace export, optional callbacks). `unknownDependencies` is declared and
empty — nothing was silently dropped.

**Step 51.2B revalidation:** the matrix was rechecked against source and one
correction applied — OTLP→tempo was listed for only 4 of 20 services, so the 16
missing edges were added (total **75** edges: 49 internal policy-generating + 26
observability-deferred). See
[kubernetes-service-connectivity.md](kubernetes-service-connectivity.md).

## Deferred / external workloads

- **Observability** (Tempo/Prometheus/Alertmanager/Grafana): treated as an
  external/managed backend; not packaged in the Step 51.1 chart.
- **Postgres/Redis**: in-cluster only for dev/test convenience; staging and
  production expect external managed datastores.

## Unresolved inventory questions

- Staging/production external Postgres + Redis endpoints (managed services) —
  modelled as external secret references only; concrete endpoints unknown until
  Step 51.3 environment wiring.
- In-cluster vs external OTLP collector topology — deferred to Step 51.4.
