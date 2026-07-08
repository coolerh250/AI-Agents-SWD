# Retry / DLQ — Known Gaps (Step 65H.4)

> **Staging only — non-production only. No production action. No production data.**
> **Documentation only. No secret value appears here.**

## Gaps
1. **[non-blocking] 3 open sev2 controlled-test incidents.** The two controlled-failure workflows
   (and the one manual replay) each drove a terminal failure, so the retry-scheduler created 3 sev2
   incident records (S1 ×2, S2 ×1), left in status `open`. These are **expected controlled-test
   artifacts**; the operator may acknowledge/close them via the incident routes. Not a safety issue
   (sev2, no sev1; `production_executed_true_count=0`).
2. **[non-blocking, evidence surface] No dedicated `/dlq` Admin Console page.** DLQ / retry / terminal
   evidence is surfaced via the formal API `/operations/dlq`, the retry-scheduler `/deadletter`
   endpoint, `/operations/incidents`, `/audit-evidence`, and the workflow_state (`failed`). Documented
   in the 65H.1 plan; a future UI enhancement could add a dedicated DLQ view.
3. **[pending] Operator UI validation.** The technical execution succeeded and API evidence is
   captured; the operator has not yet visually confirmed the evidence on the formal Admin Console
   pages / APIs. Tracked in
   [retry-dlq-operator-validation-request.md](retry-dlq-operator-validation-request.md).

## Non-gaps (done)
- Controlled agent failure (platform `simulate_failure` switch), retry scheduler, DLQ creation, one
  manual replay, retry-count limit (max_retries=3; dead-letter at 3, terminal at >3), and terminal
  failure (`stream.deadletter.terminal` + incident + workflow `failed`) all validated; the retry
  loops were bounded and settled (no runaway); `production_executed_true_count=0`; no external
  integration; no DB manipulation; no unsafe stream injection.

## Blocking gaps
- **None.** No gap blocks the technical result; the only open item is the pending operator UI
  validation.

## Status
Step 65H.4: **PASS** (operator UI validation pending). `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
