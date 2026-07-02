# Product UI Remediation Plan (Step 64E.4A)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Planning only — no code change, no rebuild, no restart, no redeploy in this stage.**

Defines how the staging Admin Console must be remediated so the **formal product pages** — not a
special Demo Evidence page — naturally represent the operator workflow. This is the acceptance
target for Step 64E after the operator judged the added Demo Evidence page insufficient for
staging validation.

## Acceptance principle
- **Formal product UI is the acceptance target.** Staging validation must exercise the pages a
  real operator would use, not a purpose-built evidence dump.
- **The Demo Evidence page is diagnostic only** (developer/debug view). It may remain in the build
  but must not be the staging acceptance path and must not be cited as proof the product UI works.
  See [demo-evidence-page-diagnostic-only-policy.md](demo-evidence-page-diagnostic-only-policy.md).
- **Step 64E remains `FAILED_STAGING_REPRESENTATIVENESS`.**
- **Step 64F remains `BLOCKED`.**
- **Claude Code does not decide operator acceptance** and does not decide production readiness.

## Operator conclusion driving this plan
The data is visible through the added Demo Evidence page, but that is not acceptable as staging
validation. Staging must validate the formal product UI, not a special demo page. If the formal
product pages are incomplete, the work returns to test/QA remediation before staging validation.
Staging should eventually connect to controlled, non-production external resources — not rely only
on fake/demo data.

## The ten planning answers
1. **Which formal pages must show WI-0001?** Projects / Work Items (project detail → work-item
   list + work-item detail). WI-0001 must render without a Demo Evidence page and without a manual
   project pre-selection workaround.
2. **Which formal pages must show agent executions?** Agent Executions (per-execution list, with
   correlation back to the work item / workflow).
3. **Which formal pages must show the workflow trace?** Workflows / Task Graph (workflow id /
   correlation id, stage sequence, completed stages, status, `production_executed=false`).
4. **Which formal pages must show QA/code outputs?** QA and Code / Workspace (QA run summary +
   status; code workspace/output summary; linked to work item or workflow).
5. **Which formal pages must show audit/evidence?** Audit / Evidence (`work_item_created` and any
   workflow audit references, event type + count + timestamp).
6. **How is the Demo Evidence page downgraded?** Relabel as a Developer Diagnostic / Evidence Debug
   view and remove it from the operator's staging-acceptance navigation path (see policy doc). No
   acceptance decision may reference it.
7. **How does Test/QA verify the formal pages?** Unit + component + API-contract tests in the
   test/QA phase, with a data-fixture strategy, before any staging redeploy. See
   [product-ui-test-qa-remediation-plan.md](product-ui-test-qa-remediation-plan.md).
8. **How does Staging verify the formal pages?** Operator re-review of the formal pages only (no
   Demo Evidence acceptance), with recorded staging evidence. See
   [product-ui-staging-redeploy-plan.md](product-ui-staging-redeploy-plan.md) and
   [operator-product-ui-rereview-plan.md](operator-product-ui-rereview-plan.md).
9. **When are external integrations enabled?** In a separate future Step 65 (controlled staging
   external integration), against sandbox/non-production resources — not in this stage and not in
   the 64E.4x remediation. See
   [controlled-staging-external-integration-roadmap.md](controlled-staging-external-integration-roadmap.md).
10. **When may Step 64F resume?** Only after the formal product UI is remediated in test/QA
    (64E.4B), redeployed to staging (64E.4C), and the operator re-reviews and accepts the formal
    pages (64E.4D). Until then Step 64F stays BLOCKED.

## Required formal-page remediation (summary)
- **Projects / Work Items** — render the demo project and WI-0001 with lifecycle/status; no manual
  pre-selection workaround; link to related execution/evidence.
- **Agent Executions** — a real product page listing intake→requirement→development→qa→devops
  executions with status and workflow correlation.
- **Workflows / Task Graph** — replace the stub with a workflow/stage view (id, stage sequence,
  status, `production_executed=false`).
- **QA / Code** — wire QA run + code workspace summaries into the formal QA and Code pages.
- **Audit / Evidence** — consume per-work-item events in a formal audit page, not only aggregate
  metrics.
- **Safety Center** — keep surfacing `production_executed_true_count=0`, disabled/labeled live
  integrations, disabled external write, disabled production deploy/sync.
- **Empty states** — every page must render a meaningful empty state when a data source is empty,
  distinct from an error, so absence of data is not read as a broken page.

Per-page purpose / operator-question / evidence / endpoints / behavior / empty-state / gap /
test-acceptance / staging-acceptance detail lives in
[formal-admin-console-page-evidence-map.md](formal-admin-console-page-evidence-map.md).

## What this stage does NOT do
No code change, no UI implementation, no backend implementation, no image rebuild, no container
restart, no `docker compose up/down`, no workflow execution, no demo-data reset, no DB mutation,
no production deploy/sync/secret, no GitHub live write, no image push, no registry login, no
external Slack/GitHub/LLM call, no public port exposure, no volume deletion. **No implementation
is claimed here** — this is a plan only.

## Status
- Step 64E: **FAILED_STAGING_REPRESENTATIVENESS**. Step 64F: **BLOCKED**.
- Demo Evidence page: **developer diagnostic only — not staging acceptance**.
- **No production action**; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
