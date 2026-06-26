# Work-item Dispatch Policy (Step 57)

Maps work types to internal agent targets/streams (requirement→requirement-agent,
planning→project-planner, implementation→development-agent, qa→qa-agent,
deployment_simulation→devops-agent, delivery_package→delivery-package,
notification→communication-gateway, …). See
[`infra/delivery/work-item-dispatch-policy.yaml`](../../infra/delivery/work-item-dispatch-policy.yaml).

Forbidden targets: github-write, github-pr, argocd-sync, production-executor,
external-notification-send. Every dispatch event carries project_id / work_item_id /
dispatch_key / target_agent / correlation_id / production_effect, and all external
side effects (github write, ArgoCD sync, external send, production action) are false.
production_effect work items are never dispatched (routed to waiting_approval).
