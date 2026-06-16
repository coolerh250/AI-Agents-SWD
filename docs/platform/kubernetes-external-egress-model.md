# Kubernetes External Egress Model (Step 51.2B / Stage 53C)

Under the default-deny egress baseline, **all external egress is disabled**.
This document records the external dependencies, why none produces an egress
allow, and the native-NetworkPolicy limitations that shape a future controlled
egress design.

## External dependencies (all disabled)

Catalogued in
[`network-connectivity-catalog.yaml`](../../infra/kubernetes/network-connectivity-catalog.yaml)
under `externalDependencies`, every entry `enabled: false`,
`policyGenerated: false`:

- GitHub API (`GITHUB_DRY_RUN=true`)
- LLM providers
- Discord / Slack / Telegram
- Cloud APIs / cloud storage
- Pager / escalation
- External OIDC
- External managed Postgres / Redis
- External OTLP collector (observability deferred)

## All disabled — nothing rendered

- `networkPolicy.externalEgress.enabled: false`
- `networkPolicy.observability.prometheusScrape.enabled: false`
- `networkPolicy.observability.otlpExport.enabled: false`
- `externalDataServices.{postgres,redis}.enabled: false` with empty `cidrs`

The template renders **no** IPBlock / external egress rule. With
`global.realDeployEnabled=false` (every shipped values file), no external egress
policy is produced under any circumstances in this stage.

## Native NetworkPolicy FQDN limitation

Kubernetes NetworkPolicy cannot express egress to a generic FQDN (e.g.
`api.github.com`) — it only supports pod/namespace selectors and IP CIDR blocks.
Therefore we do **not** fabricate FQDN egress "policies". Controlled external
egress (when needed) will require a dedicated egress gateway or a CNI that
supports FQDN/DNS-aware policy — designed in a later stage, not here.

## No unrestricted CIDR

`0.0.0.0/0` and `::/0` are forbidden by the values schema
(`externalDataServices.*.cidrs` items `not enum`), by `validate-values.yaml`,
and by `verify_kubernetes_network_policy.py` (scans rendered IPBlocks).

## Future controlled egress (deferred)

When `realDeployEnabled=true` (a later stage), external managed Postgres/Redis
will require a **non-empty, non-unrestricted** CIDR per service; external API
egress will go through an egress gateway / FQDN-aware policy. None of this is
enabled in Step 51.2B.

## Production placeholder behaviour

The production placeholder keeps `networkPolicy.enabled=true`, default-deny on,
external egress off, ingress-controller off, observability off, and external
data services off — and remains non-deployable (`realDeployEnabled=false`).
`validate-values.yaml` fails the render if production tries to enable any of
these.
