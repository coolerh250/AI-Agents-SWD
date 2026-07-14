# Product UX Review — DESIGN-66UI.3

> Owner: Claude Design. A product-experience review of the **deployed** Admin Console (test
> runtime, `main` @ `51ad83d`) in response to the Product Owner's feedback: "目前 UI / UX 非常工程風格."
> **Review and direction only — no runtime code, no Codex implementation authorized, no backend/API
> change requested.**

## Stage

`66ui3-product-ux-visual-direction` (DESIGN-66UI.3)

## What this review is grounded in

Not a repeat of the design docs — an inspection of the **actual shipped code** now live on the test
runtime: `apps/admin-console/src/styles.css`, `components/SafetyStatusBar.tsx`,
`components/Nav.tsx` + `NavGroup.tsx`, `pages/TaskList.tsx`, `pages/TaskDetail.tsx`,
`pages/TaskWorkroom.tsx`, `components/PlaceholderPanel.tsx`. Every issue below cites a real,
currently-deployed artifact.

## The core question: what product is this?

AI Agents Team Work is a platform where **a human delegates work to, and collaborates with, an AI
team.** The right mental model for the Admin Console is:

```text
An AI Team Command Center wrapping an Agent Workroom —
  the human sees what the AI team is doing, what it is blocked on, what it needs a decision on,
  what it delivered, and what is safe — and drops into a task to work alongside the agents.
```

It is **not** primarily:
- a **DevOps console** — that is the *Platform Ops* surface, which today visually dominates and
  makes the whole product read as ops tooling;
- a **plain task manager / ticket grid** — the Task List today is exactly this;
- a **log viewer** — the Workroom today reads like one;
- a **bare chat app** — the opposite failure mode we must also avoid.

The product should feel like the first line. Today it feels like the middle three. That gap is the
"engineering style" the Product Owner named.

## Why it currently reads as engineering-style (summary)

Full detail in `current-ui-engineering-style-analysis.md`. The five root causes:

1. **Raw backend field names are shown as UI.** `SafetyStatusBar.tsx` prints 12 verbatim fields —
   `production_executed_true_count`, `task_api_workflow_dispatch_enabled`,
   `discord_external_send_enabled`, … — as a flat grey run of `key: value`. `TaskDetail.tsx` renders
   the **entire raw task object** through `KeyValueTable`, then a safety panel of snake_case field
   names (`production_effect`, `requires_approval`, `dispatch_enabled`). The interface speaks the
   database's language, not the user's.
2. **Data-grid-first, not attention-first.** `TaskList.tsx` is a 10-column table (Title, Type,
   Status, Priority, Owner/Created by, Environment, Production effect, Requires approval, Created,
   Updated). It optimizes for field completeness, not for "what needs me right now." Nothing surfaces
   the one thing a user actually opens the app for: *is the AI team waiting on me?*
3. **The Workroom reads like a log, not a collaboration.** Messages are uniform grey cards
   (`.workroom-message`) with a metadata line; human / agent / clarification messages are barely
   differentiated. The single most important, most differentiating surface of the product looks like
   `tail -f`.
4. **Evidence/JSON aesthetic for governance.** Audit evidence renders as muted metadata rows
   (`.workroom-audit-event`) foregrounding `body_hash`, `body_length`. Safety is a raw field dump.
   Governance is present but styled like a debug panel.
5. **A flat, uniformly-muted palette with no hierarchy or product moments.** Almost everything is
   `--muted (#8b949e)` on near-black `--bg (#0f1419)`; semantic color appears only inside small
   badges. There is no visual hierarchy, no calm/attention contrast, no sense that the AI team is a
   presence in the product.

Underlying all five: **there is no representation of the AI team as an actor.** An agent is just
another `sender_id` string; there are no agent identities, no "the team is working / blocked /
waiting on you" states. The product's whole premise is invisible in its UI.

## Required review areas

