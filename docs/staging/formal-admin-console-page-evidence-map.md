# Formal Admin Console Page Evidence Map (Step 64E.4A)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Planning only — no code change, no rebuild, no restart in this stage.**

Maps each demo-evidence type to the **formal product page** that must surface it, and defines for
each page: purpose, operator question answered, expected demo evidence, required API endpoints,
required UI behavior, empty-state behavior, known current gap, test acceptance criteria, staging
acceptance criteria. The Demo Evidence page is **not** in this map — it is diagnostic only.

## Evidence-type → formal page
| Evidence | Formal page |
|---|---|
| WI-0001 | **Projects / Work Items** |
| Agent executions | **Agent Executions** |
| Workflow | **Workflows / Task Graph** |
| QA/code | **QA / Code** |
| Audit/evidence | **Audit / Evidence** |
| Safety | **Safety Center** |

## Projects / Work Items
- **Purpose:** show delivery projects and their work items.
- **Operator question answered:** "What is being delivered, and what is WI-0001's status?"
- **Expected demo evidence:** demo project `SaaS User Management Module`; work item `WI-0001`
  `Create user CRUD API`; work-item status/lifecycle; environment / production flag; link to
  related execution/evidence.
- **Required API endpoints:** `/operations/delivery/projects`,
  `/operations/delivery/projects/{id}/work-items`, `/operations/delivery/work-items/{id}`.
- **Required UI behavior:** project detail lists work items without a manual pre-selection
  workaround; WI-0001 opens a work-item detail with lifecycle + links.
- **Empty-state behavior:** "No projects / work items yet" distinct from an error.
- **Known current gap:** Projects/ProjectDetail carry no `work_items`; work items load only after
  manual project selection in Multi-project Delivery.
- **Test acceptance criteria:** component test renders WI-0001 from a mocked projects+work-items
  response; contract test asserts the work-items endpoint shape.
- **Staging acceptance criteria:** operator opens Projects → demo project → sees WI-0001 with
  status and a link to its evidence, with no Demo Evidence page.

## Agent Executions
- **Purpose:** show per-agent executions for the delivery pipeline.
- **Operator question answered:** "Which agents ran, in what order, with what status?"
- **Expected demo evidence:** intake, requirement, development, qa, devops executions; execution
  status; correlation/workflow link; `production_executed=false` indicator where available.
- **Required API endpoints:** `/operations/agent-executions` (read-only, shaped) and/or
  `/operations/metrics/agents` for aggregate.
- **Required UI behavior:** a formal Agent Executions list page renders the executions with status
  and correlation, reachable from the top nav.
- **Empty-state behavior:** "No agent executions yet".
- **Known current gap:** only aggregate `/operations/metrics/agents` was wired; WorkspaceExecution
  read `latest_pilot` (=None for the demo).
- **Test acceptance criteria:** component test renders 5 pipeline executions from a mocked list;
  contract test asserts no raw error/metadata fields exposed.
- **Staging acceptance criteria:** operator sees the pipeline executions on the formal page.

## Workflows / Task Graph
- **Purpose:** show the workflow/stage trace.
- **Operator question answered:** "How did the workflow progress, and did it touch production?"
- **Expected demo evidence:** workflow id or correlation id; stage sequence; completed stages;
  workflow status; `production_executed=false`.
- **Required API endpoints:** `/operations/workflows` (read-only, shaped) and/or
  `/operations/metrics/workflows`.
- **Required UI behavior:** replace the Task Graph stub with a workflow/stage view; show
  `production_executed=false`.
- **Empty-state behavior:** "No workflows yet".
- **Known current gap:** only aggregate `/operations/metrics/workflows`; Task Graph is a stub.
- **Test acceptance criteria:** component test renders 2 workflows with `production_executed=false`
  from a mocked list.
- **Staging acceptance criteria:** operator sees the workflow trace with `production_executed=false`.

## QA / Code
- **Purpose:** show QA runs and code workspace/output summaries.
- **Operator question answered:** "Did QA run, and what code output exists for this work item?"
- **Expected demo evidence:** QA run summary + status; code workspace/output summary; related work
  item or workflow; known gaps if rows are count-only.
