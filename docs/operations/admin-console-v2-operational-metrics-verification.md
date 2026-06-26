# Admin Console v2 — Operational Metrics Verification (Step 58)

## Combined
```bash
PYTHON=.venv/bin/python ORCHESTRATOR_URL=http://localhost:8000 \
  ./scripts/verify_admin_console_v2_operational_metrics_baseline.sh
```
Final marker: `ADMIN_CONSOLE_V2_OPERATIONAL_METRICS_BASELINE_VERIFY: PASS | BLOCKED | FAIL`.
It generates the metrics snapshot, runs the Step 52–57 baselines (via the deduped Step 57
combined) + the tenant strategy-note verifier, the 6 metrics verifiers, the targeted
tests, and the safety posture check; classifies any FAIL → FAIL; else any BLOCKED →
BLOCKED; else PASS.

## Verifiers + markers
model `OPERATIONAL_METRICS_MODEL_VERIFY`, sources `OPERATIONAL_METRICS_SOURCES_VERIFY`,
snapshot `OPERATIONAL_METRICS_SNAPSHOT_VERIFY`, API `OPERATIONAL_METRICS_API_VERIFY`,
Admin Console `ADMIN_CONSOLE_V2_OPERATIONAL_METRICS_VERIFY`, safety fields
`OPERATIONAL_METRICS_SAFETY_FIELDS_VERIFY`.

## Read-only endpoints
`GET /operations/metrics/*` (14, GET-only). No generate / refresh / sync / deploy / PR /
external-send endpoint.
