# Operator Walkthrough SOP (Step 64E)

> **Staging only — non-production only. No production action. No production secret. No external write.**

## Purpose
A step-by-step SOP for an operator to access the **staging** AI Agents Platform, verify system
health, review the seeded demo (project → work item → agent execution → audit → metrics), and
confirm the safety posture — without performing any production action.

## Scope
Staging runtime on `10.0.1.32` (`agentai-swd-stage`) only. **Non-production.** This SOP is for
inspection/acceptance; it does not deploy, approve, or mutate production anything.

## Staging-only statement
Everything below is staging/non-production. Live GitHub / Slack (Discord) / LLM integrations
are disabled or mocked. `production_executed_true_count=0`. Claude Code does not decide
production readiness.

## Prerequisites
- SSH access to `itadmin@10.0.1.32` (key-based). If you lack the session key, see
  [operator-access-troubleshooting.md](operator-access-troubleshooting.md) and
  [staging-operator-access-validation.md](staging-operator-access-validation.md) for alternatives.
- A local web browser.

## Step 1 — open the SSH local port-forward tunnel
```bash
ssh -i ~/.ssh/ai-agents-staging/staging_10_0_1_32 -L 18000:127.0.0.1:18000 itadmin@10.0.1.32
```
Leave this session open. (If local port 18000 is busy, use `-L 18080:127.0.0.1:18000` and use
`localhost:18080` below.)

## Step 2 — open the Admin Console (first page)
Open **`http://localhost:18000/admin`** — it redirects to `/admin/` and shows
**"Admin Console v0 — read-only"** (the Overview / Executive Overview page).
Operator URL: `http://localhost:18000/admin`.

## Step 3 — confirm system health
On the host (or via the tunnel), the orchestrator health endpoint returns 200:
`http://localhost:18000/health` → `200`. The Overview page reflects service/workflow status.

## Walkthrough sequence (expected observations)
Follow [operator-admin-console-navigation-guide.md](operator-admin-console-navigation-guide.md)
page by page:
1. **Overview / Dashboard** — platform + delivery status at a glance.
2. **Projects / Work Items** — the demo project **SaaS User Management Module** with work item
   **WI-0001 "Create user CRUD API"**.
3. **Agent Executions** — the intake → requirement → development → qa → devops pipeline, all
   completed (10 executions).
4. **Workflows / QA / Code** — 2 workflows completed; 2 QA runs; 2 code workspaces.
5. **Audit / Evidence** — `work_item_created` event; audit log total grew (≈60).
6. **Operational Metrics** — project=1, work items=1, `production_executed_true_count=0`.
7. **Safety Posture** — production toggles false; see
   [operator-safety-check-guide.md](operator-safety-check-guide.md).

## Safety checks
Confirm `production_executed_true_count=0` and all live integrations disabled via
[operator-safety-check-guide.md](operator-safety-check-guide.md).

## Known gaps
Read [operator-known-gaps-and-limitations.md](operator-known-gaps-and-limitations.md): Release
Governance empty (delivery dispatch gated), communication-gateway PyYAML gap, Vault dev/mock,
HTTP-only tunnel, LLM/GitHub/Slack disabled.

## What the operator must NOT do
See [operator-do-not-execute-list.md](operator-do-not-execute-list.md).

## Stop condition
Stop after confirming the acceptance checklist
([operator-acceptance-checklist.md](operator-acceptance-checklist.md)). Close the browser tab
and end the SSH session (`Ctrl-D`) to close the tunnel; local port 18000 is released.

## Support / escalation
For access or runtime issues, follow
[operator-access-troubleshooting.md](operator-access-troubleshooting.md) (collect only
non-secret diagnostics). Do not attempt to fix runtime gaps or bypass auth; record and escalate.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
