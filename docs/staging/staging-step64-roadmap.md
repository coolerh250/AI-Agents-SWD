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
| **Step 64C** | Admin Console Exposure | **(completed — operator confirmation pending)** validated Admin Console reachable on `10.0.1.32`; SSH port-forward path validated end-to-end from a client host; inventoried 24 read-only routes (13 `/operations/*` endpoints probed 200); operator mutations gated (`operator_actions_disabled`); no public exposure. `STAGING_ADMIN_CONSOLE_EXPOSURE_VERIFY: PASS_WITH_OPERATOR_CONFIRMATION_PENDING`. No production action. |
| **Step 64D** | Demo Workflow Seed & Execution | seed the SaaS User Management / Create user CRUD API demo, run the (mocked) agent workflow, produce Admin Console evidence. |
| **Step 64E** | Operator Walkthrough SOP | a step-by-step operator walkthrough of the staging system. |
| **Step 64F** | Deployment Management SOP | rebuild / start / stop / teardown / upgrade SOP for staging. |
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
