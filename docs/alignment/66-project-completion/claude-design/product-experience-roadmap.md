# Product Experience Roadmap — Step 66ALIGN.1 (Claude Design)

> Owner: Claude Design. Product-experience alignment from the current state to production
> completion, anchored to the canonical M0–M7 milestone order. **Design analysis only — no runtime
> code, no prototype, no merge, no deploy. `source/progress.md`, `apps/**`, `services/**`,
> `infra/**` are NOT modified by this stage.**

## The product loop (the thing every milestone serves)

```text
Assign → Converse → Clarify → Wait / Resume → Observe agent team →
Review delivery → Request changes / rerun QA → Accept
```

The Admin Console must read as an **AI team command center / operator workspace / delivery and
decision surface** — never regress into an **API inspector / raw evidence browser / engineering
debug console**. Every milestone below is measured against how much of that loop a real user can
complete, and how product-grade the experience of completing it is.

## Canonical milestone order (shared baseline)

```text
M0 — Source of Truth and Runtime Reconciliation
M1 — Core Human–Agent Interaction Loop
M2 — Delivery and Acceptance Loop
M3 — AI Team Orchestration and Multi-role Control
M4 — Notifications, Action Center and Channels
M5 — Controlled End-to-End Pilot
M6 — Production Readiness and Platform Hardening
M7 — Production Rollout and Adoption
```

## Where each loop step lives on the roadmap

| Loop step | Milestone that makes it real | Today |
| --- | --- | --- |
| Assign | M1 (exists: Create Task) | works |
| Converse | M1 (Workroom message thread) | works (log-style; needs product-grade treatment) |
| Clarify | M1 (clarification as a decision request) | works as task-scoped form; needs decision-request UX |
| Wait / Resume | M1 (safe wait state) + later workflow resume | wait state shown; resume is disabled by design |
| Observe agent team | M1 + M3 (team visibility model) | read-only agent-execution evidence only |
| Review delivery | M2 (Delivery Inbox/Detail) | placeholder (Requires 66D) |
| Request changes / rerun QA | M2 | placeholder (Requires 66D) |
| Accept | M2 | placeholder (Requires 66D) |

## Current product-experience assessment

**Strong / shipped:** grouped IA shell (7 groups) with product-language nav labels, subtitles, and
Soon/Read-only/Evidence badges (FE.1D-S1); attention-first Overview (FE.1C) that leads with
"Needs your attention" + AI team activity + current work; calm safety posture (FE.1B/FE.1B.1) that
reads as reassurance, not a raw field dump; task list/detail/workroom and task-scoped clarifications
(Step 66B/C); honest placeholders for everything not yet built.

**The core gap:** the loop is only completable through *Clarify / Answer*. **Wait/Resume** (workflow
resume is disabled by design), **Observe agent team** (only read-only execution evidence, no rich
team state), and the entire **Review → Request changes → Accept** arc (66D) are not yet real. So the
product today lets you *start* working with the AI team but not *finish* a delivery with it — M1 and
M2 are where the product becomes itself.

**The standing risk:** with so many engineering/evidence surfaces already present (Platform Ops's 20
read-only/evidence pages, audit evidence), the product can drift back toward "engineering console"
if polish and capability aren't sequenced deliberately. The whole point of this alignment is to keep
M1/M2 (the product loop) ahead of cosmetic and ops-surface work.

## Sequencing principle

1. **Capability before cosmetics.** Real loop capability (M1 Workroom/clarification/wait, M2
   delivery/accept) outranks any cosmetic polish pass.
2. **Adopt polish standards as-you-build.** The FE.1D microcopy/field-label standards are applied to
   *new* M1/M2 surfaces as they are built — not run as a separate pass that jumps the queue.
3. **Engineering surfaces stay secondary.** Platform Ops / Evidence / Safety remain present, calm,
   collapsed/badged, and never the product's headline (see `team-visibility-model.md` and the
   dedicated analyses).
4. **Nothing fake.** No surface is designed beyond a compliant placeholder before its milestone
   owner/contract exists.

## FE.1D-S2 recommended timing (explicit)

**FE.1D-S1** (navigation labels + badges + Platform Ops density) is merged and deployed. **FE.1D-S2**
is the *remaining* FE.1D work — microcopy cleanup, the field-label rename map, engineering-field
exposure reduction (TaskList status/timestamp/boolean labels, shared status-label map, empty-state
and placeholder wording consistency, moving raw dumps into a "Technical details" disclosure).

**FE.1D-S2 is cosmetic polish over existing surfaces. It must NOT be scheduled ahead of M1 or M2.**
Recommended placement:

- **Do not** run FE.1D-S2 as the next standalone stage if it would displace M1 core-loop work.
- **Preferred:** fold the FE.1D-S2 *standards* into M1 as the Workroom / clarification / task
  surfaces are (re)built, so new work ships product-grade by construction; then run the small
  residual S2 pass over the remaining legacy surfaces **concurrent with or after M1**, as
  low-priority polish, never as a gate.
- The FE.1D-S2 design already exists (`docs/design/66ui4-fe1d-navigation-microcopy/`) and is
  ready; this is a *scheduling* recommendation, not a request to redesign it.

## Companion documents

`milestone-user-journeys.md` (per-milestone 10-point analysis), `core-loop-experience-definition.md`
(M1), `delivery-experience-definition.md` (M2), `team-visibility-model.md` (agent/team visibility),
`action-center-channel-experience.md` (M4), `production-trust-and-adoption-ux.md` (M6/M7),
`alignment-statement.md` (result + conflicts + marker).

## Statement

Design analysis only. No runtime code. No production action. No prototype. No merge. No Codex
authorization by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
