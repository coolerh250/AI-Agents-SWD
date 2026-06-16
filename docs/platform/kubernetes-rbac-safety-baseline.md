# Kubernetes RBAC Safety Baseline (Step 51.2A / Stage 53B)

Least-privilege == **no-privilege** at this baseline. The chart grants zero
Kubernetes API access: no Role, RoleBinding, ClusterRole or ClusterRoleBinding
is created. Recorded in
[`rbac-safety-catalog.yaml`](../../infra/kubernetes/rbac-safety-catalog.yaml)
and enforced by `verify_kubernetes_rbac_safety.py`.

## ServiceAccount model

- One dedicated ServiceAccount per enabled component (`serviceAccount.create`).
- `automountServiceAccountToken: false` on both the ServiceAccount **and** the
  pod spec — no token is mounted into any workload.
- No component requires the Kubernetes API (`kubernetesApiRequired: false` for
  all 23), so no token is needed.

## No Role / ClusterRole

This stage creates **0** Role / RoleBinding / ClusterRole / ClusterRoleBinding
(catalog counters are all 0). The verifier fails if any RBAC object appears in
the rendered manifests.

## Prohibited permissions

Asserted absent (catalog flags all `false`):

- no `cluster-admin`, no wildcard apiGroup / resource / verb;
- no `secrets` get/list/watch;
- no `deployments`/`statefulsets`/`daemonsets` create/update/patch/delete;
- no `jobs`/`cronjobs` create;
- no `pods/exec`, no `pods/portforward`.

Agents get no Secret-read, no Deployment-mutation, no Job-creation. The
orchestrator gets no Kubernetes deploy permission. The Step 50
operator/platform_admin roles map to **no** Kubernetes permission.

## Future deployment-agent policy boundary

Any future Kubernetes deploy capability must be **namespaced, least-privilege,
and gated by the existing policy / approval / audit plane** (Step 50) — never
cluster-admin, never wildcard, never direct Secret access. This is recorded as a
boundary only; nothing is created for it in Step 51.2A.

## Verification

`verify_kubernetes_rbac_safety.py` scans the rendered manifests (no RBAC kinds,
automount false everywhere) and asserts the catalog (flags false, counters 0,
all components no-API, no unresolved API needs). No cluster connection.
