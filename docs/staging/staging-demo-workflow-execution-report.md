# Staging Demo Workflow Execution Report (Step 64D)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Live GitHub / Slack (Discord) / LLM integrations disabled or mocked.**

Overall result: **PASS_WITH_GAPS**. A demonstrable non-production workflow was seeded and
executed on the staging runtime (`10.0.1.32`, `agentai-swd-stage`): the **SaaS User Management
Module** project + **Create user CRUD API** work item were created, and the mock agent
workflow ran through the full intake → requirement → development → qa → devops pipeline. Two
gaps are documented (delivery-package / release-candidate are gated; a gateway image bug was
worked around) — see [staging-demo-known-gaps.md](staging-demo-known-gaps.md).

## Runtime status
- **Target host:** `10.0.1.32`; repo `/data/ai-agents-staging/AI-Agents-SWD` at `f43e163`
  (only docs/tests/scripts changed since — no runtime-code sync needed).
- **Runtime:** running — 22/22 containers. `/health` 200; `/admin/` 200; `/operations/safety`
  200 with `production_executed_true_count=0`.

## Demo scenario
- **Demo project:** SaaS User Management Module (`PRJ-SAAS-USER-MANAGEMENT-MODULE-15F51D`,
  environment_scope `nonprod`, `production_allowed=false`).
- **Demo work item:** `WI-0001` — "Create user CRUD API" (`production_effect=false`,
  `requires_human_approval=false`, lifecycle `created`).

## Seed method
Seeded via the existing project / work-item SDK (`ProjectStore` / `WorkItemStore` — the same
code path as the communication-gateway mock intake), run inside the orchestrator container by
`scripts/staging_seed_demo_workflow.py` (staging-only, idempotent). The gateway's own
`/intake/mock/project-work-item` endpoint currently 500s due to a missing PyYAML dependency in
the gateway image (documented gap); the orchestrator container has the SDK + PyYAML. No raw SQL
was used; no production action. Details: [staging-demo-seed-data.md](staging-demo-seed-data.md).

## Workflow execution path
The mock agent workflow was executed via the orchestrator `POST /workflow/test` (non-production
`run_mock_workflow`, `mock=true`, `production_executed=false`). The pipeline consumed the
dispatched task through all stages:

| Stage | Agent | Result |
|---|---|---|
| intake | intake-agent | completed |
| requirement | requirement-agent | completed |
| development | development-agent | completed |
| qa | qa-agent | completed |
| devops (mock deploy) | devops-agent | completed |

- **Agent executions:** 10 total, 10 completed, 0 failed (5-agent pipeline × 2 demo tasks).
- **Workflows:** 2 total, 2 completed, 0 failed (`approval_required=false`, `risk_level=low`).
- **QA runs:** 2 · **Code workspaces:** 2 · **LLM interactions:** 0 (LLM disabled/mocked — no
  live call).
- **Execution result:** `awaiting_agents` → all agents `completed`; `production_executed=false`.

## Delivery / release evidence
- **Gated:** the delivery work item remains at lifecycle `created`, delivery_state
  `not_started`, `0` dispatches — the governed work-item **dispatch** (which would drive a
  delivery package + release candidate) requires operator auth, and **operator actions are
  disabled in staging** (`operator_actions_disabled`). No delivery package / release candidate
  was produced. See [staging-demo-delivery-evidence.md](staging-demo-delivery-evidence.md).

## Audit evidence
`work_item_created` recorded for `WI-0001` (actor `staging-demo`, role `intake`); mock-workflow
`audit_refs` recorded per workflow; `audit_logs_total=60`. See
[staging-demo-audit-evidence.md](staging-demo-audit-evidence.md).

## Admin Console evidence
Backing `/operations/*` endpoints return the demo data (project=1, work items=1, workflows=2,
agent executions=10, qa runs=2). **Correction (Step 64E-R):** this is **backend-API only**. The
operator walkthrough found the deployed console (zero-build fallback) surfaces only aggregate
counts + safety posture; work-item identity, agent executions, workflows, QA/code, and audit are
**not visible** in the console. See
[staging-demo-admin-console-evidence.md](staging-demo-admin-console-evidence.md) and
[staging-admin-console-deployment-gap.md](staging-admin-console-deployment-gap.md).

## Safety posture (final)
- `production_executed_true_count = 0`; `deployment_environment_production_count = 0`;
  `workflow_production_executed_true_count = 0`.
- `github_external_write_enabled=false`; `discord_external_send_enabled=false`; LLM live off.
- No production deploy / sync / secret / external write; no public exposure.

## Explicit statements
- **No production action** was performed; the demo is non-production and mock throughout.
- **Live integrations disabled / mocked.** `production_executed_true_count=0`.
- **Claude Code does not decide production readiness.**

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false live-integrations=disabled demo-workflow-executed=true -->
