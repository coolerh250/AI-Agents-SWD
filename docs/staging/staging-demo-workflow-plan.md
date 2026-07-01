# Staging Demo Workflow Plan (Step 64A)

> **Staging only — non-production only. No production action. No production secret. No external write.**

A scripted, seedable demo workflow for the operator walkthrough. Defined here; **seeded and
executed in Step 64D** (not in Step 64A).

## Demo
- **Demo Project:** SaaS User Management Module
- **Demo Work Item:** Create user CRUD API

## Seed data
- One project `SaaS User Management Module` (non-production, environment_scope = staging,
  production_allowed = false).
- One work item `Create user CRUD API` (delivery work type; production_effect = false → no
  production action).
- Seeded via a Step 64D seed script writing to the staging Postgres only (no production DB).

## Workflow path
intake → requirement → planning / design-review → development (sandbox/dry-run, LLM mocked)
→ QA → delivery package assembly → acceptance gate (operator review) → release governance
candidate (non-production) → recorded. No GitHub merge, no image push, no deploy.

## Expected agent stages
intake-agent → requirement-agent → project-planner-agent → design-review-agent →
development-agent → qa-agent → workspace-operator-agent (all mockable; LLM/GitHub live
disabled).

## Expected audit events
project_created, work_item_created, work_item_dispatched, agent stage transitions,
delivery_package_created, acceptance_gate evaluated, release_candidate_created — all with
`production_executed=false`.

## Expected delivery package
A non-production delivery package for `Create user CRUD API` with QA + acceptance evidence,
visible in the Admin Console Delivery Package page; `production_ready=false`.

## Expected Admin Console evidence
Project + work item visible (Projects); agent run trace (Agent Executions / Workspace);
metrics counters (Operational Metrics); a release candidate (Release Governance, non-prod);
safety posture green (Safety) with `production_executed_true_count=0`.

## Step 64D execution update
Executed **PASS_WITH_GAPS**: seeded SaaS User Management Module + `WI-0001` "Create user CRUD
API" (nonprod, `production_effect=false`) via `scripts/staging_seed_demo_workflow.py`, and ran
the mock agent workflow (`/workflow/test`) through the full intake→requirement→development→qa→
devops pipeline (10 agent executions completed, 2 QA runs, 2 code workspaces, 2 workflows
completed). Audit `work_item_created` recorded; `audit_logs_total=60`. Admin Console pages
populated; `production_executed_true_count=0`. **Gaps:** delivery package + release candidate
gated (governed dispatch needs operator auth, disabled in staging); gateway mock-intake
endpoint 500s on a missing-PyYAML image bug (worked around via the orchestrator container). See
[staging-demo-workflow-execution-report.md](staging-demo-workflow-execution-report.md) and
[staging-demo-known-gaps.md](staging-demo-known-gaps.md).

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false -->
