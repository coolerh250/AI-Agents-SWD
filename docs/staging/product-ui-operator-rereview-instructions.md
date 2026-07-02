# Product UI Operator Re-review Instructions (Step 64E.4C → 64E.4D)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Instructions for the operator's formal-page re-review. Claude Code does not decide acceptance.**

The tested formal product UI is now deployed on staging (`10.0.1.32`, bundle `index-B4s3Ud5S.js`).
Use these steps to re-review the **formal product pages** — not the diagnostic Demo Evidence page.

## Access
1. Open the SSH tunnel from your workstation:
   `ssh -i <your key> -L 18000:127.0.0.1:18000 itadmin@10.0.1.32`
2. Browse to `http://localhost:18000/admin`.
3. **Navigate using the top-nav tabs** (do not hard-refresh a deep URL — see known gaps).

## Re-review checklist (formal pages only)
- [ ] **Projects / Work Items** (tab "Projects / Work Items", `/delivery`): demo project +
      **WI-0001 "Create user CRUD API"** visible without any manual click.
- [ ] **Agent Executions** (`/agent-executions`): the agent pipeline (10 executions) with status.
- [ ] **Workflows / Task Graph** (`/task-graph`): workflow/stage trace with
      `production_executed=false`.
- [ ] **QA / Code** (`/qa-code`): QA runs + code workspaces.
- [ ] **Audit / Evidence** (`/audit-evidence`): `work_item_created` event.
- [ ] **Safety Center** (`/safety`): `production_executed_true_count=0`; live GitHub/Discord/LLM
      disabled.
- [ ] **Diagnostics (Demo Evidence)** is last in nav and clearly diagnostic — **not** used for this
      acceptance.

## Verdict
Record one of: **usable** / **usable-with-accepted-gaps** / **not-usable**, per
[operator-product-ui-rereview-plan.md](operator-product-ui-rereview-plan.md). Accepted gaps must
not hide a required evidence type from its formal page.

## Boundary
Until you record acceptance in Step 64E.4D, Step 64E stays
**FAILED_STAGING_REPRESENTATIVENESS** and Step 64F stays **BLOCKED**. Claude Code must not
self-accept operator usability. No production action; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
