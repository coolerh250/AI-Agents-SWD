# Delivery Experience Definition — M2 (Step 66ALIGN.1, Claude Design)

> Owner: Claude Design. The M2 experience: Review delivery → Request changes / rerun QA → Accept.
> Defines the **minimal complete** Delivery Inbox + Delivery Detail and resolves the Request-Changes
> vs Re-run-QA confusion risk. Analysis only; gated on the Step 66D contract (Claude Code owns the
> data shape).

## M2 goal

A reviewer can see what the AI team delivered, understand it without reading raw JSON, and take one
of four clear decisions — Accept / Reject / Request Changes / Re-run QA — each with an unambiguous
consequence.

## Delivery Inbox — minimal complete design

A cross-task **acceptance queue**, not an evidence table:

- **Rows:** delivery title (from the task), which task it belongs to, producing agent, QA state,
  risk state, submitted time (relative). Product-readable — no raw ids as the headline.
- **Primary sort:** what's awaiting the viewer's review first.
- **States:** submitted / under-review / accepted / rejected / changes-requested /
  qa-rerun-requested.
- **Empty/error/loading:** "Nothing to review right now." / loading skeleton / role-restricted.
- **No bulk destructive actions**; opening a delivery is the path to acting on it.
- **Distinct from the legacy `Delivery Package`** (Platform Ops evidence record) — the Inbox is the
  66D task-linked human-acceptance surface; do not conflate (already a settled decision).

## Delivery Detail — minimal complete design (the "acceptance desk")

- **Summary first:** what was produced, in plain language; producing agent; QA result and risk as
  calm chips.
- **Evidence is expandable secondary detail** (artifacts, QA output, diffs, hashes) under a
  "Technical details" disclosure — never the headline. This is the anti-"raw evidence browser"
  guarantee.
- **Four review actions**, each with explicit consequence copy (see below).
- **Safety:** a delivery review action must not imply workflow dispatch/resume or any production/
  external action; the calm posture stays visible.

## Request Changes vs Re-run QA — avoiding confusion

These two are the confusion risk. Make them **visibly different decisions with different
consequences**:

| Action | What it means (plain language) | Consequence | Who/what acts next |
| --- | --- | --- | --- |
| **Accept** | "This delivery is good." | Delivery accepted; loop completes for this work. | closes the loop |
| **Reject** | "This isn't acceptable and shouldn't proceed." | Delivery rejected; needs a new direction. | returns to the team with a stop |
| **Request Changes** | "Mostly right — change these specific things." | Goes back for revision; you describe the changes. | the development agent revises |
| **Re-run QA** | "The work may be fine — re-check quality." | Re-runs the QA step only; no scope/content change requested. | the QA agent re-verifies |

Design rules to prevent confusion:

1. **Group by intent:** "Accept" (positive, primary) separated from the three "send back" actions.
2. **Request Changes always requires a written "what to change"** — it is about *content*; Re-run QA
   requires *no* change description — it is about *verification*. The form each opens makes the
   difference obvious (a change-description field vs a confirm-only "re-check quality").
3. **Consequence preview:** each action states, before confirm, exactly what will happen and who
   acts next (the table's "Consequence"/"acts next" columns as inline copy).
4. **Request Changes small vs major** (from the product model) is a secondary choice *inside*
   Request Changes, not a fifth top-level button — keep the top level to the four.
5. **Never two buttons that look interchangeable** — different weight, icon, and consequence copy.

## Human decision points (M2)

Accept · Reject · Request Changes (+ small/major) · Re-run QA — the four, each consequence-explicit.

## Agent visibility (M2)

Which agent produced the delivery; the QA agent's result; what a re-run would re-execute. Ties into
`team-visibility-model.md`.

## Product-language requirements

Acceptance-desk language: "Ready for your acceptance", "Accept", "Request changes", "Re-run QA",
"Rejected". Evidence/QA/hash detail lives under "Technical details". No JSON-dump headline.

## Accessibility

The four actions are distinct, labelled, keyboard-reachable; consequential actions confirmed; the
change-description field is properly labelled and its requirement enforced accessibly.

## Product Owner validation checklist (M2)

```text
- Can see deliveries awaiting review (or a calm empty state).
- Can open a delivery and understand it WITHOUT reading raw JSON/evidence.
- Can Accept / Reject / Request Changes / Re-run QA.
- The difference between Request Changes and Re-run QA is unambiguous (content vs verification).
- Each action previews its consequence and who acts next.
- No review action implies workflow dispatch/resume or production/external action.
```

## What must remain placeholder-only in M2

- Any action requiring workflow **re-dispatch** stays gated until that is explicitly authorized
  (the review *decision* is recorded; the automated re-execution is separate and gated).
- **External delivery notifications** (M4).
- Anything the 66D contract does not yet return — no fabricated fields; stays a compliant
  placeholder until Claude Code publishes the shape.

## Dependency

M2 is **gated on the Step 66D API/data contract** (Claude Code). This document defines the
*experience*; the *data shape* is Claude Code's contract. No M2 surface is built beyond a compliant
placeholder until that contract exists.

## Statement

Design analysis only. No runtime code. No production action. No merge. No Codex authorization.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
