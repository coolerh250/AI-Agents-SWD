# Operator Product UI Re-review Plan (Step 64E.4D, planned)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Planning only — no implementation, rebuild, or acceptance decision is made here.**

Defines the future **Step 64E.4D** operator re-review of the **formal product pages** (not the Demo
Evidence page), after the 64E.4C staging redeploy.

## Readiness (after Step 64E.4C)
The tested formal pages are now **deployed on staging** (`10.0.1.32`, bundle `index-B4s3Ud5S.js`;
Step 64E.4C redeploy, PASS_WITH_GAPS): Projects/Work Items (`/delivery`) auto-loads WI-0001; Agent
Executions (`/agent-executions`); Workflows/Task Graph (`/task-graph`); QA/Code (`/qa-code`);
Audit/Evidence (`/audit-evidence`); Safety Center (`/safety`). All formal-page endpoints returned
the demo data and `production_executed_true_count=0`. **This re-review (Step 64E.4D) is now ready
to run** — see [product-ui-operator-rereview-instructions.md](product-ui-operator-rereview-instructions.md).
Claude Code does not decide acceptance.

## Access
`ssh -i ~/.ssh/ai-agents-staging/staging_10_0_1_32 -L 18000:127.0.0.1:18000 itadmin@10.0.1.32` then
open `http://localhost:18000/admin`. Navigate via the formal top-nav tabs (not deep-link
hard-refresh, until the SPA deep-link gap is resolved).

## Operator re-review checklist (formal pages only)
- [ ] **Projects / Work Items** — demo project + `WI-0001` `Create user CRUD API` with status,
      reached via normal navigation (no Demo Evidence page, no manual workaround).
- [ ] **Agent Executions** — intake → requirement → development → qa → devops executions with
      status + workflow correlation.
- [ ] **Workflows / Task Graph** — workflow/stage trace with `production_executed=false`.
- [ ] **QA / Code** — QA run summary/status + code workspace/output summary.
- [ ] **Audit / Evidence** — `work_item_created` event with type + timestamp.
- [ ] **Safety Center** — `production_executed_true_count=0`; live integrations disabled/labeled;
      external write disabled; production deploy/sync disabled.
- [ ] **Release Governance** — release actions gated/disabled in staging.
- [ ] **Demo Evidence page NOT used** for this acceptance (relabeled/hidden as diagnostic).

## Pass / fail rules
- **PASS** — every required evidence type is visible on its **formal page** via normal navigation,
  and the safety posture shows `production_executed_true_count=0`.
- **PASS_WITH_ACCEPTED_GAPS** — all required evidence visible on formal pages; only gaps explicitly
  listed in the accepted-gaps policy remain, and the operator accepts them.
- **FAIL** — any required evidence type is missing from its formal page, only visible via the Demo
  Evidence page / a diagnostic view, or reachable only via an undocumented workaround.

## Accepted-gaps policy
- A gap is acceptable only if: (1) it does not hide a required evidence type from its formal page,
  (2) it is documented with a workaround, and (3) the operator explicitly accepts it.
- Candidate accepted gaps: SPA deep-link 404 (navigate via tabs); QA `validation_runs` per-row
  count-only detail — **only if** the summary still renders on the formal QA page.
- Diagnostic-page-only visibility is **never** an accepted gap.

## Outcome handling
- On **PASS / PASS_WITH_ACCEPTED_GAPS**: record the operator's verdict; Step 64E may then move off
  `FAILED_STAGING_REPRESENTATIVENESS` and Step 64F may be considered for unblocking (separate
  decision).
- On **FAIL**: return to Step 64E.4B test/QA remediation.
- **Claude Code records the operator's verdict; it does not decide operator acceptance and does not
  decide production readiness.**

## Status
- Step 64E: **FAILED_STAGING_REPRESENTATIVENESS** (until operator accepts here). Step 64F: **BLOCKED**.
- Demo Evidence page: **diagnostic only — not staging acceptance**.
- **No production action**; `production_executed_true_count=0`. **No implementation claimed.**

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
