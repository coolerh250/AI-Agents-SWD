# Operator Demo Workflow Review Guide (Step 64E)

> **Staging only — non-production only. No production action. No production secret. No external write.**

How an operator reads and interprets the Step 64D demo.

> **Correction (Step 64E-R):** most of what this guide describes ("in the Admin Console the
> operator sees each stage's agent execution", audit interpretation, etc.) is **not visible in
> the deployed console** — it reflects backend API data + the full React app, not the deployed
> zero-build fallback. The operator walkthrough confirmed only aggregate counts + safety posture
> are visible. Treat the agent-stage / audit sections below as **API-level explanation**, not
> operator-visible pages, until the console deployment gap is remediated. See
> [staging-admin-console-deployment-gap.md](staging-admin-console-deployment-gap.md).

## Demo project
- **SaaS User Management Module** (`PRJ-SAAS-USER-MANAGEMENT-MODULE-15F51D`), environment
  `nonprod`, `production_allowed=false`. A non-production demonstration project.

## Demo work item
- **WI-0001 — "Create user CRUD API"**: build a staging-only user management CRUD API with
  create/read/update/delete operations. `production_effect=false`, `requires_human_approval=false`,
  lifecycle `created`.

## Workflow path
The mock agent workflow runs: **intake → requirement → development → qa → devops**. In the
Admin Console the operator sees each stage's agent execution as `completed`.

## Agent stage interpretation
| Stage | Agent | What it means |
|---|---|---|
| intake | intake-agent | request accepted + classified (mock) |
| requirement | requirement-agent | requirement spec drafted (mock) |
| development | development-agent | code workspace produced (mock) |
| qa | qa-agent | QA run executed (mock) |
| devops | devops-agent | **mock** deploy — `production_executed=false`, not a real deployment |

**10 agent executions, all completed, 0 failed** (5-stage pipeline × 2 demo tasks).

## Audit interpretation
- `work_item_created` recorded for WI-0001 (actor `staging-demo`, role `intake`).
- Each workflow run carries `audit_refs`. `audit_logs_total≈60`.
- All audit entries are non-production; nothing was approved for or executed in production.

## Metrics interpretation
- `project_count_total=1`, `work_item_count_total=1`, `dispatch_count_total=0`,
  `production_executed_true_count=0`, `production_ready=false`.
- `dispatch_count_total=0` because the governed delivery dispatch is gated (see below).

## Why delivery package / release candidate are not yet present
The delivery work item stays at lifecycle `created` / `delivery_state=not_started`. The
governed work-item **dispatch** (`POST /operations/delivery/work-items/{id}/dispatch`) — which
would drive a delivery package and a release candidate — requires operator auth + CSRF, and
**operator actions are disabled in staging**. So Release Governance shows no candidate. This is
an expected, documented gap, not a failure. See
[operator-known-gaps-and-limitations.md](operator-known-gaps-and-limitations.md).

## Safety
No production action; live integrations disabled/mocked; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
