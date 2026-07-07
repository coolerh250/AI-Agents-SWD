# Cancel / Abort — Known Gaps (Step 65H.3)

> **Staging only — non-production only. No production action. No production data.**
> **Documentation only. No secret value appears here.**

## Gaps
1. **[tracked, authorized-as-acceptable] Raw late-stream-event injection not executed.** The
   "late event ignored after abort" path was validated at the **API** level — late
   `resume` / `cancel` / `abort` on an aborted workflow were all refused (HTTP 409), and the terminal
   state held. Injecting a **raw late stream event** to a terminal workflow would require **unsafe
   stream injection**, which the operator explicitly forbade. Per the 65H.3 authorization, this
   specific variant is recorded as a **tracked gap**, not a failure.
2. **[non-blocking, honest observation] Cancel-during does not un-dispatch in-flight agent events.**
   WF2 was already dispatched to `stream.tasks` before the cancel landed, so the in-flight mock agent
   pipeline ran its 5 hops. The **workflow** was canceled (terminal state held; `production_executed=false`),
   but workflow-level cancel does not retroactively stop already-emitted agent events. This is a
   documented characteristic of the async pipeline, not a safety issue (no production action; prod_exec=0).
3. ~~Operator UI validation pending.~~ **RESOLVED** — the operator confirmed **VISIBLE** on the
   formal Admin Console pages. See
   [cancel-abort-operator-validation-request.md](cancel-abort-operator-validation-request.md).

## Non-gaps (done)
- Cancel-before, cancel-during, abort-during validated; ignore-after-abort confirmed (HTTP 409 on
  re-cancel / re-abort / resume; terminal state held); `production_executed_true_count=0`; no
  external integration used; ≤3 workflows.

## Blocking gaps
- **None.** No gap blocks the technical result; the raw-stream-injection variant is an
  authorized-acceptable tracked gap, and the only open item is the pending operator UI validation.

## Status
Step 65H.3: **PASS_WITH_GAPS**. `production_executed_true_count=0`.

---
_Staging only — non-production only. No production action. No production data._

<!-- staging-safety: staging-only=true non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
