# Operational Metrics — Snapshot (Step 58)

- Generator: `scripts/generate_operational_metrics_snapshot.py` → `OPERATIONAL_METRICS_SNAPSHOT_RUN`
- Output: `.runtime/operations/operational-metrics-snapshot.json` (gitignored, **never committed**)
- Verifier: `scripts/verify_operational_metrics_snapshot.py` → `OPERATIONAL_METRICS_SNAPSHOT_VERIFY`
- SDK: `shared/sdk/operations_metrics` (collectors / aggregator / redaction / freshness / safety)

The snapshot aggregates the read-only sources via the SDK aggregator. It always carries
`production_ready: false`, lists `limitations` and `blockers` (unavailable domains)
explicitly, and is redacted (no secret / token / kubeconfig / chain-of-thought shape).
A domain whose source is unavailable is recorded with `available: false` + a `reason` —
**missing data is never reported as clean**. The generator/aggregator never mutate,
sync, deploy, or call external services.

```bash
python scripts/generate_operational_metrics_snapshot.py   # writes the snapshot
python scripts/verify_operational_metrics_snapshot.py      # validates it
```
