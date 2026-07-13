# Placeholder Rules — DESIGN-66UI.2

> Owner: Claude Design. How not-yet-available features are presented so no user ever believes a
> capability is active when it is not. Implements the placeholder policy from
> `docs/design/66ui-full-redesign-options/product-owner-decision-summary.md` §5 and the boundary in
> `docs/frontend/66ui-full-redesign-options/codex-readiness-boundary.md` §1.

## Core rule

A placeholder is a **read-only informational panel**. It never renders an actionable control
(no Accept / Reject / Approve / Retry / Replay / Send / Dispatch / Resume / drag handle). It always
states, in plain text, (1) that the feature is not yet available, (2) the specific stage that will
enable it, and (3) that no workflow action is available from it.

## Placeholder state vocabulary

| State label | When used | Required message elements |
| --- | --- | --- |
| **Not yet available** | Any placeholder (baseline) | "Not yet available." |
| **Requires Step 66D** | Delivery Inbox, Delivery Detail, Approvals, DLQ / Retry | "Not yet available. Requires Step 66D." + "No workflow action available." |
| **Requires Step 66C.4** | Clarification Reminder / Expiry / overdue indicators | "Not yet available. Requires Step 66C.4." + "No workflow action available." |
| **Requires Step 66S** | Roles & Permissions, Identity / Session | "Not yet available. Requires Step 66S." |
| **Read-only preview** | A future area that may show real server data but no controls (e.g. the deferred read-only Lifecycle Pipeline, once its contract exists) | "Read-only preview. No workflow action available." + (for pipeline) "Stage is server-derived; it cannot be changed here." |
| **Coming later** | Integrations, Web Research Sources, Approval Policy, external Notification channels | "Coming later." + (for integrations) "Not connected. No external action is available." |

## Presentation rules

1. **Nav item styling.** A placeholder nav item (or placeholder group header) renders in a muted /
   disabled visual style, with a short tag reflecting its state (e.g. `Requires 66D`, `Coming
   later`). It is visibly distinct from an active item.
2. **Destination panel.** Selecting a placeholder opens a panel — not a working page — containing:
   the feature name, the state label, the plain-text message elements from the table above, and
   nothing that can be submitted or triggered.
3. **No fabricated data.** A placeholder must not show invented counts, fake rows, sample
   deliveries, or a mock queue that could be mistaken for real state. Attention badges that would
   depend on 66D/66C.4 data are themselves suppressed (or shown as "—") until those contracts exist.
4. **No affordance leakage.** No disabled-but-visible action button that looks clickable, no form
   fields, no toggles. If there is nothing safe to do, there is nothing that looks like it can be
   done.
5. **Safety reinforcement.** Every 66D/66C.4 placeholder explicitly repeats "No workflow action
   available," reinforcing — at the point of the feature — that nothing here dispatches or resumes a
   workflow or performs a production/external action.
6. **Integrations special case.** The Integrations placeholder must present each connector
   (GitHub / Discord / Slack / Telegram / LLM / web research) as **not connected / disabled**, and
   must not present a "Connect" control that implies external authentication is available in this
   environment.
7. **Read-only preview special case (future pipeline).** If the deferred Lifecycle Pipeline view is
   ever built as a read-only preview, it must state that stage is server-derived and read-only, must
   have no drag handles or column-move affordance, and requires a status-to-column mapping contract
   from Claude Code before it moves past placeholder (`frontend-implementation-boundary.md` §3). It
   is **not** part of the round-1 nav shell.

## Example placeholder copy

Delivery Inbox:

```text
Delivery Inbox
Not yet available. Requires Step 66D.
When available, this is where delivered work will await human acceptance.
No workflow action available.
```

Approvals:

```text
Approvals
Not yet available. Requires Step 66D.
When available, gated actions requiring human approval will appear here for review.
No workflow action available.
```

Clarification Reminder / Expiry:

```text
Reminder / Expiry
Not yet available. Requires Step 66C.4.
Clarification reminder and expiry timing will appear here once the scheduler ships.
No workflow action available.
```

Integrations:

```text
Integrations
Coming later.
GitHub · Discord · Slack · Telegram · LLM provider · Web research — all not connected.
No external action is available.
```

## What placeholders must never do

```text
- Never show an Accept / Reject / Approve / Retry / Replay / Send / Dispatch / Resume control.
- Never show a drag handle or any control implying a workflow-state change.
- Never display fabricated deliveries, approvals, queue items, or counts.
- Never present a "Connect" / "Enable" control for an external integration.
- Never imply that answering, submitting, or clicking will start or resume an agent workflow.
```

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
