# Product Owner Decision Checklist — Step 66C.4-P

> **Planning document only. This checklist authorizes nothing itself. Only genuine product-
> behavior decisions are listed here — purely technical choices (scheduler technology, DB index
> design, etc.) are NOT included, since those are Claude Code's architectural responsibility, not
> a Product Owner decision.**

## Decision 1 — Is a late answer allowed after 72h expiry?

```text
Recommended option: NOT allowed once the scheduler has actually transitioned the row to 'expired'
  (the existing CAS-guarded answer-claim already enforces this with zero new code).
Alternative: allow a grace-period reopen (e.g. a new "reopen expired clarification" action).
User impact: recommended option means a user who answers a few seconds after the 72h deadline
  (but before the scheduler's next poll cycle claims it) may still succeed narrowly, but once
  actually expired, they must be told clearly and, if a decision is still needed, a NEW
  clarification must be raised.
Safety impact: recommended option requires zero new code and reuses an already-proven guard;
  a reopen mechanism would be new, untested code with its own race conditions to solve.
Implementation impact: recommended option = zero additional work; a reopen mechanism would add a
  meaningful chunk of new scope to 66C.4-BE3.
Default if PO does not override: recommended option (no late answer / no reopen).
```

## Decision 2 — How should "blocked" vs. "expired" be presented to the user?

```text
Recommended option: this stage does NOT introduce a separate "blocked" state for clarification
  timeout at all — it reuses only "expired" (clarification-level) and clarification_expired
  (task-level), both already-modeled. The existing, unrelated `blocked` task-status value is left
  untouched (reserved for its current operational-failure meaning).
Alternative: introduce a visually distinct "blocked" presentation layered on top of the same
  expired state, if the Product Owner wants a softer/different tone than "expired" conveys.
User impact: recommended option means the user-facing language is "this clarification window has
  closed / expired," not "blocked" — a wording choice, not a functional difference.
Safety impact: none either way — this is purely a presentation choice.
Implementation impact: recommended option = zero additional work (frontend-ux-boundary.md's
  "blocked / clarification expired" UX state already accounts for a single combined presentation).
Default if PO does not override: recommended option (single "expired" presentation, no separate
  "blocked" tone).
```

## Decision 3 — Answer-to-resume: explicit operator resume (Option A) or policy-controlled
automatic resume (Option B)?

```text
Recommended option: Option A — Explicit operator-controlled resume (see controlled-resume-
  contract.md for the full comparison).
Alternative: Option B — Policy-controlled automatic resume.
User impact: Option A adds one explicit step for an operator/PM/Admin after a clarification is
  answered; Option B requires no human action beyond answering.
Safety impact: Option A preserves this project's unbroken precedent of gating every consequential
  action behind an explicit human decision; Option B would be the first-ever automatic,
  non-human-triggered state transition with real workflow effect in this project's history.
Implementation impact: Option A requires one additional endpoint (POST .../resume-request) and one
  additional RBAC capability function; Option B requires neither, but shifts all safety weight
  onto the automated policy/safety check's correctness.
Default if PO does not override: Option A (this stage's own recommendation).
**This is the single most consequential decision in this entire planning document** — it
  determines whether 66C.4-BE3 builds a request endpoint at all.
```

## Decision 4 — Is additional human confirmation required before resume, beyond the
request/authorization step itself?

```text
Recommended option: NO additional confirmation step beyond the resume-request action itself (under
  Option A) — the request itself already IS the explicit human action; a second "are you sure"
  confirmation would be redundant given resume never proceeds past "authorized" in any stage this
  planning covers (actual dispatch, where a second confirmation might matter more, is out of
  scope entirely).
Alternative: require a second, explicit confirmation step (e.g. a modal "confirm resume") before
  the request is finalized.
User impact: recommended option is a single-click action; the alternative adds one more click/step.
Safety impact: minimal difference either way, since this stage's implementation scope never
  reaches actual dispatch — the highest-stakes moment (an actual workflow resuming) is not built
  by any stage this planning covers, so the marginal safety value of a second confirmation now is
  low. A future stage that actually builds dispatch should revisit this question at that time,
  when the real consequence exists.
Implementation impact: recommended option = simpler; alternative = one more UI state to design/
  build in 66C.4-FE.
Default if PO does not override: recommended option (no additional confirmation at the
  request/authorization stage; revisit when dispatch is eventually built).
```

## Decision 5 — Is the reminder sent exactly once, or should multiple reminders be supported?

```text
Recommended option: exactly once, at +24 hours (matches the existing reminder_at column and the
  already-operator-decided Q2 timeout from Stage 66A.3 — see lifecycle-and-time-contract.md's
  canonical default).
Alternative: multiple reminders (e.g. at 24h and again at 48h) — would require a reminder_count
  column instead of a single reminder_sent_at timestamp.
User impact: recommended option means a single nudge; the alternative provides more persistent
  prompting for a user who missed the first reminder.
Safety impact: none either way.
Implementation impact: recommended option is simpler (one nullable timestamp column); the
  alternative requires a counter column plus recurring-claim logic in the scheduler.
Default if PO does not override: recommended option (exactly one reminder).
```

## Decision 6 — Should an expired clarification ever be allowed to reopen, or must a new
clarification always be created instead?

```text
Recommended option: must always create a new clarification (no reopen mechanism proposed) — this
  is the same underlying question as Decision 1, restated here explicitly per this stage's own
  required checklist item, since the prompt lists it separately.
Alternative: build a "reopen" action that resets an expired clarification back to 'open' with a
  fresh due_at/reminder_at.
User impact: recommended option means slightly more friction (create a new clarification, losing
  the original question's thread continuity beyond the audit trail); the alternative preserves
  continuity but reintroduces a timed-out conversation.
Safety impact: recommended option avoids reopening a decision window that may no longer reflect
  current task state (e.g. the task may have moved on in ways that make the original question
  stale); the alternative risks resuming a stale conversation.
Implementation impact: recommended option = zero additional work; the alternative requires new
  reopen logic with its own race-condition analysis (not covered by this stage's 16-scenario
  catalogue, since it assumes no-reopen).
Default if PO does not override: recommended option (no reopen; new clarification only).
```

## Statement

Planning document only. This checklist authorizes nothing itself. Only genuine product-behavior
decisions are listed here.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
