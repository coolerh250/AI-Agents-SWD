# Step 64 Staging Roadmap (Step 64A)

> **Staging only — non-production only. No production action. No production secret. No external write.**

The Step 64 staging demonstration mainline. **Staging target host: `10.0.1.32` · Access:
SSH (interactive credentials, never stored).** Each sub-stage is non-production; none
performs a production action.

| Stage | Title | Scope |
|---|---|---|
| **Step 64A** | Staging Architecture & Deployment Plan | **(this stage)** inventory + architecture + deployment/access plans + service inventory + Admin Console plan + demo workflow plan + information request + risk/safety plan + roadmap + verifier + test. Planning only — no deployment. |
| **Step 64B.1** | Authenticated Staging Host Preflight | **(completed)** key-based SSH read-only inventory of `10.0.1.32` (`agentai-swd-stage`): Ubuntu 24.04, 16 vCPU, 7.7 GiB RAM, `/data` 93 GB free; **Docker not installed** → `ready_for_runtime_bootstrap=false`. No install, no runtime deployment, no production action. |
| **Step 64B.2A** | Staging Host Runtime Preparation | **(completed)** under explicit operator authorization: installed Docker Engine `29.6.1` + Docker Compose v2 `v5.2.0` on `10.0.1.32`, enabled/started daemon, added `itadmin` to `docker` group, created `/data/ai-agents-staging`, `hello-world` validation-only. **No `docker compose up`; no AI Agents runtime deployed; no production action.** |
| **Step 64B.2B** | Staging Runtime Bootstrap | **(completed)** synced repo to `10.0.1.32` (`f43e163`), generated gitignored staging env, validated + brought up `docker-compose.staging.yml` (22 containers running), applied migrations, initialised streams; `/health` 200, Admin Console `/admin/` 200, `/operations/safety` `production_executed_true_count=0`. Live integrations disabled/mocked; demo workflow NOT run. No production action. |
| **Step 64C** | Admin Console Exposure | **(completed)** validated Admin Console reachable on `10.0.1.32`; SSH port-forward path validated end-to-end and **operator confirmed access from their own workstation**; inventoried 24 read-only routes (13 `/operations/*` endpoints probed 200); operator mutations gated (`operator_actions_disabled`); no public exposure. `STAGING_ADMIN_CONSOLE_EXPOSURE_VERIFY: PASS`. No production action. |
| **Step 64D** | Demo Workflow Seed & Execution | **(completed — PASS_WITH_GAPS)** seeded SaaS User Management Module + `WI-0001` "Create user CRUD API" (nonprod); ran mock agent workflow through intake→requirement→development→qa→devops (10 agent executions completed, 2 workflows, 2 QA runs); audit + metrics populated; `production_executed_true_count=0`. Gaps: delivery package/release candidate gated (operator auth disabled); gateway mock-intake PyYAML image bug (worked around). `STAGING_DEMO_WORKFLOW_VERIFY: PASS_WITH_GAPS`. No production action. |
| **Step 64E** | Operator Walkthrough SOP | **FAILED_OPERATOR_VALIDATION** — SOP **document completeness = PASS** (`OPERATOR_WALKTHROUGH_SOP_VERIFY: PASS`), but the **operator performed the walkthrough and judged the deployed console NOT USABLE**: work-item identity, agent executions, workflows, QA/code, and audit are not visible (deployed console is the zero-build fallback; full React bundle not built into the image). No production action. |
| **Step 64E-R** | Operator Walkthrough Revalidation & Status Correction | **(completed)** ran the operator walkthrough live; recorded result **NOT USABLE**; documented root cause + remediation ([staging-admin-console-deployment-gap.md](staging-admin-console-deployment-gap.md)); corrected the overclaimed "pages populated" docs. `OPERATOR_WALKTHROUGH_REVALIDATION_VERIFY: PASS`. No production action. |
| **Step 64E.1** | Admin Console React Bundle Remediation | **(completed — PASS_WITH_GAPS, remediation-prepared)** added a Vite build stage to the orchestrator Dockerfile; rebuilt + recreated the orchestrator on `10.0.1.32`; `/admin` now serves the full React bundle (all 23 routes; assets 200). Gaps: SPA deep-link 404; per-item render pending operator re-review; safety `result=warning` (mock-vault). `STAGING_ADMIN_CONSOLE_REACT_BUNDLE_REMEDIATION_VERIFY: PASS_WITH_GAPS`. **Step 64E stays FAILED_OPERATOR_VALIDATION; Step 64F stays BLOCKED** until operator re-review. No production action; no image push. |
| **Step 64E.2** | Operator Re-review Failure Recording | **(completed)** recorded the operator's re-review after the bundle remediation: **NOT_USABLE** — WI-0001, agent executions, workflow, QA/code, audit **still not visible**. Blocker is now the Admin Console demo-evidence UI/API integration, not deployment. `OPERATOR_REREVIEW_FAILURE_RECORDING_VERIFY: PASS`. **Step 64E stays FAILED_OPERATOR_VALIDATION; Step 64F stays BLOCKED.** Next: Admin Console Demo Evidence UI Remediation. No production action. |
| **Step 64F** | Deployment Management SOP | **BLOCKED** until the Admin Console deployment gap is remediated (demo evidence actually visible) **and** the operator re-reviews + accepts (or explicitly waives). rebuild / start / stop / teardown / upgrade SOP for staging. |
| **Step 64G** | Staging Acceptance & Production Gap Report | acceptance criteria + an explicit staging-vs-production gap report. NOT a production readiness sign-off. |

## Roadmap status
- **Step 63 — blocked / not approved / not ready** (Step 63A recommendation = `no_go`).
- **Step 64 — staging demonstration mainline started.**
- **Step 64A — staging architecture and deployment plan (this stage).**
- Tenant strategy note — recorded only, not scheduled.

Claude Code does not decide production readiness.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false -->
