# Non-production Kubernetes Runtime Smoke — Verification (Step 55)

## Combined
```bash
PYTHON=.venv/bin/python ORCHESTRATOR_URL=http://localhost:8000 \
  ./scripts/verify_nonproduction_kubernetes_runtime_smoke.sh
```
Final marker: `NONPRODUCTION_KUBERNETES_RUNTIME_SMOKE_VERIFY: PASS |
BLOCKED_NO_SAFE_CLUSTER | FAIL`. Chains Step 51/52/53/54 (deduped) then the preflight
+ smoke + operations + Admin Console + safety verifiers + targeted tests, and
classifies: any FAIL → FAIL; else any BLOCKED → BLOCKED_NO_SAFE_CLUSTER; else PASS.

## Individual verifiers + markers
preflight `NONPROD_CLUSTER_PREFLIGHT_VERIFY`, namespace `NONPROD_NAMESPACE_PLAN_VERIFY`,
helm `NONPROD_HELM_RUNTIME_SMOKE_VERIFY`, pods `NONPROD_POD_STARTUP_SMOKE_VERIFY`,
services `NONPROD_SERVICE_HEALTH_SMOKE_VERIFY`, connectivity
`NONPROD_SERVICE_CONNECTIVITY_SMOKE_VERIFY`, network `NONPROD_NETWORKPOLICY_SMOKE_VERIFY`,
storage `NONPROD_STORAGE_SMOKE_VERIFY`, securitycontext
`NONPROD_SECURITYCONTEXT_SMOKE_VERIFY`, batch `NONPROD_BATCH_JOB_SMOKE_VERIFY`, report
`NONPROD_RUNTIME_SMOKE_REPORT_VERIFY`, operations
`NONPROD_RUNTIME_OPERATIONS_VISIBILITY_VERIFY`, admin console
`ADMIN_CONSOLE_NONPROD_RUNTIME_SMOKE_VERIFY`, safety
`NONPROD_RUNTIME_SAFETY_FIELDS_VERIFY`.

Read-only endpoints: `GET /operations/runtime/nonprod-smoke/*` (12, GET-only).

## Step 55.1 — real run on a safe kind cluster
Bootstrap + install + smoke + combined readiness (run from the repo root on the test host):
```bash
scripts/bootstrap_nonproduction_kind_cluster.sh
scripts/run_nonproduction_helm_smoke.sh --namespace aiagents-smoke-dev \
  --values infra/kubernetes/charts/ai-agents-platform/values-nonprod-smoke-local.yaml
scripts/run_nonproduction_runtime_smoke.py            # writes the live redacted report
scripts/verify_nonproduction_cluster_ready_for_smoke.sh
```
`run_nonproduction_runtime_smoke.py` (`NONPROD_RUNTIME_SMOKE_RUN`) performs real
`kubectl` checks + an in-cluster connectivity probe and writes
`.runtime/kubernetes/nonproduction-runtime-smoke-report.json` (gitignored, never
committed). The cluster-dependent verifiers consume that report — PASS reflects the
real cluster; an absent report is BLOCKED, never a faked PASS. New Step 55.1 markers:
`NONPROD_KUBERNETES_TOOLING_VERIFY`, `KIND_NONPROD_CLUSTER_VERIFY`,
`NONPROD_CLUSTER_BOOTSTRAP_VERIFY`, `NONPROD_CLUSTER_SAFETY_VERIFY`, and the combined
`NONPROD_CLUSTER_READY_FOR_RUNTIME_SMOKE_VERIFY`.