| # | Area | Deployed state | Product-experience issue | Improvement direction |
| --- | --- | --- | --- | --- |
| 1 | Dashboard / Overview | `ExecutiveOverview` KPI cards (`.grid`/`.card`: uppercase muted key + big number) | Reads as a metrics/ops dashboard; does not answer "what does the AI team need from me?" | Lead with a human-action summary: decisions waiting, deliveries to review, blocked tasks — then metrics. |
| 2 | Navigation / IA shell | 7 grouped collapsible groups (shipped 66UI.2) | Structurally good; visually still plain card-chips, all same weight, no active-context sense | Visual polish: group rhythm, active state, quiet Platform Ops; keep the IA. |
| 3 | Task List | 10-column dense grid | Attention-blind; every column equal weight; raw timestamps | Triage-first list: status + "waiting on you" + last activity foregrounded; details on demand. |
| 4 | Create Task | `.task-form` vertical stack of muted labels incl. `production_effect` checkbox | Reads as a DB insert form; `production_effect` is jargon; safety warning is a yellow slab | Delegation framing ("Assign work to the AI team"); plain-language fields; safety as calm inline guidance. |
| 5 | Task Detail | `KeyValueTable` dump of the whole task object + raw safety-panel | Raw object dump is the definition of engineering-style | Summarize as a task header (title, stage, owner, what's next); safety as a compact posture chip; drop the raw dump. |
| 6 | Workroom | `.workroom-message` uniform grey cards + metadata line | Log-viewer feel; human/agent/clarification not visually distinct; no agent presence | The product's core: distinct human/agent/system/clarification treatments, agent identity, a clear "waiting on you" state. |
| 7 | Clarification | Rendered as a message-typed card + `open` badge; create/answer are bare `<textarea>`s | Looks like a form field, not "an AI agent is asking you to decide" | A decision-request card: who's asking, why it's blocking, the question, a clear answer affordance. |
| 8 | Delivery placeholders | `PlaceholderPanel` dashed box, 3-line text | Correct and safe; just visually spartan | Keep the safety semantics; give the future acceptance-desk concept a legible "coming in 66D" shape. |
| 9 | Operator Center | Separate pages (Operator Console, Incidents, Agent Executions) + 66D placeholders | Fine for operators; not the problem area | Leave mostly as-is; light consistency pass. |
| 10 | Governance / Safety / Audit | `SafetyStatusBar` raw 12-field bar; audit = muted metadata rows | Raw field dump; competes visually; debug-panel aesthetic | Calm, legible posture ("Safe: no automated actions will run") with details on demand; audit as readable evidence, not hashes-first. |
| 11 | Platform Ops | 20 real DevOps pages, collapsed group | Visually dominates the product's identity when expanded; makes the whole app feel like ops | Keep it; keep it quiet and clearly secondary — it must not define the product's feel. |
| 12 | Settings placeholders | Placeholder pages (66S / later) | Fine and safe | Keep; ensure consistent placeholder treatment. |

## Highest-impact improvement areas (ranked)

1. **Workroom** — the core differentiator, currently the most log-like. Biggest product upside.
2. **Safety/Governance presentation** — the rawest field-dump; a calm posture indicator would
   remove the single strongest "engineering" signal that's visible on *every* page.
3. **Task List + Dashboard "attention" framing** — turn completeness-grids into "what needs me."
4. **Clarification as a decision request** — small surface, high symbolic value for the "AI team
   asks the human" premise.
5. **Language pass** — replace raw field names with product language across all of the above.

## Product experience risks if unaddressed

- Users read the product as internal DevOps tooling and never perceive the "AI team" value.
- The Workroom's log aesthetic makes human-agent collaboration feel like reading output, not
  working with a team — undercutting the core pitch.
- Raw safety/audit fields either intimidate non-technical roles or get ignored as noise, weakening
  the governance story the platform is built on.

## Scope note / conflict surfaced in preflight

The deployed baseline has **Delivery Package under Platform Ops** (PO-validated VISIBLE at FE.1).
This contradicts the earlier 66UI.2 "decision #2" (move to Deliveries) that exists only on the
**unmerged PR #2** branch. This review uses the deployed reality (Platform Ops) as baseline. The
PR #2 divergence is flagged for reconciliation in `product-owner-discussion-guide.md` — it is a nav
sub-item, not a visual-direction blocker.

## Statement

Design review only. No runtime code. No production action. No API/contract decision. No Codex
implementation authorized by this document.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
