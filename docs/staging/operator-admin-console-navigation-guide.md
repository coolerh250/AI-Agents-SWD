# Operator Admin Console Navigation Guide (Step 64E)

> **Staging only — non-production only. No production action. No production secret. No external write.**

Page-by-page guidance for the **staging** Admin Console (`http://localhost:18000/admin` via the
operator SSH tunnel). All pages are **read-only**; operator mutations are disabled in staging
(`operator_actions_disabled`).

> **Correction (Step 64E-R, after the operator walkthrough):** the **deployed** console is the
> zero-build static fallback with **18 tabs**, and it is **summary-only** — it does **not**
> render per-item work items, agent executions, workflows, QA/code, or audit. Earlier versions
> of this guide listed pages (Agent Executions, Workflows, QA/Code, Task Graph, Workspace
> Execution, Operator Console) that are **not in the deployed console**; those were based on the
> React source, not on what is served. The demo's per-item evidence exists only via backend API.
> Root cause + remediation: [staging-admin-console-deployment-gap.md](staging-admin-console-deployment-gap.md).
>
> **Deployed tabs (18):** Executive Overview, Projects, Delivery Package, Safety Center,
> Regression, Cost/LLM, Incidents, Runtime Baseline, Identity Posture, Secret Posture,
> Security/Supply Chain, Multi-project Delivery, Operational Metrics, Sandbox GitHub Draft PR,
> Release Governance, Backup/Restore/DR, Production Readiness Gate, Controlled Rollout Review.
> **What is genuinely visible:** aggregate counts (Executive Overview, Operational Metrics) and
> the safety posture (Safety Center, Multi-project Delivery flags). **Not visible:** work-item
> identity, agent executions, workflows, QA/code, audit.

The sections below describe the *intended* per-page content of the full React app; treat any
"Agent Executions / Workflows / QA / Task Graph / Workspace / Operator Console" entry as
**not present in the current deployed console** until the deployment gap is remediated.

## Overview / Dashboard (`/`)
- **What to look for:** platform + delivery status cards, service/workflow summaries.
- **Expected demo data:** workflow + agent activity present (2 workflows completed).
- **Interpretation:** the staging platform is up and has processed the demo.

## Projects / Work Items (`/projects`, `/delivery`)
- **What to look for:** the demo project and its work item.
- **Expected demo data:** **SaaS User Management Module** (`nonprod`); work item **WI-0001
  "Create user CRUD API"** (lifecycle `created`, `production_effect=false`).
- **Interpretation:** the demo project/work item were seeded non-production.

## Agent Executions (`/workspace`, `/operator`)
- **What to look for:** the agent pipeline stages.
- **Expected demo data:** intake → requirement → development → qa → devops, **10 executions,
  all completed, 0 failed**.
- **Interpretation:** the mock agent workflow ran end-to-end without production effect.

## Workflows (`/task-graph`, Overview workflows summary)
- **Expected demo data:** 2 workflows, 2 completed, 0 failed.

## QA / Code output (`/regression`, workspace/code views)
- **Expected demo data:** 2 QA runs; 2 code workspaces.
- **Interpretation:** mock QA + code generation artifacts for the demo task.

## Operational Metrics (`/metrics`)
- **What to look for:** counters.
- **Expected demo data:** `project_count_total=1`, `work_item_count_total=1`,
  `dispatch_count_total=0`, `production_executed_true_count=0`, `production_ready=false`.

## Audit / Evidence (Audit views; Safety Center audit)
- **Expected demo data:** `work_item_created` event (actor `staging-demo`); `audit_logs_total≈60`.
- **Interpretation:** all demo actions are audited and non-production.

## Release Governance (`/release-governance`)
- **Expected empty state:** no release candidate.
- **Known gap:** the governed delivery dispatch (which would create a release candidate) is
  gated behind operator auth, disabled in staging. See
  [operator-known-gaps-and-limitations.md](operator-known-gaps-and-limitations.md).

## Backup / DR (`/backup-dr`)
- **Expected data:** baseline read-only DR posture; not exercised by the demo.

## Production Readiness Gate (`/production-readiness`)
- **What to look for:** readiness decision.
- **Expected data:** not production-ready; decision remains `ready_for_operator_review` (Step
  62). **Not** an approval to deploy.

## Controlled Rollout Review (`/controlled-rollout-review`)
- **Expected data:** recommendation `no_go` (Step 63A). A recommendation is not an approval.

## Safety Posture (`/safety`)
- **What to look for:** production toggles + counters.
- **Expected data:** `production_executed_true_count=0`; production deploy/sync/secret off; live
  GitHub/Discord/LLM off. See [operator-safety-check-guide.md](operator-safety-check-guide.md).

## Sandbox GitHub / External Integration Safety (`/sandbox-github`)
- **Expected data:** sandbox draft-PR safety posture; **live GitHub write disabled**
  (`github_external_write_enabled=false`). Any token present is sandbox/mock only.
- **Interpretation:** no live external write can occur.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