- **Required API endpoints:** `/operations/qa/runs`, `/operations/code/workspaces`.
- **Required UI behavior:** wire the formal QA and Code/Workspace pages to render these; link to
  the related work item/workflow.
- **Empty-state behavior:** "No QA runs / code workspaces yet"; if only counts are available, show
  the count and label the per-row gap.
- **Known current gap:** endpoints return data but no formal page calls them; QA `validation_runs`
  per-row detail may be empty (count-only).
- **Test acceptance criteria:** component test renders QA/code summaries from mocked responses.
- **Staging acceptance criteria:** operator sees QA + code summaries on the formal pages.

## Audit / Evidence
- **Purpose:** show audit events and evidence references.
- **Operator question answered:** "What was recorded for this work item, and when?"
- **Expected demo evidence:** `work_item_created` event; workflow audit references if available;
  event count; event type; timestamp; `production_executed=false` where available.
- **Required API endpoints:** `/operations/delivery/work-items/{id}/events`, and/or
  `/operations/metrics/audit` for aggregate.
- **Required UI behavior:** a formal Audit / Evidence page consumes per-work-item events, not only
  aggregate metrics.
- **Empty-state behavior:** "No audit events yet".
- **Known current gap:** only aggregate `/operations/metrics/audit`; per-event endpoint unconsumed.
- **Test acceptance criteria:** component test renders the `work_item_created` event from a mocked
  events response.
- **Staging acceptance criteria:** operator sees the work-item audit events on the formal page.

## Operational Metrics
- **Purpose:** show aggregate delivery/workflow/agent/audit counts.
- **Operator question answered:** "What is the overall staging activity summary?"
- **Expected demo evidence:** projects/work-items/dispatches counts; workflow/agent/audit
  aggregates; `production_executed` count.
- **Required API endpoints:** `/operations/metrics/*`.
- **Required UI behavior:** existing metrics page continues to render aggregates.
- **Empty-state behavior:** zeroed counts render as `0`, not blank.
- **Known current gap:** aggregate-only — not a substitute for the per-item formal pages above.
- **Test acceptance criteria:** existing metrics tests pass.
- **Staging acceptance criteria:** operator sees consistent aggregates matching the per-item pages.

## Safety Center
- **Purpose:** show the staging safety posture.
- **Operator question answered:** "Is anything touching production or live integrations?"
- **Expected demo evidence:** `production_executed_true_count=0`; live integrations disabled or
  clearly labeled; external write disabled; production deploy/sync disabled.
- **Required API endpoints:** `/operations/safety`.
- **Required UI behavior:** Safety Center renders the posture flags clearly.
- **Empty-state behavior:** N/A (posture always present); `result=warning` for mock-vault is
  expected and must be labeled.
- **Known current gap:** none functional; `result=warning` due to mock-vault must be explained.
- **Test acceptance criteria:** component test renders `production_executed_true_count=0`.
- **Staging acceptance criteria:** operator confirms `production_executed_true_count=0` and
  disabled/labeled integrations.

## Release Governance
- **Purpose:** show release/governance gating state.
- **Operator question answered:** "What is gated, and is any release action possible in staging?"
- **Expected demo evidence:** operator mutations gated (`operator_actions_disabled`); no release
  executed; `production_executed=false`.
- **Required API endpoints:** existing governance/operator-action read endpoints (read-only).
- **Required UI behavior:** render the gated posture; no enabled release action in staging.
- **Empty-state behavior:** "No release actions available in staging".
- **Known current gap:** delivery package/release candidate gated behind operator auth (disabled in
  staging) — expected.
- **Test acceptance criteria:** component test renders the gated/disabled governance state.
- **Staging acceptance criteria:** operator confirms release actions are gated/disabled in staging.

## Status
- Step 64E: **FAILED_STAGING_REPRESENTATIVENESS**. Step 64F: **BLOCKED**.
- Demo Evidence page: **diagnostic only — not staging acceptance**.
- **No production action**; `production_executed_true_count=0`. **No implementation claimed.**

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
