# Staging Admin Console Operator Re-Review Plan (Step 64E.1)

> **Staging only — non-production only. No production action. No production secret. No external write.**

The Step 64E.1 remediation deployed the full React Admin Console. **The operator must re-review**
to decide whether the per-item demo evidence is now usable. Claude Code cannot self-confirm this.

> **Re-review result (Step 64E.2):** the operator re-reviewed and the verdict is **NOT_USABLE** —
> WI-0001, agent executions, workflow, QA/code, and audit are **still not visible** in the
> deployed UI (`production_executed_true_count=0`). Deploying the bundle was not sufficient; the
> next blocker is the Admin Console demo-evidence UI/API integration. See
> [operator-rereview-result-after-react-bundle-remediation.md](operator-rereview-result-after-react-bundle-remediation.md)
> and [admin-console-demo-evidence-ui-blocker.md](admin-console-demo-evidence-ui-blocker.md).

## Access
```bash
ssh -i ~/.ssh/ai-agents-staging/staging_10_0_1_32 -L 18000:127.0.0.1:18000 itadmin@10.0.1.32
```
Open `http://localhost:18000/admin` — you should now see the full React app (more tabs than the
previous 18). **Navigate via the top tabs** (client-side routing). Do **not** hard-refresh a
sub-page or bookmark a deep link — those 404 (SPA-on-StaticFiles limitation; see
[staging-admin-console-remediation-known-gaps.md](staging-admin-console-remediation-known-gaps.md)).

## Re-review items (the ones that failed the first walkthrough)
Confirm each is now visible/usable, and record yes/no:
1. **Work item identity** — a tab showing `WI-0001` "Create user CRUD API" (e.g. Multi-project
   Delivery / Projects / Task Graph).
2. **Agent executions** — the intake→requirement→development→qa→devops pipeline (e.g. Workspace
   Execution / Task Graph / Operator Console).
3. **Workflows** — the 2 completed workflows.
4. **QA / code output** — QA runs / code workspaces.
5. **Audit / evidence** — the `work_item_created` event / audit view.
6. Re-confirm the still-good items: metrics (projects 1 / work items 1), Safety Center
   (`production_executed_true_count=0`), read-only.

## Verdict
Record in [operator-walkthrough-confirmation-form.md](operator-walkthrough-confirmation-form.md)
item 15: **usable / usable with gaps / not usable**.

## Status handling
- If the operator accepts → Step 64E can move off `FAILED_OPERATOR_VALIDATION`; Step 64F may
  proceed.
- If not → Step 64E stays failed; further UI work is needed. Claude Code must not self-approve.
- Until the operator responds, **Step 64E stays FAILED_OPERATOR_VALIDATION and Step 64F stays
  BLOCKED.**

## Safety
No production action; no production secret; no external write; no public exposure; live
integrations disabled/mocked; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
