# Runtime Baseline Verification (Step 51.4 / Stage 53G)

How to verify the read-only runtime baseline. **No cluster, no kubectl, no
argocd CLI, no Helm install/upgrade.**

## Markers

| Marker | Script |
| --- | --- |
| `RUNTIME_OPERATIONS_VISIBILITY_VERIFY` | `scripts/verify_runtime_operations_visibility.py` |
| `RUNTIME_SAFETY_FIELDS_VERIFY` | `scripts/verify_runtime_safety_fields.py` |
| `ADMIN_CONSOLE_RUNTIME_BASELINE_VERIFY` | `scripts/verify_admin_console_runtime_baseline.py` |
| `KUBERNETES_HELM_ARGOCD_BASELINE_VERIFY` | `scripts/verify_kubernetes_helm_argocd_baseline.sh` (combined Step 51) |

The runtime visibility / safety / admin verifiers hit the **live** orchestrator
(`ORCHESTRATOR_URL`, default `http://localhost:8000`); bring the controlled test
stack up first. The combined script chains the entire 51.1 → 51.3 baseline.

## Run

```bash
./scripts/verify_kubernetes_helm_argocd_baseline.sh      # Step 51 overall
python scripts/verify_runtime_operations_visibility.py
python scripts/verify_runtime_safety_fields.py
python scripts/verify_admin_console_runtime_baseline.py
```

## What they assert

* The 12 `/operations/runtime/*` endpoints are GET-only and 200; no
  deploy/sync/apply/install endpoint exists; no secret leak.
* `/operations/safety` carries the runtime fields with a non-production posture
  (`kubernetes_cluster_connected=false`, `argocd_auto_sync_enabled=false`,
  `runtime_production_ready=false`, `runtime_validated_not_deployed=true`,
  per-area `*_status=passed`, `production_executed_true_count=0`).
* The Admin Console Runtime Baseline view exists, is report-API backed, and has
  no deploy/sync/apply control, no credential input, no mutation client method.
* The committed `runtime-baseline-summary.yaml` matches a fresh collection
  (anti-drift) and contains no secret / rendered manifest.

## Full regression

`./scripts/run_full_regression.sh --full --json-report` should report
`PASS` or `PASS_WITH_NON_PRODUCTION_LIMITATIONS`. The
[non-production limitations](kubernetes-non-production-limitations.md) are
allowed; security/audit/tamper/production failures are not.
