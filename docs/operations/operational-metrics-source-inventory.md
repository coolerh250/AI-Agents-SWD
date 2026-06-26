# Operational Metrics — Source Inventory (Step 58)

Every metrics source is **read-only** and allowlisted. Runtime reports are never
committed; when absent the metric is shown **missing/stale**, never clean.

- Inventory: [`infra/operations/operational-metrics-source-inventory.yaml`](../../infra/operations/operational-metrics-source-inventory.yaml)
- Verifier: `scripts/verify_operational_metrics_sources.py` → `OPERATIONAL_METRICS_SOURCES_VERIFY`

## Sources
- **DB tables (live):** projects, project_work_items, work_item_dispatches,
  work_item_events, project_delivery_states, project_delivery_packages,
  agent_executions, workflow_states, approval_requests, audit_logs.
- **Runtime reports (not committed; stale-if-absent):**
  `.runtime/kubernetes/nonproduction-runtime-smoke-report.json`,
  `.runtime/gitops/nonproduction-argocd-manual-sync-report.json`.
- **Committed summaries:** `infra/security/*`, `infra/gitops/...manual-sync-summary.yaml`.
- **In-process:** `/operations/safety` posture (via the SDK safety functions).

Each source declares type / freshness / availability / redaction / `secretExposureRisk:
false`. Rules: missing runtime → stale, never clean; runtime reports never committed;
no arbitrary path (allowlist only); no secret exposure.
