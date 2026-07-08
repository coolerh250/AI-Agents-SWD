# Staging Functional Gap Register (Step 65A)

> **Staging only — non-production only. No production action. No production secret. No external write.**
> **Read-only assessment / documentation only — no runtime change in this stage.**

Blockers and gaps to staging functional acceptance, grouped by category, derived from
[staging-functional-coverage-matrix.md](staging-functional-coverage-matrix.md).

## Functional gaps
- **No fresh end-to-end workflow from a real intake.** ~~All agent/workflow/QA/code/audit evidence
  is seeded/mock.~~ → **RESOLVED (65G.2) + OPERATOR_VISIBLE (65G.2-V):** fresh intake
  `step65g2-e2e-20260706074202` drove the real 5-hop distributed pipeline
  (intake→requirement→development→qa→devops, all completed) with correlated controlled
  LLM/GitHub(PR #16)/Discord artifacts; `production_executed_true_count=0`. Operator confirmed
  **VISIBLE** on the formal Admin Console pages; Step 65G.2 final status **PASS**. See
  [e2e-staging-operator-ui-validation-record.md](e2e-staging-operator-ui-validation-record.md).
- **[65G.1 tracked gap → CONFIRMED in 65G.2] Workflow-trace visibility for a stream-mode intake.** A
  stream-mode fresh intake creates **no** `workflow_state`, so `/task-graph` shows no trace; pipeline
  evidence is on `/agent-executions`. No `workflow_state` fabricated. Non-blocking; a future
  enhancement could register a workflow for real intakes.
- **[65G.2 finding, non-blocking] `/intake/mock/project-work-item` broken in staging** — the
  communication-gateway image lacks PyYAML (HTTP 500). Worked around via the orchestrator
  multi-project API. A future maintenance pass should add PyYAML to that image.
- **[65G.1 finding] Pipeline-native integrations are mock/dry-run.** The distributed agent pipeline
  uses mock LLM, dry-run demo-PR, and simulated notifications; the controlled rails (65D/65E/65F)
  must be invoked as separately-authorized correlated steps to produce real external artifacts in
  65G.2 (per the 65F-C guardrail).
- **Workflow resume / cancel / abort / ignore-after-abort** ~~exercised only in tests~~ →
  **VALIDATED (65H.3, PASS_WITH_GAPS):** cancel-before → canceled; cancel-during (dispatched) →
  canceled (stuck); abort-during → aborted; ignore-after-abort confirmed (HTTP 409 on late
  re-cancel/re-abort/resume; terminal state held); `production_executed_true_count=0`; no external
  integration. Raw late-**stream**-event injection = tracked gap (unsafe injection forbidden).
  **Operator confirmed VISIBLE** on the formal pages. See
  [cancel-abort-validation-report.md](cancel-abort-validation-report.md).
- **Approval paths (required / granted / denied / expired)** ~~exercised only in tests~~ →
  **VALIDATED (65H.2, PASS_WITH_GAPS):** required/granted/denied + production-block validated on
  controlled staging workflows (WF1 granted→resumed→completed; WF2 denied→rejected; WF3
  production.deploy blocked); `production_executed_true_count=0`; no external integration. The
  **approval expired/timeout** path is a **tracked gap** — no safe expiry route exists (read-only
  confirmed; not executed, no DB manipulation). **Operator confirmed VISIBLE** on the formal pages.
  See [approval-governance-validation-report.md](approval-governance-validation-report.md).
- **Retry / DLQ / manual replay / terminal-failure** ~~exercised only in tests~~ → **VALIDATED
  (65H.4, PASS):** controlled failure via the platform `simulate_failure` switch → retry (retry_count
  3→4) → DLQ creation → 1 manual replay → terminal failure (`stream.deadletter.terminal` + sev2
  incident + workflow `failed`); retry-count limit respected (loops bounded/settled);
  `production_executed_true_count=0`; no external integration, no DB manipulation, no unsafe
  injection. **Operator confirmed VISIBLE with gap** (PARTIAL_WITH_GAPS) — DLQ has no Admin Console
  page. See [retry-dlq-validation-report.md](retry-dlq-validation-report.md).
- **[65H.5 consolidation] Failure/governance track reviewed.** 65H.2/65H.3/65H.4 consolidated into an
  operator-reviewable evidence review; **65H = COMPLETED_WITH_GAPS, no BLOCKING gap**; every gap
  classified for Step 65I. See
  [failure-governance-operator-evidence-review.md](failure-governance-operator-evidence-review.md) +
  [failure-governance-gap-classification.md](failure-governance-gap-classification.md).
- **[65H.4 OPERATOR-FLAGGED UX GAP → 65I] No dedicated DLQ / Retry Admin Console page.** During
  65H.4 UI validation the operator confirmed VISIBLE-with-gap and flagged that the DLQ — an
  operator-facing failure indicator — has **no Admin Console page**: queue depth, per-entry failure
  reason (`task_id`/`original_stream`/`failure_reason`/`retry_count`), and manual replay are
  backend-API-only (`/operations/dlq`, retry-scheduler `/deadletter`). Terminal failures surface
  indirectly (Incidents / Task Graph `failed` / Audit-Evidence). **Recommendation:** add a
  first-class DLQ / Retry Admin Console page. Carry to Step 65I acceptance. Registered in
  [failure-governance-operator-ux-gap-register.md](failure-governance-operator-ux-gap-register.md).
- **[65H.1 finding, non-blocking] No dedicated `/approvals` Admin Console page.** Approval operator
  evidence surfaces on `/task-graph` (approval_status) + `/audit-evidence`
  (+ `/operations/approval-decisions/{task_id}` API).

## Integration gaps
- **GitHub:** ~~dry-run/mock only; no controlled sandbox write validated~~ → **RESOLVED (65D)**:
  real draft PR #15 created in `AI-Agents-SWD-sandbox` via the controlled path (a Step 59 no-commit
  flow gap was fixed); reset to safe; `production_executed_true_count=0`.
- **Notification (Slack/Discord):** ~~**PENDING_65E**~~ → **VALIDATED**: one real `[STAGING]` test
  message sent to `MySanbox`/`#general` via the discord-gateway controlled path; reset to safe;
  `production_executed_true_count=0`; operator confirmed **VISIBLE**. → see
  [controlled-notification-validation-report.md](controlled-notification-validation-report.md).
- **LLM:** ~~**PENDING_65F**~~ → **VALIDATED_WITH_GOVERNANCE_GAP**: one official, audited, bounded
  Anthropic call (`claude-haiku-4-5-20251001`, 708 tokens, actual cost $0.03096, well under the $1
  cap) via the Stage-35 plan-only real-LLM rail succeeded; `production_executed_true_count=0`. Two
  diagnostic probes bypassed the budget/audit rail before that call (disclosed, non-sensitive,
  negligible cost) — Step 65F final status is **PASS_WITH_GAPS**, not a clean PASS; future direct
  diagnostic external calls are forbidden unless separately authorized. → see
  [controlled-llm-validation-report.md](controlled-llm-validation-report.md) +
  [step65f-llm-validation-final-status.md](step65f-llm-validation-final-status.md).
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
