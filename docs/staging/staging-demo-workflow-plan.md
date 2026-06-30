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

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false -->
