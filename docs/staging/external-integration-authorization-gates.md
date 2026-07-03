# External Integration Authorization Gates (Step 65B)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Planning only — gates define authorization; nothing is executed by this document.**

Authorization gates for Step 65C–65I. Each step is default-off and runs only when the operator
explicitly authorizes it; sandbox / non-production only.

## Step 65C — Staging Secret & Credential Setup
- **Operator authorization:** required. **Resource:** staging secret backend. **Credential ref:**
  the sandbox references in [staging-secret-backend-plan.md](staging-secret-backend-plan.md).
- **Allowed:** store sandbox references (existence only). **Forbidden:** production secrets;
  printing/committing secrets.
- **Success:** references present (never values); mock→sandbox toggle documented. **Failure:** any
  production secret or leaked value.
- **Rollback/disable:** remove/rotate references → mock. **Audit:** existence booleans. **User
  validation:** operator confirms credentials/resources.

## Step 65D — Controlled GitHub Sandbox Validation
- **Operator authorization:** required. **Resource:** sandbox repo. **Credential ref:** `GITHUB_TOKEN`.
- **Allowed:** sandbox branch/commit/draft-PR/read/audit. **Forbidden:** merge, production/customer
  repo, release/tag, protected branch, image push.
- **Success:** recorded sandbox interaction; `production_executed_true_count=0`. **Failure:** any
  non-sandbox target.
- **Rollback/disable:** `GITHUB_DRY_RUN=true` / revoke token. **Audit:** PR/branch ref + result.
  **User validation:** operator verifies the sandbox artifact.

## Step 65E — Controlled Notification Validation
- **Operator authorization:** required. **Resource:** test channel. **Credential ref:**
  `DISCORD_TEST_CHANNEL_ID` + token/webhook.
- **Allowed:** `[STAGING]` test-channel sends. **Forbidden:** production channels, real-user DMs,
  spam, secrets in messages.
- **Success:** recorded test delivery. **Failure:** any production channel.
- **Rollback/disable:** `RUN_REAL_DISCORD_TEST=false` / revoke. **Audit:** channel ref + delivery
  result. **User validation:** operator confirms delivery.

## Step 65F — Controlled LLM Validation
- **Operator authorization:** required. **Resource:** non-prod LLM key + quota. **Credential ref:**
  `LLM_API_KEY`.
- **Allowed:** bounded live calls. **Forbidden:** production keys/data, unbounded spend, auto
  production action, external write from LLM output.
- **Success:** recorded call within quota; `production_executed_true_count=0`. **Failure:** quota
  breach / production key.
- **Rollback/disable:** `LLM_PROVIDER=mock` / revoke key. **Audit:** call metadata + cost. **User
  validation:** operator confirms usage.

## Step 65G — End-to-End Staging Workflow Validation
- **Operator authorization:** required (authorize the run). **Resource:** in-scope integrations (or
  mock). **Credential ref:** as scoped.
- **Allowed:** controlled E2E run. **Forbidden:** production action.
- **Success:** E2E evidence on **formal** pages; `production_executed_true_count=0`. **Failure:**
  any production side effect.
- **Rollback/disable:** abort run; disable integrations. **Audit:** workflow + agent + external
  evidence. **User validation:** operator validates E2E output.

## Step 65H — Failure / Recovery / Governance Validation
- **Operator authorization:** required (authorize each scenario). **Resource:** staging runtime.
- **Allowed:** controlled failure/governance scenarios (approval, cancel/abort, retry/DLQ).
  **Forbidden:** production action; destructive teardown.
- **Success:** each path exercised + evidence; safety preserved. **Failure:** unexpected production
  effect.
- **Rollback/disable:** stop scenario; validate. **Audit:** per-scenario evidence. **User
  validation:** operator authorizes scenarios.

## Step 65I — Staging Functional Acceptance Report
- **Operator authorization:** the operator gives the verdict. **Resource:** consolidated evidence.
- **Allowed:** documentation. **Forbidden:** self-accepting acceptance; production readiness claim.
- **Success:** operator verdict recorded (PASS / PASS_WITH_ACCEPTED_GAPS / FAIL). **Failure:**
  operator withholds acceptance.
- **Audit:** acceptance record. **User validation:** operator verdict (required).

## Posture
Planning only. No integration enabled, no secret created, no external write, no runtime change, no
production action; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
