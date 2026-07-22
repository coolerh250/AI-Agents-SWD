# Planning Handoff — Step 66C.4-P

> **Handoff document only. No implementation authorized by this document.**

Follows `docs/process/partner-handoff-standard.md`: what changed, what remains undecided, what
requires Claude Code review, what requires Product Owner decision, and what Codex/Claude Design
must not implement yet.

## What changed

Nothing in runtime code, backend, API, database, or workflow. This stage produced 13 planning/
contract documents under `docs/contracts/66c4-reminder-expiry-controlled-resume/`, all read-only
analysis and forward-looking proposals:

```text
current-state-assessment.md, lifecycle-and-time-contract.md, data-model-contract.md,
api-and-event-contract.md, scheduler-architecture-decision.md, controlled-resume-contract.md,
rbac-and-safety-contract.md, race-condition-and-failure-analysis.md, observability-and-audit-
plan.md, frontend-ux-boundary.md, implementation-stage-slicing-plan.md, test-and-validation-
plan.md, product-owner-decision-checklist.md.
```

## Step 66C.4-P-R1 remediation (contract corrections, same branch)

Following the Product Architect `PASS_WITH_GAPS` review, seven corrections (A–G) were applied on the
SAME branch (`contract-remediation-record.md` documents each in full):

```text
A Field inventory      -> six lifecycle columns reconciled; resume_dispatched_at removed; durable
                          outbox table added; four additional candidate columns declined.
B Authoritative expiry -> due_at is the authoritative exclusive deadline; answer-claim gains
                          `AND due_at > now()`; scheduler lag cannot extend the answer window.
C Reminder semantics    -> at-least-once + idempotent; exactly-once NOT claimed.
D Atomicity model       -> transactional outbox selected (Option 3/existing-mechanism rejected with
                          evidence); publish failure is no longer a "non-blocking gap".
E Clock semantics        -> absolute "no clock skew" wording removed; canonical wording adopted.
F Recovery semantics     -> automatic vs operator recovery explicitly split.
G Resume state model     -> request/authorized/dispatched/resumed are four separate transitions;
                          operator request never equals workflow resumed; dispatch built gated in
                          66C.4-BE3 (disabled-by-default).
```

Nothing about the authorization posture changed: Codex and Claude Design remain unauthorized, and
Step 66C.4-BE1 remains not started.

## What remains undecided

Six genuine Product Owner decisions, all in `product-owner-decision-checklist.md`:

```text
1. Late answer after 72h expiry — recommended: not allowed once DB time >= due_at (deadline-
   authoritative, regardless of scheduler lag).
2. Blocked vs. expired presentation — recommended: "Blocked — clarification expired" user-facing
   label over the existing `expired` backend semantics.
3. Explicit operator resume (Option A) vs. policy-controlled automatic resume (Option B) —
   recommended: Option A. THE most consequential decision in this planning stage.
4. Additional confirmation before resume — recommended: the explicit request IS the confirmation;
   production-effect approval unchanged; no added second general confirmation.
5. Single reminder vs. multiple reminders — recommended: single, at +24h.
6. Reopen expired clarification vs. always create new — recommended: always create new.
```

## What requires Claude Code review

Nothing further from this stage's own output requires additional Claude Code review before Product
Owner decision — this planning IS Claude Code's own review-equivalent output (architecture
direction self-certified per the stage-gate pattern for planning-only stages, see
`docs/stages/66c4-reminder-expiry-controlled-resume-planning/stage-gate-report.md`).

## What requires Product Owner decision

The six items above, plus the standing authorization to proceed to `66C.4-BE1` (data model/
migration) once the Product Owner confirms the recommended defaults (or overrides any of them).

## What Codex must not implement yet

Everything in `frontend-ux-boundary.md`'s "Codex potential future scope" section — Codex is not
authorized to begin any implementation by this stage, and will not be until: (a) 66C.4-BE1/BE2/BE3
are complete, (b) 66C.4-BE-R passes, and (c) a separate, explicit Product Owner authorization names
`66C.4-FE` specifically.

## What Claude Design must not do yet

Everything in `frontend-ux-boundary.md`'s "Claude Design potential future scope" section — Claude
Design is not authorized to begin any design work by this stage, and a `66C.4-DESIGN` stage may
not even be necessary at all (conditional on whether new UX-state design is genuinely required
beyond what `core-loop-experience-definition.md` already covers).

## Statement

Handoff document only. No implementation authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
