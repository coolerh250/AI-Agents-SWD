# Non-production Runtime Smoke Report (Step 55)

Schema: [`infra/kubernetes/nonproduction-runtime-smoke-report-schema.yaml`](../../infra/kubernetes/nonproduction-runtime-smoke-report-schema.yaml)
Output: `.runtime/kubernetes/nonproduction-runtime-smoke-report.json` (**never committed**).

A redacted report of a real smoke run: cluster context **hash only** (no kubeconfig/
token/cert), namespace, helm release/chart version, image refs, pod status, service
health, connectivity, NetworkPolicy, PVC, securityContext, batch-job results, an events
summary (counts only) and limitations. `productionReady` / `productionExecuted` always
false; no rendered manifest or secret is stored. When no smoke has run (blocked) the
report is absent and the live views degrade to `not_run`. Verified by
`verify_nonproduction_runtime_smoke_report.py`.
