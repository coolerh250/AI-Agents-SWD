# Cluster ready for runtime smoke (Step 55.1)

The combined end-to-end check that the non-production cluster is bootstrapped,
safe, and that the Step 55 runtime smoke passes for real against it.

- Combined: [`scripts/verify_nonproduction_cluster_ready_for_smoke.sh`](../../scripts/verify_nonproduction_cluster_ready_for_smoke.sh)
  → `NONPROD_CLUSTER_READY_FOR_RUNTIME_SMOKE_VERIFY`

## Chain

1. `NONPROD_KUBERNETES_TOOLING_VERIFY` — kubectl/helm/kind present, no registry login/push.
2. `KIND_NONPROD_CLUSTER_VERIFY` — local-only kind cluster, safe context.
3. `NONPROD_RUNTIME_SMOKE_RUN` — (re)generate the live runtime smoke report.
4. `NONPROD_CLUSTER_BOOTSTRAP_VERIFY` — bootstrap plan valid + release deployed.
5. `NONPROD_CLUSTER_SAFETY_VERIFY` — no LoadBalancer/NodePort/Ingress; invariants false.
6. `NONPROD_NAMESPACE_PLAN_VERIFY` — namespace plan safe.
7. `NONPRODUCTION_KUBERNETES_RUNTIME_SMOKE_VERIFY` — Step 55 combined smoke (consumes the report).
8. Safety posture: `nonprod_kubernetes_smoke_enabled=true`, not production ready, no
   deploy, no ArgoCD sync, `production_executed_true_count=0`.

## Result classification

- Any sub-check FAIL → `NONPROD_CLUSTER_READY_FOR_RUNTIME_SMOKE_VERIFY: FAIL`.
- Else any BLOCKED → `BLOCKED` (cluster/tools/deploy missing).
- Else `PASS` (and Step 55 smoke is a real PASS).

## Run

```bash
# from the repo root on the test host, with the cluster bootstrapped + release installed
scripts/verify_nonproduction_cluster_ready_for_smoke.sh
```

## Relationship to Step 55 / Step 56

When this verifier and the Step 55 smoke are `PASS` on a real cluster, the Step 55
`PASS_WITH_GAPS` is lifted **for the deployed scope**. Step 56 (real ArgoCD
non-production manual sync) remains out of scope and must not begin from automation —
it requires an explicit operator decision.
