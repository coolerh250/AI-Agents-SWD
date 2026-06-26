# Work-item Decomposition Policy (Step 57)

Deterministic (no LLM) decomposition types: epic, feature, task, bug, security_task,
ops_task, research_task, verification_task, release_task. Each declares allowed target
agents, required input/output, default approval requirement, allowed environments
(dev/test/nonprod), `productionEffectDefault=false`, and delivery-package linkage
requirement. See
[`infra/delivery/work-item-decomposition-policy.yaml`](../../infra/delivery/work-item-decomposition-policy.yaml).
release_task requires delivery-package linkage and operator review; no production
effect in this stage.
