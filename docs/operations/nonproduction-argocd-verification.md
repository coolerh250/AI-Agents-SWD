# Non-production ArgoCD manual sync — verification (Step 56)

## Combined
```bash
PYTHON=.venv/bin/python ORCHESTRATOR_URL=http://localhost:8000 \
  ./scripts/verify_nonproduction_argocd_manual_sync_baseline.sh
```
Final marker: `NONPRODUCTION_ARGOCD_MANUAL_SYNC_BASELINE_VERIFY: PASS | BLOCKED | FAIL`.
It regenerates the live Step 55 + Step 56 reports, runs the Step 51/52/53/54/55
baselines (via the deduped Step 55 combined), the 9 ArgoCD verifiers, the targeted
tests, and the safety posture check; classifies any FAIL → FAIL; else any BLOCKED →
BLOCKED; else PASS.

## Individual verifiers + markers
preflight `NONPROD_ARGOCD_PREFLIGHT_VERIFY`, install boundary
`NONPROD_ARGOCD_INSTALL_BOUNDARY_VERIFY`, project policy
`NONPROD_ARGOCD_PROJECT_POLICY_VERIFY`, application `NONPROD_ARGOCD_APPLICATION_VERIFY`,
manual sync `NONPROD_ARGOCD_MANUAL_SYNC_VERIFY`, safety `NONPROD_ARGOCD_SAFETY_VERIFY`,
operations visibility `NONPROD_ARGOCD_OPERATIONS_VISIBILITY_VERIFY`, Admin Console
`ADMIN_CONSOLE_NONPROD_ARGOCD_VERIFY`, safety fields `NONPROD_ARGOCD_SAFETY_FIELDS_VERIFY`.

## Read-only endpoints
`GET /operations/gitops/nonprod-argocd/{preflight,install,project,application,sync,safety,report,readiness}`
(8, GET-only). No sync / install / delete / rollback / promote endpoint.

## One-shot run (bootstrap + sync + verify)
```bash
scripts/run_nonproduction_argocd_manual_sync.sh
scripts/verify_nonproduction_argocd_manual_sync_baseline.sh
```
