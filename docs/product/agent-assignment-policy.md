# Agent Assignment Policy (Step 57)

Capability-based assignment with role fallback; see
[`infra/delivery/agent-assignment-policy.yaml`](../../infra/delivery/agent-assignment-policy.yaml).
When no capable agent is available the work item is blocked. No autonomous production
action, no direct production deploy, no GitHub write, no external send. Manual
reassignment is future work.
