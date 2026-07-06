# Staging Functional Validation Roadmap (Step 65A)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Roadmap / documentation only — no step below is executed in this stage.**

Defines the Step 65 functional-validation track (65B–65I) with per-step purpose, allowed/forbidden
actions, inputs, authorization, acceptance, exit, and rollback/abort. Each step runs only under
explicit operator authorization; sandbox/non-production only.

## Step 65A — Functional Coverage & Integration Readiness Assessment (this step)
- **Purpose:** inventory all functions, classify staging status, register gaps, define the roadmap.
- **Allowed:** read-only inspection + documentation. **Forbidden:** runtime change, workflow exec,
  integration enablement, secret creation, production action.
- **Acceptance:** the seven assessment docs + verifier PASS. **Exit:** operator confirms scope.

## Step 65B — Controlled Staging External Integration Plan (completed)
- **Purpose:** detailed plan for each in-scope integration (GitHub/notification/LLM/secret backend).
- **Allowed:** documentation. **Forbidden:** enabling integrations, storing secrets.
- **Inputs:** operator's in-scope integration list. **Op-auth:** required to set scope.
- **Acceptance:** per-integration plan with kill switches. **Exit/abort:** operator defers an
  integration.
- **Done:** operator scope `FULL_DOMAIN_MATRIX`; in-scope GitHub/notification/LLM/secret backend;
  deferred registry + cloud storage. Plans in
  [controlled-external-integration-plan.md](controlled-external-integration-plan.md) +
  [external-integration-authorization-gates.md](external-integration-authorization-gates.md) +
  [external-integration-user-input-checklist.md](external-integration-user-input-checklist.md).
  Planning only; no integration enabled; `production_executed_true_count=0`.

## Step 65C — Staging Secret & Credential Setup (completed — PASS_WITH_GAPS)
- **Purpose:** provision sandbox credentials in the staging secret store.
- **Allowed:** configure sandbox credentials (existence only). **Forbidden:** production secrets;
  printing/committing secrets.
- **Op-auth:** granted. **User validation:** operator confirms sandbox credentials/resources.
- **Acceptance:** credentials present (never values); mock→sandbox toggle documented. **Rollback:**
  remove/rotate to return to mock.
- **Done:** env-file backend; non-secret references + safe kill switches provisioned (owner/rotation
  = Zachary); three secret values pending operator out-of-band entry; no integration enabled;
  `production_executed_true_count=0`. See
  [staging-secret-credential-setup-report.md](staging-secret-credential-setup-report.md).

## Step 65D — Controlled GitHub Sandbox Validation (completed — PASS)
- **Purpose:** validate GitHub integration against a sandbox repo (draft PRs).
- **Allowed:** controlled sandbox-repo writes. **Forbidden:** production repo writes, protected-branch
  merges, image push.
- **Op-auth:** granted. **User validation:** operator can verify the sandbox artifact.
- **Acceptance:** recorded sandbox interaction; `production_executed_true_count=0`. **Abort:** any
  non-sandbox target.
- **Done:** real draft **PR #15** created in `coolerh250/AI-Agents-SWD-sandbox` (draft, 1 commit,
  no merge) via the full controlled path; a Step 59 flow gap (no-commit → empty PR) was fixed;
  staging reset to safe; `production_executed_true_count=0`. See
  [controlled-github-sandbox-validation-report.md](controlled-github-sandbox-validation-report.md).

## Step 65D-C — 65C / 65D Integration Status Consolidation (completed)
- **Purpose:** consolidate 65C + 65D results, correct integration status, confirm safety posture.
- **Allowed:** documentation / reconciliation / read-only verification. **Forbidden:** GitHub write,
  notification send, LLM call, workflow execution, runtime change, production action.
- **Done:** GitHub sandbox **VALIDATED** (token gap **RESOLVED_BY_65D**); notification **PENDING_65E**;
  LLM **PENDING_65F**; no new external write; `production_executed_true_count=0`. See
  [step65c-65d-integration-status-consolidation.md](step65c-65d-integration-status-consolidation.md).

