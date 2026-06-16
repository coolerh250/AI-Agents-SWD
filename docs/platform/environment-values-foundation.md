# Environment Values Foundation (Step 51.1 / Stage 53A)

Four environment values files layer over the base
[`values.yaml`](../../infra/kubernetes/charts/ai-agents-platform/values.yaml).
None is deployable in Step 51.1 — `global.realDeployEnabled` is false in all of
them and no chart connects to a cluster.

| Environment | production | realDeploy | testAuth | operatorActions | internal PG/Redis | Vault dev |
| --- | :--: | :--: | :--: | :--: | :--: | :--: |
| dev | false | false | true | true (controlled) | true | true (test-only) |
| test | false | false | true | true (controlled) | true | true (test-only) |
| staging placeholder | false | false | false | false | false | false |
| production placeholder | true | false | false | false | false | false |

## dev

Local development convenience: in-cluster Postgres/Redis + test-only Vault
enabled, Admin Console + test-local auth on, operator actions controlled-only,
all external integrations off. No secrets.

## test

Mirrors the current controlled test baseline on 10.0.1.31: same as dev, plus an
explicit `aiagents-runtime-secrets` reference. GitHub write / PR / deploy / real
LLM / external delivery / production execution all off.

## staging placeholder

Not directly deployable. Internal datastores off (staging expects external
managed Postgres/Redis), test auth + operator actions off, real integrations
off. External secret referenced by name only; image tags remain placeholders.

## production placeholder

Fail-closed and **not deployable**. `production=true` but
`realDeployEnabled=false`. No real hostnames, no credentials — only a
clearly-marked external secret name. Every risky capability is off:
test/production auth, OIDC, operator actions, GitHub write, deployment, real
LLM, external delivery, production backup schedule, in-cluster
Postgres/Redis/Vault.

## Fail-closed rules

`templates/validate-values.yaml` aborts the render (helm lint / template) when:

- environment ∉ {dev,test,staging,production};
- production environment without `production=true`, or non-production with
  `production=true`;
- `realDeployEnabled=true` (anywhere) or `secrets.create=true`;
- production enabling test auth / production auth / OIDC / operator actions /
  GitHub write / deployment / external delivery / production backup schedule /
  in-cluster Postgres / Redis / Vault / any test-only component;
- any component using image tag `latest`.

The production placeholder satisfies every rule, so it renders safely while
staying non-deployable. A deliberately bad production override (e.g.
`operatorActionsEnabled=true`) is rejected at render time — exercised by
`verify_helm_foundation.sh`.

## No real secrets / no deploy / no cluster connection

These values files contain no credentials, trigger no deployment, and the
render pipeline (`verify_helm_foundation.sh`) only runs `helm lint` and
`helm template` into a gitignored `.runtime/kubernetes-rendered/` directory —
never `helm install`, `helm upgrade`, `kubectl`, or any cluster connection.
