# External Integration Authorization Gates (Step 65B)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Planning only — gates define authorization; nothing is executed by this document.**

Authorization gates for Step 65C–65I. Each step is default-off and runs only when the operator
explicitly authorizes it; sandbox / non-production only.

## Step 65C — Staging Secret & Credential Setup (completed — PASS_WITH_GAPS)
- **Operator authorization:** granted. **Resource:** env-file staging secret backend. **Credential
  ref:** the sandbox references in [staging-secret-backend-plan.md](staging-secret-backend-plan.md).
- **Allowed:** store sandbox references (existence only). **Forbidden:** production secrets;
  printing/committing secrets.
- **Success:** non-secret references + safe kill switches provisioned (never values); mock→sandbox
  toggle documented. **Failure:** any production secret or leaked value.
- **Rollback/disable:** remove/rotate references → mock. **Audit:** existence booleans. **User
  validation:** operator confirms credentials/resources.
- **Done:** env-file backend; references + safe defaults set; three secret values pending operator
  out-of-band entry; `production_executed_true_count=0`; no integration enabled. See
  [staging-secret-credential-setup-report.md](staging-secret-credential-setup-report.md).

## Step 65D — Controlled GitHub Sandbox Validation (completed — PASS)
- **Operator authorization:** granted. **Resource:** sandbox repo `coolerh250/AI-Agents-SWD-sandbox`.
  **Credential ref:** `SANDBOX_GITHUB_TOKEN` (the real live gate is `SANDBOX_GITHUB_LIVE` +
  `SANDBOX_GITHUB_TOKEN`, not the earlier-assumed `RUN_REAL_GITHUB_TEST`).
- **Allowed:** sandbox branch/commit/draft-PR/read/audit. **Forbidden:** merge, production/customer
  repo, release/tag, protected branch, image push.
- **Success:** recorded sandbox interaction; `production_executed_true_count=0`. **Failure:** any
  non-sandbox target.
- **Rollback/disable:** `SANDBOX_GITHUB_LIVE=false` / revoke token. **Audit:** PR/branch ref +
  result. **User validation:** operator verifies the sandbox artifact.
- **Done:** real draft **PR #15** created in the sandbox repo (draft=true, 1 commit); required an
  allowlist retarget (`022b518`), compose env wiring (`38e4fcd`), and a flow fix to commit an
  evidence file before opening the PR (`ea52208`); staging reset to safe;
  `production_executed_true_count=0`. See
  [controlled-github-sandbox-validation-report.md](controlled-github-sandbox-validation-report.md).

## Step 65E — Controlled Notification Validation (completed — PASS)
- **Operator authorization:** granted. **Resource:** `MySanbox` / `#general` Discord test channel.
  **Credential ref:** `DISCORD_TEST_CHANNEL_ID` + `DISCORD_TEST_GUILD_ID` + `DISCORD_BOT_TOKEN`.
- **Allowed:** `[STAGING]` test-channel sends. **Forbidden:** production channels, real-user DMs,
  spam, secrets in messages.
- **Success:** recorded test delivery. **Failure:** any production channel.
- **Rollback/disable:** `RUN_REAL_DISCORD_TEST=false` / revoke. **Audit:** channel ref + delivery
  result. **User validation:** operator confirms delivery.
- **Done:** real `[STAGING]` test message sent to the non-production Discord test channel via the
  controlled path; required a compose env-wiring fix for `discord-gateway`
  (`DISCORD_TEST_CHANNEL_ID`/`DISCORD_TEST_GUILD_ID`) and a scoped, temporary
  `SECRET_PROVIDER=env` override for that one container (reset after); staging reset to safe;
  `production_executed_true_count=0`. Operator confirmed **VISIBLE**. See
  [controlled-notification-validation-report.md](controlled-notification-validation-report.md).

## Step 65F — Controlled LLM Validation (completed — PASS_WITH_GAPS, corrected by 65F-C)
- **Operator authorization:** granted. **Resource:** non-prod Anthropic key + $1 per-run cap.
  **Credential ref:** `ANTHROPIC_API_KEY`.
- **Allowed:** bounded live calls. **Forbidden:** production keys/data, unbounded spend, auto
  production action, external write from LLM output.
- **Success:** recorded call within quota; `production_executed_true_count=0`. **Failure:** quota
  breach / production key.
- **Rollback/disable:** `LLM_PROVIDER=mock` / revoke key. **Audit:** call metadata + cost. **User
  validation:** operator confirms usage.
- **Done:** one official, audited, bounded call (model `claude-haiku-4-5-20251001`, 708 tokens,
  actual cost $0.03096) via the platform's Stage-35 plan-only real-LLM rail; required an
  `ANTHROPIC_MODEL` env override (the hardcoded default model name was stale) — no source change;
  real-call flags were ephemeral (scoped to one `docker compose exec` process only), so nothing
  persistent needed resetting; `production_executed_true_count=0`. See
  [controlled-llm-validation-report.md](controlled-llm-validation-report.md).
- **Governance correction (65F-C):** two diagnostic probes preceded the official call, bypassing
  the platform budget/audit rail (disclosed, non-sensitive, negligible cost). Step 65F final status
  is **PASS_WITH_GAPS**, not a clean PASS; future direct diagnostic external calls are forbidden
  unless separately authorized. See
  [step65f-llm-validation-final-status.md](step65f-llm-validation-final-status.md) +
  [step65f-llm-guardrail-update.md](step65f-llm-guardrail-update.md).

## Step 65G — End-to-End Staging Workflow Validation
- **Operator authorization:** required (authorize the run). **Resource:** in-scope integrations (or
  mock). **Credential ref:** as scoped.
- **Allowed:** controlled E2E run. **Forbidden:** production action.
- **Success:** E2E evidence on **formal** pages; `production_executed_true_count=0`. **Failure:**
  any production side effect.
- **Rollback/disable:** abort run; disable integrations. **Audit:** workflow + agent + external
  evidence. **User validation:** operator validates E2E output.
- **65G.1 planned (completed):** grounded execution plan built; the operator authorizes 65G.2 via
  [e2e-staging-operator-authorization-template.md](e2e-staging-operator-authorization-template.md),
  which names: fresh intake, GitHub sandbox draft-PR (yes/no), Discord staging notification
  (yes/no), Anthropic budget/audit LLM calls (yes/no), max LLM call count, max LLM cost, max Discord
  sends, max GitHub draft-PR flows, and post-run UI validation. All real external calls go through
  the controlled rails (65D/65E/65F); direct diagnostic external calls forbidden unless separately
  authorized. See
  [e2e-staging-workflow-readiness-report.md](e2e-staging-workflow-readiness-report.md).
- **65G.2 executed (completed — PASS_WITH_OPERATOR_VALIDATION_PENDING):** one fresh intake drove the
  real 5-hop pipeline; the three controlled rails each ran once, correlated — controlled LLM call
  ($0.05073 ≤ $1), sandbox draft **PR #16** (no merge), one `[STAGING]` Discord send; 0 direct
  diagnostic calls; all flags reset; `production_executed_true_count=0`. Operator UI validation
  pending. See [e2e-staging-workflow-execution-report.md](e2e-staging-workflow-execution-report.md).

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