## Step 65E — Controlled Notification Validation (completed — PASS)
- **Purpose:** validate notification delivery to a test channel.
- **Allowed:** test-channel sends. **Forbidden:** production channels / real users.
- **Op-auth:** granted. **User validation:** operator confirmed test-channel delivery (`VISIBLE`).
- **Acceptance:** recorded test delivery. **Abort:** any production channel.
- **Done:** one real `[STAGING]` test message sent to `MySanbox`/`#general` via the discord-gateway
  controlled path (`external_sent=true`); reset to safe; `production_executed_true_count=0`;
  operator confirmed **VISIBLE**. See
  [controlled-notification-validation-report.md](controlled-notification-validation-report.md).

## Step 65F — Controlled LLM Validation (completed — PASS_WITH_GAPS, corrected by 65F-C)
- **Purpose:** validate live LLM calls against a non-prod key/quota.
- **Allowed:** bounded live calls. **Forbidden:** production keys, unbounded spend, production data.
- **Op-auth:** granted (key + $1 per-run cap). **User validation:** technical delivery documented
  (metadata + audit trail); no operator-visible Admin Console surface for this call (see known
  gaps).
- **Acceptance:** recorded live call within quota. **Abort:** quota breach / production key.
- **Done:** one official, audited, bounded Anthropic call (`claude-haiku-4-5-20251001`, 708 tokens,
  actual cost $0.03096, well under the $1 cap) via the Stage-35 plan-only real-LLM rail;
  `plan_only=true`, `requires_human_review=true`, `production_executed=false`;
  `production_executed_true_count=0`. See
  [controlled-llm-validation-report.md](controlled-llm-validation-report.md).
- **Step 65F-C correction:** two diagnostic probes bypassed the budget/audit rail before the
  official call (disclosed, non-sensitive, negligible cost) — Step 65F final status is
  **PASS_WITH_GAPS**; LLM integration status is **VALIDATED_WITH_GOVERNANCE_GAP**. See
  [step65f-llm-validation-final-status.md](step65f-llm-validation-final-status.md).

## Step 65F-C — LLM Diagnostic Exception & Guardrail Consolidation (completed)
- **Purpose:** formally reconcile the 65F diagnostic-probe disclosure and update future guardrails.
- **Allowed:** documentation / reconciliation / guardrail update. **Forbidden:** any new LLM call,
  GitHub write, notification send, workflow execution, runtime change.
- **Done:** Step 65F corrected to PASS_WITH_GAPS; LLM integration status
  VALIDATED_WITH_GOVERNANCE_GAP; guardrail added — direct diagnostic external calls forbidden
  unless separately authorized; Step 65G preconditions updated accordingly;
  `production_executed_true_count=0`. See
  [step65f-llm-diagnostic-exception-record.md](step65f-llm-diagnostic-exception-record.md),
  [step65f-llm-guardrail-update.md](step65f-llm-guardrail-update.md),
  [step65f-to-step65g-precondition-update.md](step65f-to-step65g-precondition-update.md).

## Step 65G — End-to-End Staging Workflow Validation (READY_AFTER_GUARDRAIL_CONSOLIDATION)
- **Purpose:** run a fresh workflow from intake through agents → QA/code → audit, visible on the
  **formal** Admin Console pages.
- **Allowed:** controlled workflow run (mock or scoped-sandbox integrations). **Forbidden:**
  production action.
- **Op-auth:** required (authorize the run). **User validation:** operator validates E2E output on
  formal pages + external artifacts.
- **Acceptance:** end-to-end evidence on formal pages; `production_executed_true_count=0`.
  **Abort:** any production side effect.
- **Preconditions (added by 65F-C):** all GitHub writes / notifications / LLM calls exercised during
  the run must go through their respective platform-controlled rails; no direct diagnostic external
  calls without separate authorization; no untracked external calls. See
  [step65f-to-step65g-precondition-update.md](step65f-to-step65g-precondition-update.md).

