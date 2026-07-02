# Staging Representativeness Policy (Step 64E.4A)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Planning/policy only — no code change, no rebuild, no restart in this stage.**

Defines what qualifies as valid staging validation for the Admin Console, so that a passing
staging review reflects the real operator product — not a purpose-built evidence view.

## What counts as staging validation
- Operator exercises the **formal product pages** (Projects / Work Items, Agent Executions,
  Workflows / Task Graph, QA / Code, Audit / Evidence, Operational Metrics, Safety Center, Release
  Governance) as a real operator would.
- Each required evidence type is visible **on its formal page** per
  [formal-admin-console-page-evidence-map.md](formal-admin-console-page-evidence-map.md).
- Evidence is reached through normal navigation — no special demo/diagnostic page, no manual
  pre-selection workaround, no direct API call.
- Safety posture is verifiable in the UI: `production_executed_true_count=0`, live integrations
  disabled or clearly labeled.

## What does NOT count as staging validation
- Data shown only via the **Demo Evidence page** or any developer/diagnostic view.
- Data confirmed only by calling `/operations/*` endpoints directly (backend-only proof).
- Data reachable only after an undocumented manual workaround.
- A "pages exist / routes present" claim without the per-item evidence rendered.

## Why demo/diagnostic pages are insufficient
A demo/diagnostic page can aggregate data from many sources to prove the data *exists*, but it does
not prove the *product* an operator uses is complete or usable. Accepting staging on a diagnostic
page would validate the wrong artifact and hide formal-page gaps. Diagnostic pages are for
developers debugging data flow; acceptance must be based on the formal product UI.

## When fake / mock data is allowed
- **Allowed now (this staging phase):** seeded demo project + work item + mock-workflow executions,
  mock vault, and disabled/mocked live integrations — sufficient to validate that the formal
  product pages render representative records.
- **Constraint:** mock data must flow through the **same product pages and endpoints** a real
  operator would use; it must not require a special page to be visible.
- **Not a substitute for:** controlled external integration validation, which is required before
  any production planning.

## When controlled external integration is required
- Before production planning, staging must additionally validate against **controlled,
  non-production external resources** (sandbox GitHub, test notification channel, non-production
  LLM) per
  [controlled-staging-external-integration-roadmap.md](controlled-staging-external-integration-roadmap.md)
  (Step 65A–65F).
- Staging must **not** use production secrets or production data. External integration is a
  separate, later, explicitly authorized phase — not part of 64E.4x.

## Status
- Step 64E: **FAILED_STAGING_REPRESENTATIVENESS** (formal pages incomplete → not representative).
- Step 64F: **BLOCKED**.
- Demo Evidence page: **diagnostic only — not staging acceptance**.
- **No production action**; `production_executed_true_count=0`. **No implementation claimed.**

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
