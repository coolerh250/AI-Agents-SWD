# Visual Language Proposal — DESIGN-66UI.3

> Owner: Claude Design. Concrete design-language guidance — not "make it prettier." Builds on the
> real existing tokens in `apps/admin-console/src/styles.css` (dark: `--bg #0f1419`, `--card
> #1b232b`, `--fg #e6edf3`, `--muted #8b949e`, `--line #30363d`; semantic `#56d364` / `#e3b341` /
> `#ff7b72`). Direction-agnostic where possible; notes where a direction changes a choice.

## Layout density

- Move from uniform dense rows to a **two-density system**: comfortable (core product: Overview,
  Team Work, Workroom, Delivery review) and compact (reference/ops: Platform Ops tables, audit
  logs). Today everything is one dense setting.
- Establish a spacing scale (e.g. 4 / 8 / 12 / 16 / 24) and use `gap`-based layout (already the
  norm in `styles.css`) — no ad-hoc margins.
- Constrain reading measures: conversation and prose columns ~60–70ch; wide tables get their own
  `overflow-x:auto` container so the page never scrolls sideways.

## Card style

- Introduce **surface elevation** to encode importance: a slightly lighter/raised surface for
  live/attention content, the current `--card` for standard content, and a flat/quiet surface for
  reference. Today every card is the same `--card` + `--line`, so nothing reads as more important.
- Keep border-radius consistent (the existing 8px). Reserve a left accent stripe **only** for
  genuine state (blocked / decision-needed), not as decoration on every card.

## Status badge style

- Keep the existing semantic mapping (`b-ok` green / `b-warn` amber / `b-bad` red / `b-neutral`
  grey) — it's sound. Improve two things: (1) always pair color with a **text label and/or icon**
  (never color alone — accessibility), (2) give lifecycle status its own calm treatment distinct
  from risk/safety status, so "Development" (a stage) doesn't look like a warning.

## Agent activity presentation (new — the missing premise)

- Give each agent a **stable identity**: a name (Intake / Requirement / Development / QA / DevOps
  Agent), a consistent color/monogram token, and an **activity state** chip (idle / working /
  blocked / waiting-on-human). This is the single most important addition — it makes the "AI team"
  visible. Sourced from existing task/agent-execution data; no new data invented, and states must
  come from the server, not be guessed client-side.
- On the dashboard (Direction A especially): a compact "team activity" strip showing which agents
  are active on what.

## Timeline style

- One shared vertical timeline primitive for Workroom conversation and for audit/activity trails:
  time-ordered, authorship-clear, with quiet connective structure. Distinguish entry kinds by
  treatment (see below), not by raw type strings.

## Workroom message style

- Replace uniform grey cards with **role-differentiated treatments**: human messages, agent
  messages, system events, and clarification questions each get a distinct, consistent visual
  language (alignment / authorship chip / accent), so authorship is legible at a glance.
- Show **agent identity** (name + monogram + state) on agent messages instead of a bare
  `sender_id`.
- Replace the raw metadata line (`message_type · sender_type · sender_id · role · created_at`) with
  a human line ("Requirement Agent · 2 hours ago") and keep the technical detail available on
  hover/expand.
- **Bodies stay plain text** — no markdown-to-HTML, no auto-linking, no `dangerouslySetInnerHTML`.
  Differentiation is in the *container treatment*, never in rendering the body as rich content.

## Clarification card style

- Present a clarification as a **decision request**, not a form: a card that states *which agent is
  asking*, *why the task is blocked without an answer*, the question in plain language, and a clear
  "Answer" affordance. When open and assigned to the viewer, it reads as "The Requirement Agent
  needs your decision to continue."
- Keep Create Clarification and Send Message as clearly separate, differently-weighted actions
  (preserve the hard-won 66C.2-R distinction) — a decision request is visually heavier than a chat
  message.

## Delivery review card style (future 66D — design intent only, placeholder until contract)

- Intended as an **acceptance desk**, not a JSON evidence dump: a delivery card summarizing what was
  produced, its QA/risk state as calm chips, and the human actions (Accept / Reject / Request
  Changes / Re-run QA) as clearly-consequenced buttons. Evidence/artifacts are expandable detail,
  not the headline. **Not built this stage** — remains a compliant placeholder until the 66D
  contract exists.

## Audit evidence treatment

- Lead with **human-readable events** ("Requirement Agent requested a clarification · 10:35"), with
  `body_hash` / `body_length` as secondary, expandable detail — the inverse of today's hashes-first
  rows. Never show raw bodies (unchanged rule). Restricted-role message stays readable, not a blank.

## Empty state tone

- Product-warm and directive, not blank: e.g. Workroom empty → "No messages yet. Start a discussion
  or ask the AI team a question." (the app already has decent empty copy; extend the tone
  consistently). Never a bare "No data."

## Warning / safety tone

- **Reassurance-first, calm, plain-language.** Replace the raw 12-field bar with one posture line:
  "Safe — no automated or production actions will run. Everything is recorded." Detail expands on
  demand. `production_effect=true` becomes a clear but non-alarming inline explanation of what will
  and won't happen, not a yellow slab of jargon. Danger red is reserved for genuine failure/blocked
  states, not for normal "off" safety flags (an *off* dispatch flag is *good* news and should not
  read as red alarm).

## Microcopy tone

- Speak the user's language, name things by what they do:
  - `production_executed_true_count: 0` → "No production actions have run."
  - `dispatch_enabled: false` / `resume_dispatch_enabled: false` → "Automated actions: off."
  - `task_api_workflow_dispatch_enabled` → not user-facing at all (technical detail, on expand).
  - `requires_approval` → "Needs approval before anything runs."
  - Active voice, consequence-explicit ("Answer" → toast "Answer recorded"). Errors say what
    happened and what to do.

## Theme note

- Directions A and B keep the dark ground (it suits an operational product and matches the existing
  app). Direction C is the one that invites a palette/theme revisit (possibly light or dual-theme).
  Any palette change is a Direction-C-scoped decision, not assumed here — no new palette is invented
  in this proposal; it refines and extends the existing token system.

## Statement

Design proposal only. No runtime code. No production action. No Codex implementation authorized.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
