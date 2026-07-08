# Retry / DLQ — Known Gaps (Step 65H.4)

> **Staging only — non-production only. No production action. No production data.**
> **Documentation only. No secret value appears here.**

## Gaps
1. **[non-blocking] 3 open sev2 controlled-test incidents.** The two controlled-failure workflows
   (and the one manual replay) each drove a terminal failure, so the retry-scheduler created 3 sev2
   incident records (S1 ×2, S2 ×1), left in status `open`. These are **expected controlled-test
   artifacts**; the operator may acknowledge/close them via the incident routes. Not a safety issue
   (sev2, no sev1; `production_executed_true_count=0`).
2. **[OPERATOR-FLAGGED UX GAP] No dedicated DLQ / Retry Admin Console page.** During 65H.4 UI
   validation the operator confirmed the evidence **VISIBLE with gap** and specifically flagged this:
   the DLQ — an operator-facing failure indicator — is **not surfaced on any Admin Console page**. Its
   queue depth, per-entry detail (`task_id` / `original_stream` / `failure_reason` / `retry_count`),
   and the manual-replay action are **backend-API-only** (`:18000/operations/dlq`, retry-scheduler
   `:18015/deadletter`). Terminal failures ARE surfaced indirectly (Incidents / Task Graph `failed` /
   Audit-Evidence), but the DLQ-specific operator view (queue + per-message reason + one-click replay)
   is missing. **Recommendation:** add a first-class **DLQ / Retry** Admin Console page (read the
   `/operations/dlq` + `/deadletter` APIs; expose queue depth, terminal vs in-flight, per-entry
   failure reason, and a controlled manual-replay control). Carry this into the Step 65I acceptance
   review as a known UI/operator-visibility gap.
3. ~~Operator UI validation pending.~~ **RESOLVED** — the operator confirmed **VISIBLE with gap**
   (`PARTIAL_WITH_GAPS`); the gap is the DLQ-no-Admin-page item above. See
   [retry-dlq-operator-validation-request.md](retry-dlq-operator-validation-request.md).

## Non-gaps (done)
- Controlled agent failure (platform `simulate_failure` switch), retry scheduler, DLQ creation, one
  manual replay, retry-count limit (max_retries=3; dead-letter at 3, terminal at >3), and terminal
  failure (`stream.deadletter.terminal` + incident + workflow `failed`) all validated; the retry
  loops were bounded and settled (no runaway); `production_executed_true_count=0`; no external
  integration; no DB manipulation; no unsafe stream injection.

## Blocking gaps
- **None** for the technical retry/DLQ result. The operator-flagged **DLQ-no-Admin-page** item is a
  non-blocking UX gap carried into the Step 65I acceptance review.

## Status
Step 65H.4: **PASS_WITH_GAPS** — operator confirmed **VISIBLE with gap** (DLQ has no Admin Console
page). `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
