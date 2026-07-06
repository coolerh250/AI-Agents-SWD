# E2E Staging Agent Pipeline Record (Step 65G.2)

> **Staging only — non-production only. No production action. No production data.**
> **Read-only pipeline evidence. No secret value printed.**

Records the real distributed agent pipeline run for the fresh intake
`step65g2-e2e-20260706074202`.

## Fresh intake
- `POST :18004/intake/mock` with `{ task_id: step65g2-e2e-20260706074202, publish_to_stream: true,
  request: { type: feature, title: "Create staging-only user profile preference API", description:
  "…staging-only…", environment: staging, production_effect: false } }`.
- Response: `mode=stream`, `stream=stream.tasks`, `published_id=1783323767121-0`. HTTP 200.
- Exactly **one** fresh intake was executed.

## Agent pipeline (all 5 hops completed)
| # | Agent | Status | Started | Completed |
|---|---|---|---|---|
| 1 | intake-agent | completed | 07:42:47.150 | 07:42:47.194 |
| 2 | requirement-agent | completed | 07:42:47.180 | 07:42:47.256 |
| 3 | development-agent | completed | 07:42:47.257 | 07:42:47.490 |
| 4 | qa-agent | completed | 07:42:47.471 | 07:42:47.681 |
| 5 | devops-agent | completed | 07:42:47.660 | 07:42:47.880 |

- Source: `GET /operations/agent-executions?task_id=step65g2-e2e-20260706074202` → `count=5`, all
  `status=completed`. End-to-end in ~730 ms.
- Each hop consumed from / published to the Redis stream chain
  (`stream.tasks → stream.requirements → stream.development → stream.qa → stream.deployments →
  stream.devops`) and recorded an agent_execution + audit event.

## Pipeline-native integrations stayed safe (as planned in 65G.1)
- The development-agent used the **mock** LLM provider (the real LLM call was the separate controlled
  65F-rail step, not the pipeline's inline planner).
- The devops-agent's GitHub behavior stayed **dry-run** (the real sandbox draft PR was the separate
  controlled 65D-rail step).
- The pipeline notifications stayed **simulated** (the real send was the separate controlled 65E-rail
  step).

## Workflow-state note (tracked gap, confirmed)
- The stream-mode fresh intake did **not** create a `workflow_state`, so `/task-graph` shows no
  trace for this task. Pipeline evidence is on `/agent-executions`. This confirms the Step 65G.1
  tracked hypothesis; **no `workflow_state` was fabricated.**

## Status
Step 65G.2 pipeline: all 5 hops completed; `production_executed_true_count=0`. Operator UI
validation pending.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
