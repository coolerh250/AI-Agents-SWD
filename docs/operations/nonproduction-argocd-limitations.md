# Non-production ArgoCD manual sync — limitations (Step 56)

Step 56 is a **real non-production ArgoCD manual sync** on a local kind cluster. It
is **NOT** production GitOps / production ArgoCD / auto-sync / production-deployment
ready.

## What is real
- A genuine ArgoCD install in `argocd-nonprod` (ClusterIP only) and a real **manual**
  sync of the `aiagents-smoke` Application into `aiagents-smoke-dev` → `Synced` +
  `Healthy`, deploying the scoped control-plane subset.

## Limitations (honest)
- **Manual only** — auto-sync, prune, and self-heal are disabled by design. This is
  not a continuous GitOps workflow.
- **Scope** — the synced app is the Step 55 host-capacity-scoped subset (orchestrator,
  policy-engine, approval-engine, audit-service, postgres, redis), not the full
  platform.
- **Local kind / kindnet** — NetworkPolicies are applied but kindnet does not enforce
  them (inherited from Step 55). The ArgoCD server is not exposed (no ingress / LB).
- **ArgoCD controller RBAC** is cluster-scoped (inherent to ArgoCD); the **AppProject**
  confines the app to `aiagents-smoke-dev` with no cluster-scoped resources.
- **Single environment** — no multi-environment promotion, no production destination,
  no release gate.
- **Public repo, read-only** — no repo credential; this does not exercise private-repo
  / production credential flows.

## Out of scope / next
- **Step 57** — Multi-project Delivery Capability & Work-item Dispatch.
- Production ArgoCD / GitOps / auto-sync / promotion remain future work behind an
  explicit operator decision and a production-readiness review.

No production cluster / namespace / ArgoCD sync / GitHub write / image push / registry
login / public ingress / LoadBalancer / production action;
`production_executed_true_count=0`. **Claude Code does not decide production
readiness.**
