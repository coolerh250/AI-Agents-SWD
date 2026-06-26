# Non-production Kubernetes Runtime Smoke — Limitations (Step 55 / 55.1)

**Step 55.1 closed the cluster gap.** A safe, local-only kind cluster
(`kind-aiagents-smoke`) was bootstrapped on the test host (after a host RAM
upgrade), the scoped chart was really installed, and the Step 55 runtime smoke now
returns a **real PASS** for the deployed scope — it is no longer
`BLOCKED_NO_SAFE_CLUSTER`. See
[nonproduction-cluster-bootstrap-plan.md](nonproduction-cluster-bootstrap-plan.md)
and [nonproduction-cluster-ready-for-smoke.md](nonproduction-cluster-ready-for-smoke.md).

## What passed (real, against the live cluster)
Pod startup (6/6 Ready), service health, in-cluster connectivity
(orchestrator → policy-engine / approval-engine / audit-service `/health` = 200),
NetworkPolicy presence, PVC binding (postgres + redis), securityContext
(runAsNonRoot / drop-ALL / no-privesc on every pod), and the controlled migration
Job completing as a no-op. Results come from a redacted runtime report consumed by
the verifiers (no faked PASS).

## Remaining limitations (honest)
- **Scope** — the smoke deploys a control-plane subset (orchestrator, policy-engine,
  approval-engine, audit-service, postgres, redis) sized for the non-production host;
  the other platform components are not deployed in this smoke.
- **NetworkPolicy enforcement** — kindnet renders/applies the default-deny + per-edge
  policies but does **not enforce** them; the report records
  `enforcementObserved: false`. Validating enforcement needs a policy-enforcing CNI
  (Calico/Cilium).
- **DB schema** — chart migration execution is fail-closed, so no schema is applied;
  services that need tables run with liveness-only `/health`.
- **postgres** — the official image needs `PGDATA` at a PVC sub-directory (smoke
  values override) to initdb under the restricted securityContext.
- **Host capacity** — no swap; a full 23-component install remains memory-risky, so
  the smoke stays scoped.
- **Dockerfile USER** — images set no `USER`; the pod securityContext forces
  `runAsUser` (non-root) and it works, but the Dockerfiles should still add a `USER`
  (Step 54.3 gap).

## Out of scope / required next
- **Step 56** — real ArgoCD non-production manual sync. Must not begin from
  automation; requires an explicit operator decision.

No production deploy / namespace / ArgoCD sync / GitHub write / image push / registry
login / production action; `production_executed_true_count=0`. Claude Code does not
decide Production readiness.
