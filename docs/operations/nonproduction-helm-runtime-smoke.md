# Non-production Helm Runtime Smoke (Step 55)

Runner: [`scripts/run_nonproduction_helm_smoke.sh`](../../scripts/run_nonproduction_helm_smoke.sh)
Values: [`values-nonprod-smoke.yaml`](../../infra/kubernetes/charts/ai-agents-platform/values-nonprod-smoke.yaml)

Renders + (optionally) installs the `ai-agents-platform` chart into a non-production
namespace. Guardrails: `--dry-run-only`, `--namespace`; refuses production/default/
`*prod*` namespaces + production/staging values; refuses a render containing Ingress /
LoadBalancer / ClusterRole / ClusterRoleBinding / CRD; never runs ArgoCD sync, pushes
an image, logs into a registry, or prints a kubeconfig/token/secret;
`production_executed` stays false. With no kubectl/helm/kubeconfig or an unsafe
context it emits `NONPROD_HELM_RUNTIME_SMOKE_VERIFY: BLOCKED_NO_SAFE_CLUSTER`.

Smoke values disable: production, real deploy, production auth, OIDC, GitHub write, PR,
deployment, real LLM, external delivery, production backup schedule.
