# Product UI Staging Redeploy Report (Step 64E.4C)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Staging redeploy of the Step 64E.4B tested UI — orchestrator only. No production action occurred.**

Records the redeploy of the test-passed formal Admin Console product UI to the staging host
`10.0.1.32`, so the operator can re-review WI-0001, agent executions, workflow, QA/code,
audit/evidence, and safety posture on the **formal product pages** (not the diagnostic Demo
Evidence page).

## Overall result
- Overall result: **PASS_WITH_GAPS** — staging repo synced to the tested commit; **orchestrator
  rebuilt + recreated only**; Admin Console reachable; all formal-page routes are in the deployed
  bundle and all read-only endpoints return the demo data; `production_executed_true_count=0`. One
  carry-over gap: SPA deep-link hard-refresh 404 (navigate via tabs).
- **Ready for operator product UI re-review** (Step 64E.4D). This is **not** operator acceptance.

## Redeploy actions
- **Staging host:** `10.0.1.32`, repo `/data/ai-agents-staging/AI-Agents-SWD`, project
  `aiagents-staging`.
- **Repo sync:** `git pull --ff-only origin main` → **3ace806 → 44f9a40** (fast-forward; no hard
  reset; no evidence/volume deletion).
- **Services rebuilt:** `orchestrator` only (in-image Vite build of the Admin Console bundle).
- **Services restarted:** `orchestrator` only (`up -d orchestrator`); postgres/redis only waited
  on for health (not recreated).
- **Volume/data changes:** none. **Workflow re-run:** none. **Image push:** none. No `down`, no
  `down -v`, no volume/DB reset.

## Runtime validation
- `/health`: **200**.
- `/admin`: **307 → `/admin/` 200** (trailing-slash redirect; SPA index served).
- `/operations/safety`: **200**, `production_executed_true_count=0`;
  `github_external_write_enabled=false`, `discord_external_send_enabled=false`,
  `llm_external_call_enabled=false`.
- **Orchestrator status:** `running (healthy)`.
- **Deployed Vite bundle:** `/admin/assets/index-B4s3Ud5S.js` — contains the formal routes
  (`agent-executions`, `qa-code`, `audit-evidence`) and nav labels ("Agent Executions", "QA /
  Code", "Audit / Evidence", "Projects / Work Items", "Diagnostics (Demo Evidence)").

## Formal-page technical validation
See [product-ui-staging-technical-validation.md](product-ui-staging-technical-validation.md) and
[product-ui-formal-page-staging-evidence.md](product-ui-formal-page-staging-evidence.md). All
read-only endpoints returned the Step 64D demo data (delivery project + WI-0001, 10 agent
executions, 2 workflows `production_executed=false`, 2 QA runs, 2 code workspaces, 1
`work_item_created` audit event).

## Staging acceptance boundary
This stage technically validated the routes/endpoints but **does not declare operator acceptance**.
Step 64E remains **FAILED_STAGING_REPRESENTATIVENESS (pending operator product UI re-review)**;
Step 64F remains **BLOCKED** until Step 64E.4D passes. The Demo Evidence / Diagnostics page is
**not an acceptance path**. Claude Code does not decide operator acceptance or production readiness.

## Safety posture
Staging redeploy completed. No production action; no production deploy/sync/secret; no external
write; no image push; no volume deletion; no public exposure (loopback + SSH tunnel only);
`production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
