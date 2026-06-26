# Operational Metrics — Read-only API (Step 58)

- Module: `apps/orchestrator/src/operational_metrics_api.py`
- Verifier: `scripts/verify_operational_metrics_api.py` → `OPERATIONAL_METRICS_API_VERIFY`

14 GET-only endpoints under `/operations/metrics`:
`overview`, `delivery`, `work-items`, `dispatch`, `agents`, `workflows`, `runtime`,
`gitops`, `security`, `approval`, `audit`, `safety`, `freshness`, `snapshot`.

Invariants:
- **GET-only** — no generate / refresh / sync / deploy / PR / external-send endpoint, no
  mutation verb, no arbitrary path input.
- The API computes a live, redacted aggregation (short in-process cache): DB-backed domains
  (delivery / work items / dispatch / agents / workflows / approval / audit) and the
  committed-summary security domain are live; the runtime / GitOps domains read the Step 55/56
  `.runtime` reports, which are **not** present in the orchestrator container, so they
  **degrade to unavailable** in-container (the host-run snapshot generator reads them for the
  snapshot verifier). The orchestrator never mutates a cluster, runs kubectl/helm, or calls
  external services.
- Responses are redacted (no secret / token / kubeconfig / chain-of-thought) and show
  stale / unavailable explicitly. Every response carries `production_ready: false`.
