# Kubernetes NetworkPolicy Baseline (Step 51.2B / Stage 53C)

A default-deny NetworkPolicy baseline generated from the evidence-backed
connectivity catalog. Static manifest baseline only — **no cluster connection,
no kubectl, no helm install**. CNI enforcement of NetworkPolicy is a cluster
concern verified later.

## Default-deny model

Every environment renders two namespace-wide policies with an empty
`podSelector` (the **only** place an empty selector is allowed):

- `<release>-default-deny-ingress` (policyTypes: Ingress)
- `<release>-default-deny-egress` (policyTypes: Egress)

All other allows are additive and explicitly scoped. `networkPolicy.enabled`,
`defaultDenyIngress`, and `defaultDenyEgress` are `true` in dev/test/staging/
production; `validate-values.yaml` fails the render if any is disabled.

## DNS model

A single `<release>-allow-dns` egress policy selects all release pods
(`app.kubernetes.io/part-of` + `app.kubernetes.io/instance`) and allows egress
to `kube-system` / `k8s-app: kube-dns` on **UDP 53 and TCP 53 only**. Selectors
are values-driven (CoreDNS defaults) so a cluster with different DNS labels can
override them; there is no unrestricted fallback.

## Label contract

Policies and workloads share a stable contract: `app.kubernetes.io/name`,
`app.kubernetes.io/instance` (Helm release), `app.kubernetes.io/part-of`,
`app.kubernetes.io/component`, `ai-agents-swd/environment`. Policy source/target
selectors always pin `app.kubernetes.io/instance` so they only match the same
release.

## Policy aggregation

Internal edges are aggregated for readability but remain traceable:

- **per target**: one `<release>-ingress-<target>` policy listing every allowed
  source podSelector + the target port;
- **per source**: one `<release>-egress-<source>` policy with one egress rule
  per target (podSelector + port).

The connectivity coverage verifier maps each canonical edge back to both a
matching egress and ingress rule.

## No unrestricted selectors / no external egress

- Empty `podSelector` only on the two default-deny policies.
- No empty `namespaceSelector` allow rules.
- No `0.0.0.0/0` / `::/0`, no IPBlock egress (the template never renders one).
- No NodePort / LoadBalancer / Ingress resource; no hostNetwork / hostPort.
- External egress is disabled; see
  [kubernetes-external-egress-model.md](kubernetes-external-egress-model.md).

## No cluster validation caveat

Policies are validated statically (`verify_kubernetes_network_policy.py` +
`verify_kubernetes_service_connectivity.py`) against rendered manifests produced
by a pinned `alpine/helm:3.16.3` container. Actual CNI enforcement, DNS label
portability, and runtime reachability require a cluster smoke test (deferred).
