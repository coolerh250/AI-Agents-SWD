# Staging Functional Gap Register (Step 65A)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Read-only assessment / documentation only — no runtime change in this stage.**

Blockers and gaps to staging functional acceptance, grouped by category, derived from
[staging-functional-coverage-matrix.md](staging-functional-coverage-matrix.md).

## Functional gaps
- **No fresh end-to-end workflow from a real intake.** All agent/workflow/QA/code/audit evidence is
  seeded/mock (`/workflow/test` + delivery seed), not a run started from intake. → 65G.
- **Workflow resume / cancel / abort / ignore-after-abort** exercised only in tests, not staging. →
  65H.
- **Approval paths (required / granted / denied / expired)** exercised only in tests. → 65H.
- **Retry / DLQ / manual replay / terminal-failure** exercised only in tests. → 65H.

## Integration gaps
- **GitHub:** ~~dry-run/mock only; no controlled sandbox write validated~~ → **RESOLVED (65D)**:
  real draft PR #15 created in `AI-Agents-SWD-sandbox` via the controlled path (a Step 59 no-commit
  flow gap was fixed); reset to safe; `production_executed_true_count=0`.
- **Notification (Slack/Discord):** ~~**PENDING_65E**~~ → **VALIDATED**: one real `[STAGING]` test
  message sent to `MySanbox`/`#general` via the discord-gateway controlled path; reset to safe;
  `production_executed_true_count=0`; operator confirmed **VISIBLE**. → see
  [controlled-notification-validation-report.md](controlled-notification-validation-report.md).
- **LLM:** **PENDING_65F** — `llm_provider=mock`; key is a configured reference present / not yet
  validated; no live call has occurred (`llm_real_enabled=false`). → 65F.
- **Container registry sandbox:** not set up. → 65B/65D.

## Credential gaps
- No staging sandbox credentials provisioned for GitHub / notification / LLM; `secret_provider` is
  `mock-vault`. A staging secret store + credential setup is required. → 65C.
- **Step 65B note:** the integration + secret-backend plans now exist
  ([controlled-external-integration-plan.md](controlled-external-integration-plan.md),
  [staging-secret-backend-plan.md](staging-secret-backend-plan.md)); credentials are still not
  provisioned (that is 65C, operator-authorized).

## Operator authorization gaps
- Operator actions are disabled in staging (`operator_actions_disabled`), so operator-submitted
  intake, approvals, and governed dispatch cannot be exercised without explicit operator
  authorization. → 65G/65H.
- Live GitHub write / notification send / LLM call each require explicit operator authorization
  before enablement. → 65D/65E/65F.

## UI / operator visibility gaps
- **SPA deep-link hard-refresh 404** — accepted non-blocking gap; navigate via tabs.
- New end-to-end workflow evidence must render on the **formal** pages (not Demo Evidence) for
  operator visual validation. → 65G.

## Operations resilience gaps
- **stop/start, rollback, restore** not yet rehearsed (64F.4 paused). → future 64F.
- Backup/DR exercised only in tests, not staging. → future 64F / 65H.

## Production-readiness gaps
- Production deploy/sync/merge remain disabled by design; controlled external integration must be
  validated **before** any production planning. Production readiness is **not** in scope for Step
  65 and is not decided by Claude Code.

## Blocking vs non-blocking
- **Blocking for staging functional acceptance:** fresh E2E workflow (65G); failure/governance in
  staging (65H); at least the controlled integrations the operator scopes in (65D/65E/65F) with
  credentials (65C).
- **Non-blocking (accepted):** SPA deep-link 404; capabilities the operator explicitly defers.

## Posture
Read-only assessment only. No runtime change, no workflow execution, no integration enablement, no
secret creation, no production action; `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production secret. No external write._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