### Step 65G.1 — E2E Workflow Readiness & Execution Plan (completed)
- **Purpose:** build a grounded, controlled, auditable E2E execution plan for 65G.2.
- **Allowed:** read-only inspection + planning. **Forbidden:** workflow execution, intake creation,
  GitHub write, Discord send, LLM call, runtime change, production action.
- **Done:** mapped the real fresh-intake entry (`/intake/mock` stream mode → `stream.tasks` →
  intake→requirement→development→qa→devops pipeline) and confirmed the pipeline's native
  integration points are mock/dry-run — so the three controlled rails (65D/65E/65F) must be invoked
  as separately-authorized correlated steps. Produced 8 planning docs (readiness report, test case,
  execution plan, integration guardrails, budget/call limits, Admin Console checklist, abort/reset
  plan, operator-authorization template); one tracked gap (confirm `workflow_state` visibility for a
  stream-mode intake). `production_executed_true_count=0`. See
  [e2e-staging-workflow-readiness-report.md](e2e-staging-workflow-readiness-report.md).
- **Step 65G status: READY_FOR_CONTROLLED_EXECUTION** (pending operator authorization for 65G.2 via
  [e2e-staging-operator-authorization-template.md](e2e-staging-operator-authorization-template.md)).

### Step 65G.2 — Controlled E2E Staging Workflow Execution (completed — PASS)
- **Purpose:** execute one controlled fresh-intake E2E run through the real pipeline + the three
  controlled rails.
- **Allowed:** 1 fresh intake, 1 LLM call (≤$1), 1 GitHub sandbox draft PR, 1 Discord `[STAGING]`
  send. **Forbidden:** production action; direct diagnostic calls; over-count.
- **Done:** fresh intake `step65g2-e2e-20260706074202` → 5-hop pipeline completed; controlled LLM
  call ($0.05073); sandbox draft **PR #16** (no merge); one `[STAGING]` Discord send; all correlated;
  flags reset; `production_executed_true_count=0`. See
  [e2e-staging-workflow-execution-report.md](e2e-staging-workflow-execution-report.md).

### Step 65G.2-V — Operator UI Validation Record (completed — PASS)
- **Purpose:** record the operator's formal UI validation of the 65G.2 evidence.
- **Allowed:** documentation only. **Forbidden:** any new external action / workflow / production
  action.
- **Done:** operator response **VISIBLE** on the formal Admin Console pages (not `/demo-evidence`);
  Step 65G.2 final status **PASS**; fresh E2E workflow **VALIDATED**; Admin Console formal evidence
  **OPERATOR_VISIBLE**; `production_executed_true_count=0`. See
  [e2e-staging-operator-ui-validation-record.md](e2e-staging-operator-ui-validation-record.md).

## Step 65H — Failure / Recovery / Governance Validation
- **Purpose:** exercise approval paths, cancel/abort, retry/DLQ/replay, failure evidence in staging.
- **Allowed:** controlled failure/governance scenarios. **Forbidden:** production action.
- **Op-auth:** required (authorize scenarios). **User validation:** operator authorizes each
  scenario.
- **Acceptance:** each path exercised + evidence recorded; safety preserved. **Abort:** unexpected
  production effect.

## Step 65I — Staging Functional Acceptance Report
- **Purpose:** consolidate results and request the operator's functional-acceptance verdict.
- **Allowed:** documentation. **Forbidden:** self-accepting acceptance.
- **Op-auth / user validation:** operator gives the acceptance verdict.
- **Acceptance:** operator verdict recorded (PASS / PASS_WITH_ACCEPTED_GAPS / FAIL). **Exit:** track
  complete.

## Gating
65B → 65C → (65D/65E/65F, in-scope only) → 65G → 65H → 65I. No staging functional acceptance until
65G + 65H pass and the operator gives the 65I verdict. Production readiness is **not** in scope.

## Posture
Roadmap only; nothing executed here. No runtime change, no integration enablement, no secret
creation, no production action; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
