# Non-production kind cluster (Step 55.1)

A throwaway, **local-only** single-node kind cluster used solely to run the Step 55
runtime smoke.

- Config: [`infra/kubernetes/kind/nonproduction-kind-cluster.yaml`](../../infra/kubernetes/kind/nonproduction-kind-cluster.yaml)
- Verifier: `scripts/verify_kind_nonproduction_cluster.py` → `KIND_NONPROD_CLUSTER_VERIFY`

| Property | Value |
|----------|-------|
| Cluster name | `aiagents-smoke` |
| kubectl context | `kind-aiagents-smoke` (no prod substring) |
| Namespace | `aiagents-smoke-dev` |
| Node image | `kindest/node:v1.31.2` |
| CNI | kindnet (default) |

## Safety properties

- Local-only (runs in Docker on the test host); **no host port mappings, no public
  ingress, no LoadBalancer**.
- No production registry / secret / DB / Redis; no cloud credential.
- In-cluster checks use `kubectl exec` against ClusterIP services only.
- Fully deletable + recreatable; holds no durable state.

## Lifecycle

```bash
kind create cluster --config infra/kubernetes/kind/nonproduction-kind-cluster.yaml \
  --image kindest/node:v1.31.2 --wait 120s        # or: scripts/bootstrap_nonproduction_kind_cluster.sh
kubectl config current-context                     # -> kind-aiagents-smoke
kind delete cluster --name aiagents-smoke          # teardown
```

## Image handling

Images are built locally (the existing compose images) and loaded with
`kind load docker-image aiagents/<component>:smoke-local --name aiagents-smoke`.
`imagePullPolicy: IfNotPresent` means kind uses the loaded image and never pulls
from a registry. **No image is ever pushed.**

## Known CNI limitation

kindnet does **not** enforce `NetworkPolicy`. The default-deny + per-edge policies
are rendered and applied, but runtime egress is not blocked. The runtime smoke
report records this honestly (`enforcementObserved: false`); it is **not** claimed
as enforced. A CNI such as Calico/Cilium would be required to validate enforcement.

> ⚠️ **Host capacity:** the test host must have adequate free memory before
> creating the cluster. A kind control-plane plus the deployed pods on a host with
> little free RAM and no swap can exhaust memory and make the host unresponsive.
> Keep the smoke scoped (see the bootstrap plan) and watch `free -h`.
