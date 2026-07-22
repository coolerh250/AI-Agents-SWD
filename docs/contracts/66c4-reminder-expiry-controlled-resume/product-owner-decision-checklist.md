# Product Owner Decision Checklist — Step 66C.4-P

> **Planning document only. This checklist authorizes nothing itself. Only genuine product-
> behavior decisions are listed here — purely technical choices (scheduler technology, DB index
> design, etc.) are NOT included, since those are Claude Code's architectural responsibility, not
> a Product Owner decision.**

## Decision 1 — Is a late answer allowed after 72h expiry?

```text
Recommended option (refined in Step 66C.4-P-R1): NOT allowed once authoritative DB time has reached
  due_at, REGARDLESS of whether the scheduler has yet materialized status='expired'. The corrected
  answer-claim carries an `AND due_at > statement_timestamp()` deadline predicate
  (lifecycle-and-time-contract.md
  §7.3A), so scheduler lag never opens a late-answer window.
Alternative: allow a grace-period reopen (e.g. a new "reopen expired clarification" action).
User impact: a user who submits at or after the 72h deadline receives a clear "this decision window
  has closed / expired" result (never a silent success); if a decision is still needed, a NEW
  clarification is raised.
Safety impact: recommended option makes the deadline authoritative and deterministic; a reopen
  mechanism would be new, untested code with its own race conditions to solve.
Implementation impact: recommended option = a small predicate addition in 66C.4-BE1; a reopen
  mechanism would add a meaningful chunk of new scope.
Default if PO does not override: recommended option (deadline-authoritative; no late answer / no
  reopen).
```

## Decision 2 — How should "blocked" vs. "expired" be presented to the user?

```text
Recommended option (refined in Step 66C.4-P-R1): the USER-FACING label is
  "Blocked — clarification expired" (a single combined presentation), while the BACKEND
  clarification/task status continues to use the existing `expired` / `clarification_expired`
  semantics unchanged. No new backend "blocked" state is introduced; the existing, unrelated
  `blocked` task-status value is left untouched (reserved for its operational-failure meaning).
Alternative: present strictly as "expired" with no "blocked" framing, or as two visually distinct
  states, if the Product Owner prefers.
User impact: the user sees "Blocked — clarification expired" — a wording choice, not a functional
  difference; backend behavior is identical either way.
Safety impact: none — purely a presentation choice.
Implementation impact: recommended option = zero backend work (frontend label only;
  frontend-ux-boundary.md already accounts for a single combined presentation).
Default if PO does not override: recommended option ("Blocked — clarification expired" label over
  the existing expired backend semantics).
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
Recommended option (refined in Step 66C.4-P-R1): the Operator's explicit resume-request action IS
  the human confirmation — no second general "are you sure" step is added at the request/
  authorization stage. IMPORTANTLY, a production-effect task still requires the EXISTING extra
  approval it always requires (production-effect protection is unchanged and non-negotiable); this
  decision does NOT add a second general confirmation and does NOT remove any existing
  production-effect approval.
Alternative: require a second, explicit confirmation step (e.g. a modal "confirm resume") before
  the request is finalized.
User impact: recommended option is a single deliberate action; the alternative adds one more step.
Safety impact: the explicit request already provides a human decision point; production-effect
  tasks retain their existing extra approval. Dispatch is built gated/disabled-by-default in
  66C.4-BE3, so enabling real production-effecting resume is itself a separate authorization — the
  marginal value of a second general confirmation now is low.
Implementation impact: recommended option = simpler; alternative = one more UI state in 66C.4-FE.
Default if PO does not override: recommended option (the explicit request is the confirmation;
  production-effect approval unchanged; no added second general confirmation).
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
