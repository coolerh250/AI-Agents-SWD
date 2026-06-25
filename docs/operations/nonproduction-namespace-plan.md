# Non-production Namespace Plan (Step 55)

Source: [`infra/kubernetes/nonproduction-namespace-plan.yaml`](../../infra/kubernetes/nonproduction-namespace-plan.yaml)

The smoke deploys ONLY into an explicitly non-production namespace
(`aiagents-smoke-dev` / `aiagents-smoke-test`) labelled
`aiagents.openai.local/environment=non-production`, `purpose=runtime-smoke`,
`production="false"`. Forbidden namespaces (`default`, `kube-system`, `argocd`,
`production`, `prod`, `staging-prod`) and any name containing `prod` are rejected by
the runner + `verify_nonproduction_namespace_plan.py`. The namespace is created only
when the preflight is safe; never cluster-scoped, never `default`.
