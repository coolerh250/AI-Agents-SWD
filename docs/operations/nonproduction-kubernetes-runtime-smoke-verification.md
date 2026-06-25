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
