# Product UI Staging Redeploy Plan (Step 64E.4C, planned)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Planning only — no rebuild, restart, or redeploy is performed in this stage.**

Defines the future **Step 64E.4C** redeploy of the test-passed formal product UI to staging on
`10.0.1.32`, gated on the 64E.4B test/QA gate passing.

## Precondition
- Step 64E.4B test/QA gate passed
  ([product-ui-test-qa-remediation-plan.md](product-ui-test-qa-remediation-plan.md)): all
  unit/component/contract tests green; every evidence type renders on its formal page in tests.

## Redeploy target
- Host `10.0.1.32`, staging repo `/data/ai-agents-staging/AI-Agents-SWD`, project
  `aiagents-staging`, loopback-only host ports (`+10000` offset), orchestrator `127.0.0.1:18000`.
- Rebuild **only the orchestrator** image (in-image Vite build) and `up -d orchestrator`. No
  `down -v`, no volume/DB reset, **no image push**, no other services rebuilt.

## Formal pages to validate (no Demo Evidence acceptance)
- Projects / Work Items (WI-0001 via normal navigation).
- Agent Executions (pipeline executions).
- Workflows / Task Graph (`production_executed=false`).
- QA / Code (QA + code summaries).
- Audit / Evidence (`work_item_created` event).
- Operational Metrics (aggregates consistent with per-item pages).
- Safety Center (`production_executed_true_count=0`, integrations disabled/labeled).
- Release Governance (release actions gated/disabled).
- **The Demo Evidence page must NOT be used for acceptance** and should be relabeled/hidden per
  [demo-evidence-page-diagnostic-only-policy.md](demo-evidence-page-diagnostic-only-policy.md).

## Record staging evidence
- Record deployed commit + bundle hash, endpoint 200 checks, and which formal page each evidence
  type rendered on.
- Record safety posture (`production_executed_true_count=0`, disabled/labeled integrations).
- Note remaining gaps (e.g. SPA deep-link 404 if unresolved).
- No secrets in the evidence record; do not print `.env.staging.local`.

## Handoff
Proceeds to Step 64E.4D operator product-UI re-review
([operator-product-ui-rereview-plan.md](operator-product-ui-rereview-plan.md)). **Claude Code does
not self-accept operator usability.**

## Executed in Step 64E.4C
This redeploy was executed: staging `10.0.1.32` synced 3ace806 → **44f9a40**; **orchestrator
rebuilt + recreated only**; `/health` 200, `/admin/` 200 (bundle `index-B4s3Ud5S.js`),
`/operations/safety` `production_executed_true_count=0`; all formal-page endpoints returned the
demo data. Result **PASS_WITH_GAPS** (SPA deep-link 404 carry-over). See
[product-ui-staging-redeploy-report.md](product-ui-staging-redeploy-report.md). **Ready for
operator product UI re-review (Step 64E.4D)** — not operator acceptance.

## Status
- Step 64E: **FAILED_STAGING_REPRESENTATIVENESS** (until operator accepts formal pages in 64E.4D).
- Step 64F: **BLOCKED**.
- Demo Evidence page: **diagnostic only — not staging acceptance**.
- **No production action**; `production_executed_true_count=0`. **No implementation claimed.**

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
