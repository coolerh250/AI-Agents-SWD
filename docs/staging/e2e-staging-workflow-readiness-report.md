# E2E Staging Workflow Readiness Report (Step 65G.1)

> **Staging only — non-production only. No production action. No production secret. No production data.**
> **Readiness / planning only — no workflow was executed, no GitHub write, no Discord send, no LLM call, no runtime change in this stage.**

Read-only readiness assessment for Step 65G (End-to-End Staging Workflow Validation). Grounded in a
read-only inspection of the actual staging services, routes, and agent pipeline on `10.0.1.32`
(HEAD `7bf8809`, all 22 services healthy).

## Baseline confirmed (read-only)
- `/operations/safety`: `production_executed_true_count=0`, `llm_provider=mock`,
  `llm_real_enabled=false`, `discord_external_send_enabled=false`,
  `sandbox_github_draft_pr_live_mode_enabled=false`, `admin_console_read_only=true`.
- Running agent pipeline services (healthy): `intake-agent`, `requirement-agent`,
  `development-agent`, `qa-agent`, `devops-agent`, plus `communication-gateway`, `orchestrator`,
  `github-automation`, `notification-worker`, `discord-gateway`, `audit-service`, `audit-worker`.

## Fresh-intake entry point (the "seeded evidence" gap this closes)
All prior Step-65 evidence was seeded/mock (`/workflow/test` + delivery seed). The **fresh** intake
entry that drives the real distributed agent pipeline is:
- **`POST http://127.0.0.1:18004/intake/mock`** (communication-gateway) with
  `{ "request": {...}, "publish_to_stream": true }` → publishes `task.created` to the Redis stream
  **`stream.tasks`** → consumed by the real 5-agent pipeline.
- Optionally paired with **`POST http://127.0.0.1:18004/intake/mock/project-work-item`** to create
  the formal **Project + Work Item** objects (`production_effect=false`) that surface on the
  Admin Console `/delivery` page.

## Real agent pipeline (confirmed by source inspection)
```
stream.tasks    → intake-agent      → stream.requirements
stream.requirements → requirement-agent → stream.development
stream.development  → development-agent → stream.qa
stream.qa       → qa-agent           → stream.deployments
stream.deployments → devops-agent    → stream.devops
```
Each hop records an **agent_execution** row, an **audit event**, and an **agent_discussion** row.

## Critical architectural finding (drives the whole 65G plan)
The pipeline's **native** external-integration points are mock / dry-run by default, and are **not**
the controlled rails validated in 65D/65E/65F:
- **LLM:** the development-agent uses the **mock** LLM provider by default (`"mock": True`). It does
  **not** natively route through the platform budget/audit rail (`RealLLMPlanOnlyProvider` +
  `BudgetPolicyEvaluator`) that Step 65F validated.
- **GitHub:** the devops-agent calls github-automation `/demo-pr` in **dry-run** by default — this
  is the older demo-PR path, **not** the Step 59 sandbox draft-PR rail
  (`/operations/github/sandbox-draft-pr`) that Step 65D validated.
- **Notification:** the pipeline publishes to `stream.notifications` → notification-worker, which is
  **simulated** by default. The Step 65E validated rail is the discord-gateway
  `/discord/real/test-message` endpoint.

**Consequence:** to satisfy the Step 65F-C guardrail ("all real GitHub/Discord/LLM must go through
the controlled rails"), Step 65G must **not** rely on the pipeline's native integration points for
real external artifacts. Instead:
1. Run the fresh intake through the real distributed pipeline in **default safe mode** (mock LLM,
   dry-run PR, simulated notification) to produce real **workflow / agent-execution / QA / audit /
   safety** evidence with a fresh correlation id — this closes the "all evidence is seeded" gap for
   the orchestration + pipeline dimensions **without any real external write**.
2. Exercise the three **controlled rails** as **separately-authorized, correlated controlled
   steps** (LLM via the 65F budget/audit rail; GitHub via the 65D sandbox draft-PR rail; one
   `[STAGING]` Discord notification via the 65E rail), each tied to the same task/correlation id, so
   the E2E evidence surfaces **real controlled external artifacts** on the formal pages.

## Admin Console formal pages (routes confirmed in `App.tsx`)
Acceptance is on **formal** pages only — Diagnostics / `/demo-evidence` is **not** an acceptance
path:
- `/delivery` — Projects / Work Items (MultiProjectDelivery)
- `/agent-executions` — Agent Executions
- `/task-graph` — Workflows / Task Graph
- `/qa-code` — QA / Code
- `/audit-evidence` — Audit / Evidence
- `/safety` — Safety Center
- `/cost-llm` — LLM cost / governance (for the controlled LLM step)
- `/sandbox-github` — Sandbox GitHub (for the controlled draft-PR step)
- `/metrics` — Operational Metrics (if relevant)

## Readiness verdict
- **Step 65G status: READY_FOR_CONTROLLED_EXECUTION (with one tracked gap).**
- **Tracked gap (before 65G.2):** confirm, by read-only check at 65G.2 start, whether a stream-mode
  fresh intake alone produces a **`workflow_state`** visible on `/task-graph`, or whether the run
  must also register/thread a workflow (the mock `/workflow/test` path is what creates
  `workflow_states`; the stream pipeline records agent_executions). This does not block planning; it
  is the first read-only step of 65G.2. Tracked in
  [staging-functional-gap-register.md](staging-functional-gap-register.md).

## This stage's posture
Readiness / planning only. **No workflow execution, no GitHub write, no Discord send, no LLM call,
no runtime change, no production action.** `production_executed_true_count=0`.

## Companion documents
- [e2e-staging-workflow-test-case.md](e2e-staging-workflow-test-case.md)
- [e2e-staging-workflow-execution-plan.md](e2e-staging-workflow-execution-plan.md)
- [e2e-staging-integration-guardrails.md](e2e-staging-integration-guardrails.md)
- [e2e-staging-budget-and-call-limits.md](e2e-staging-budget-and-call-limits.md)
- [e2e-staging-admin-console-validation-checklist.md](e2e-staging-admin-console-validation-checklist.md)
- [e2e-staging-abort-and-reset-plan.md](e2e-staging-abort-and-reset-plan.md)
- [e2e-staging-operator-authorization-template.md](e2e-staging-operator-authorization-template.md)

---
_Staging only — non-production only. No production action. No production secret. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
