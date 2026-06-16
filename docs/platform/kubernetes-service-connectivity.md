# Kubernetes Service Connectivity (Step 51.2B / Stage 53C)

How the platform's internal service-to-service connectivity is modelled and
verified for the NetworkPolicy baseline.

## Corrected dependency edge count

The dependency matrix was revalidated against source. One correction:
OTLP→tempo was listed for only 4 of 20 services, yet **all 20** build services
export OTLP (`env:OTEL_EXPORTER_OTLP_ENDPOINT`). The 16 missing edges were added
for completeness.

| Category | Count |
| --- | --: |
| Total edges | 75 |
| Internal policy-generating | 49 |
| Observability-deferred (20 OTLP export + 6 backend) | 26 |
| Duplicate edges | 0 |
| Unknown components | 0 |

Internal breakdown: 12 first-party HTTP edges, 18 Postgres edges, 19 Redis edges.

## Evidence types

Every edge carries `evidence`: `compose_depends_on` and/or `env:<VAR>` (an
explicit service URL). No edge is inferred from name similarity. Source:
[`runtime-dependency-matrix.yaml`](../../infra/kubernetes/runtime-dependency-matrix.yaml);
canonical model: [`network-connectivity-catalog.yaml`](../../infra/kubernetes/network-connectivity-catalog.yaml).

## Ingress / egress pairing

Each required edge `S → T:port` produces both an egress allow on `S` and an
ingress allow on `T`. `verify_kubernetes_service_connectivity.py` computes a
coverage summary and requires `missing_edges=0` and `unexpected_edges=0` in
every environment.

## Postgres / Redis access matrix

In-cluster Postgres (18 sources) and Redis (19 sources) are dev/test only and
ClusterIP; ingress is restricted to exactly the cataloged sources on 5432 / 6379
respectively. Neither is ever exposed externally. In staging/production the
internal datastores are disabled (external managed services, deferred).

## Optional / deferred dependencies

- Optional internal edges (`required: false`, e.g. `comm-gw → github-automation`,
  `devops-agent → audit-service`) still get allow rules because the target is an
  always-enabled first-party component.
- OTLP export and Prometheus scrape are observability-deferred — no policy is
  generated (see the external-egress model).

## Coverage verification

`KUBERNETES_NETWORK_TOPOLOGY_VERIFY` (catalog ⟷ matrix ⟷ values consistency),
`KUBERNETES_NETWORK_POLICY_VERIFY` (rendered policy safety), and
`KUBERNETES_SERVICE_CONNECTIVITY_VERIFY` (edge coverage) must all PASS. Runtime
reachability is not cluster-tested in this stage.
