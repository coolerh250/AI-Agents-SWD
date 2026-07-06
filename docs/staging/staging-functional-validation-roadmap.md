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

## Step 65E — Controlled Notification Validation
- **Purpose:** validate notification delivery to a test channel.
- **Allowed:** test-channel sends. **Forbidden:** production channels / real users.
- **Op-auth:** required. **User validation:** operator confirms test-channel delivery.
- **Acceptance:** recorded test delivery. **Abort:** any production channel.

## Step 65F — Controlled LLM Validation
- **Purpose:** validate live LLM calls against a non-prod key/quota.
- **Allowed:** bounded live calls. **Forbidden:** production keys, unbounded spend, production data.
- **Op-auth:** required (authorize key + quota). **User validation:** operator confirms usage.
- **Acceptance:** recorded live call within quota. **Abort:** quota breach / production key.

## Step 65G — End-to-End Staging Workflow Validation
- **Purpose:** run a fresh workflow from intake through agents → QA/code → audit, visible on the
  **formal** Admin Console pages.
- **Allowed:** controlled workflow run (mock or scoped-sandbox integrations). **Forbidden:**
  production action.
- **Op-auth:** required (authorize the run). **User validation:** operator validates E2E output on
  formal pages + external artifacts.
- **Acceptance:** end-to-end evidence on formal pages; `production_executed_true_count=0`.
  **Abort:** any production side effect.

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
