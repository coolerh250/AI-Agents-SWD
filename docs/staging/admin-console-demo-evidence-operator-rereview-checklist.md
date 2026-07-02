# Admin Console Demo Evidence Operator Re-Review Checklist (Step 64E.3B)

> **Staging only — non-production only. No production action. No production secret. No external write.**

For the operator to re-review the remediated Admin Console. Claude Code cannot self-accept; only
the operator's verdict counts.

## Access
```bash
ssh -i ~/.ssh/ai-agents-staging/staging_10_0_1_32 -L 18000:127.0.0.1:18000 itadmin@10.0.1.32
```
Open `http://localhost:18000/admin`, then click the **"Demo Evidence"** tab (second in the top
nav). Navigate via tabs — do not hard-refresh a sub-route (SPA deep-links 404).

## Re-review items (record yes/no)
On the Demo Evidence page, confirm each section shows data:
1. **Demo Project** — "SaaS User Management Module" (nonprod, production_allowed false).
2. **Demo Work Items** — `WI-0001` "Create user CRUD API" (lifecycle created, production_effect false).
3. **Agent Executions** — rows for intake / requirement / development / qa / devops (status completed).
4. **Workflows** — `demo-crud-userapi` (+ `demo-crud-001`), stage completed, production_executed false.
5. **QA Runs / Code Workspaces** — a QA count and code workspace rows (QA per-run rows may be
   empty — see known gaps).
6. **Audit / Evidence** — `work_item_created` event for the demo work item.
7. **Safety Posture** — `production_executed_true_count: 0`.

## Verdict
Record in [operator-walkthrough-confirmation-form.md](operator-walkthrough-confirmation-form.md)
item 15: **usable / usable with gaps / not usable**, and note any section still not visible.

## Status handling
- Operator accepts → Step 64E can move off `FAILED_OPERATOR_VALIDATION`; Step 64F may proceed.
- Operator rejects → Step 64E stays failed; further UI work needed. Claude Code must not
  self-accept.
- Until the operator responds, **Step 64E stays FAILED_OPERATOR_VALIDATION and Step 64F stays
  BLOCKED.**

## Safety
No production action; no production secret; no external write; no public exposure; live integrations
disabled/mocked; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
