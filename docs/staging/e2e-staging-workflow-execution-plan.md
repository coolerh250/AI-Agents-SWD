# E2E Staging Workflow Execution Plan (Step 65G.2 plan)

> **Staging only — non-production only. No production action. No production data.**
> **Planning only — no step below is executed in this stage (65G.1).**

Step-by-step execution plan for Step 65G.2, mapping the exact expected path. Each real external call
goes through its controlled rail only.

## Flow map
| # | Step | Entry point | Service / endpoint / stream | Evidence object | UI page | External? | Guardrail | Success | Failure / abort |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Intake creation | operator-authorized script | `POST :18004/intake/mock/project-work-item` + `POST :18004/intake/mock {publish_to_stream:true}` | project + work_item rows; `task.created` on `stream.tasks` | `/delivery` | no | fresh, `production_effect=false` | project+WI created; task published | intake error → stop |
| 2 | Project / work item | communication-gateway | ProjectStore + WorkItemStore | project + work_item | `/delivery` | no | `environment_scope∈{dev,test,nonprod}` | rows visible | production scope → abort |
| 3 | Workflow trace | (tracked gap) stream pipeline and/or `/workflow/test` | orchestrator WorkflowStore | `workflow_state` | `/task-graph` | no | mock in-process only | trace visible | no trace → tracked-gap follow-up |
| 4 | Agent pipeline | intake→requirement→development→qa→devops | Redis streams (`stream.*`) | agent_execution + audit + discussion rows | `/agent-executions` | no | default safe mode | all 5 hops recorded | a hop stalls → inspect, no retry w/o auth |
| 5 | LLM call point | operator-authorized controlled step | `RealLLMPlanOnlyProvider` + `BudgetPolicyEvaluator` + LLMInteractionStore | llm_interaction + usage + budget events | `/cost-llm` | **yes (65F rail)** | budget cap ≤$1; plan-only; audit-recorded | one bounded call, `plan_only=true` | direct/diagnostic call → abort |
| 6 | QA / code evidence | qa-agent | `stream.qa` → QA store | qa evidence / code checks | `/qa-code` | no | mock/static in default mode | QA evidence present | — |
| 7 | DevOps behavior | devops-agent | `stream.deployments` → `stream.devops` | deployment_record (dry-run) | `/task-graph` / `/agent-executions` | no | **no real deploy**; native demo-PR left dry-run | dry-run recorded | any real deploy → abort |
| 8 | GitHub sandbox draft PR | operator-authorized controlled step | `POST :18000/operations/github/sandbox-draft-pr` (65D rail) | sandbox draft-PR request + evidence file | `/sandbox-github` | **yes (65D rail)** | sandbox repo only; draft only; no merge | draft PR created | non-sandbox target → abort |
| 9 | Discord notification | operator-authorized controlled step | `POST :18007/discord/real/test-message` (65E rail) | notification_delivery (external_sent) | (delivery record) | **yes (65E rail)** | `MySanbox/#general`; `[STAGING]`; one send | one delivered send | production channel/DM → abort |
| 10 | Audit / evidence | audit-service + audit-worker | audit chain | audit_log + integrity records | `/audit-evidence` | no | integrity preserved | audit complete | integrity break → abort |
| 11 | Admin Console visibility | operator (browser) | formal pages | all of the above | formal pages | no | formal pages only (not `/demo-evidence`) | evidence visible | evidence missing → fail |
| 12 | Safety Center | operator (browser) + `/operations/safety` | orchestrator | safety snapshot | `/safety` | no | stays safe | `production_executed_true_count=0` | count changes → abort |

## Ordering for 65G.2
1. Read-only pre-checks (safety baseline; confirm the workflow-trace tracked gap #3).
2. Fresh intake (steps 1–2) → real pipeline runs (steps 3–4, 6–7) in **default safe mode**.
3. Controlled LLM step (step 5) — separately authorized, budget-gated.
4. Controlled GitHub sandbox draft-PR step (step 8) — separately authorized.
5. Controlled Discord `[STAGING]` notification (step 9) — separately authorized.
6. Audit/evidence + Admin Console + Safety Center verification (steps 10–12).
7. Reset all live flags to safe (see the abort/reset plan).

## Correlation
All controlled-rail steps (5, 8, 9) must carry the **same task/correlation id** as the fresh intake
(step 1) so the Admin Console evidence ties together end-to-end.

## This stage's posture
Planning only. No workflow execution, no GitHub write, no Discord send, no LLM call, no runtime
change, no production action. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
