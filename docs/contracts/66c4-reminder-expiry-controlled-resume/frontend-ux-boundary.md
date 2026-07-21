# Frontend and UX Planning Boundary — Step 66C.4-P

> **Planning document only. Claude Design is NOT authorized to begin design work by this document.
> Codex is NOT authorized to begin implementation by this document. This document only marks
> future potential scope for later, separately authorized stages.**

## Claude Design potential future scope (NOT started by this stage)

Only if Option A (explicit operator-controlled resume) is confirmed and a new UX-state decision is
genuinely needed beyond what `core-loop-experience-definition.md` already defines. That document
already specifies the five team-states (working / waiting-on-you / paused-will-not-resume / idle /
blocked) and the clarification-as-decision-request pattern — 66C.4's new states below are largely
refinements within that existing framework, not a new design language:

```text
- team working (existing).
- waiting on you (existing).
- reminder sent -- NEW, a refinement: still "waiting on you," now with an added "we reminded you"
  signal.
- blocked / clarification expired -- NEW-ish: maps onto the existing clarification_expired
  task-status; needs a calm, honest presentation ("this decision window has closed") rather than
  an error tone.
- answer received -- existing pattern (already covered by "Answer recorded" in
  core-loop-experience-definition.md).
- ready to resume -- NEW, only relevant under Option A: a distinct "waiting for you" state where
  the OPERATOR (not the original requester) is now the one with a pending action.
- resume in progress -- NEW, only relevant under Option A, and only as far as "authorized" (not
  "dispatched," which is out of scope for any stage this planning covers).
- resume failed -- NEW, only relevant under Option A; "not eligible" is the realistic outcome to
  design for, not a dispatch failure (dispatch itself doesn't exist yet).
- resumed -- NOT applicable to any stage this planning covers (dispatch/actual resume is out of
  scope entirely).
```

Claude Design is explicitly NOT asked to start on any of the above by this stage. This list exists
so a FUTURE `66C.4-DESIGN` stage (only if the ownership-remediation-corrected slicing plan
determines new UX-state design is genuinely required — see implementation-stage-slicing-plan.md)
has a concrete, evidence-based starting point rather than re-deriving it from scratch.

## Codex potential future scope (NOT started by this stage)

```text
- Workroom lifecycle banner: a small addition to the existing ClarificationCard
  (`apps/admin-console/src/pages/TaskWorkroom.tsx`) showing reminder-sent/expired state, reusing
  the existing card structure rather than a new component.
- Clarification due/reminder/expired state: rendering the new lifecycle fields (reminder_sent_at,
  expired_at) already returned by the proposed GET .../lifecycle endpoint.
- Late-answer behavior: rendering the existing 409 invalid_state_for_answer response readably
  (this is a frontend error-handling refinement, not new backend behavior — the backend behavior
  already exists per current-state-assessment.md).
- Resume eligibility display: rendering the proposed GET .../resume-eligibility response.
- Explicit resume control: ONLY if Option A is the Product-Owner-confirmed model — a button
  calling the proposed POST .../resume-request endpoint, RBAC-gated identically to the backend
  (never a client-side-only gate, per rbac-and-safety-contract.md and
  security-governance/SKILL.md item 5).
- Audit/evidence display: the new audit event types surfacing through the EXISTING, unmodified
  AuditEvidenceSection component (`TaskWorkroom.tsx`) — no new evidence-display component needed,
  since the existing allowlist-projection pattern is reused unchanged.
- Loading/error/empty states: reuse the existing `AsyncView`/`EmptyState`/`ErrorState` components
  already used throughout the Workroom surface — no new state-management pattern needed for this
  scope (unlike, e.g., the Master Plan's M4 Action Center, which Codex's own prior alignment
  analysis flagged as needing a new shared query/mutation pattern; 66C.4's scope is narrow enough
  that the existing `AsyncView` pattern remains sufficient).
- Frontend tests: extending the existing `WorkroomUI`/`WorkroomAuditVisibility`-style test suites
  with new lifecycle-state and (if Option A) resume-request test cases.
```

## Existing components confirmed reusable (verified by direct inspection, not assumed)

```text
ClarificationCard, AnswerForm, AuditEvidenceSection, AsyncView, EmptyState, ErrorState — all
  already exist in apps/admin-console/src and already handle the closest-analog states this
  stage's future frontend work would extend, per current-state-assessment.md §7.
```

## Fake controls prohibited

```text
Per security-governance/SKILL.md item 8: no future frontend stage may render a resume button (or
  any other control) that appears actionable before its backend contract exists and is
  authorized. The existing /clarification-reminders PlaceholderPage must remain exactly that — a
  compliant placeholder stating "Not yet available, requires Step 66C.4" — until a future,
  separately-authorized implementation stage actually builds the real page.
```

## Authorization status (restated for absolute clarity)

```text
Claude Design: NOT authorized to begin any design work by this document.
Codex: NOT authorized to begin any implementation by this document.
Both require: (a) this planning stage's own Product Owner review and decision on Option A vs. B
  (product-owner-decision-checklist.md item 3), (b) a separate, explicit Product Owner
  authorization naming the specific future stage (e.g. "66C.4-FE") before either partner may start
  work, exactly matching this project's established design-collaboration/SKILL.md and
  frontend-implementation/SKILL.md authorization chains.
```

## Statement

Planning document only. Claude Design is NOT authorized to begin design work by this document.
Codex is NOT authorized to begin implementation by this document. This document only marks future
potential scope for later, separately authorized stages.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
