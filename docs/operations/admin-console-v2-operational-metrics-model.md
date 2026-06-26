# Admin Console v2 — Operational Metrics Model (Step 58)

Operational metrics aggregate existing platform state into **read-only** visibility.
**Not** production readiness, **not** an SLA/SLO guarantee, **not** multi-tenant.

- Model: [`infra/operations/operational-metrics-model.yaml`](../../infra/operations/operational-metrics-model.yaml)
- Verifier: `scripts/verify_operational_metrics_model.py` → `OPERATIONAL_METRICS_MODEL_VERIFY`

## Domains (11)
delivery · work_items · dispatch · agents · workflows · runtime · gitops · security ·
approval · audit · safety.

## Metric types
count · rate · duration · status · freshness · readiness · blocker.

## Rules (enforced)
- Metrics are **visibility only** — never a production approval / readiness signal.
- Metrics may show **stale / unavailable**; **missing data is never hidden** as clean.
- No secret / token / kubeconfig / chain-of-thought output.
- Does not claim production readiness or SLA guarantee.
- Delivery completed ≠ production approved; security baseline PASS ≠ all-risks-remediated.
- `productionReady: false` everywhere.
