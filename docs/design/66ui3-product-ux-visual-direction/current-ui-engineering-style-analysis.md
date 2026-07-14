# Current UI Engineering-Style Analysis — DESIGN-66UI.3

> Owner: Claude Design. A specific, code-cited analysis of *why* the deployed Admin Console reads as
> engineering-style. Every claim points at a real file on `main` @ `51ad83d`.

## Method

Read the deployed source, not the design docs. Files inspected: `styles.css`,
`SafetyStatusBar.tsx`, `Nav.tsx`, `NavGroup.tsx`, `TaskList.tsx`, `TaskDetail.tsx`,
`TaskWorkroom.tsx`, `PlaceholderPanel.tsx`.

## Finding 1 — the UI speaks the database's language

- **`SafetyStatusBar.tsx`** renders a flat row of 12 verbatim backend fields:
  `production_executed_true_count`, `workflow_production_executed_true_count`, `dispatch_enabled`,
  `resume_dispatch_enabled`, `task_api_workflow_dispatch_enabled`,
  `task_workroom_resume_dispatch_enabled`, `github_external_write_enabled`,
  `discord_external_send_enabled`, `llm_external_call_enabled`, `production_delegation_allowed`,
  `approval_required`, `requires_approval` — each printed as `field: value` in muted grey.
- **`TaskDetail.tsx`** renders the **entire raw task object** via
  `<KeyValueTable data={task as ... Record<string, unknown>} />`, then a safety panel of snake_case
  labels (`production_effect`, `requires_approval`, `dispatch_enabled`, `external_actions_enabled`,
  `production_executed`).
- **Effect:** the interface exposes the data model directly. A person reads
  `task_api_workflow_dispatch_enabled: false` where they need "Automated actions: off." This is the
  single strongest engineering signal, and it appears on high-traffic pages.

## Finding 2 — data-grid-first, attention-blind

- **`TaskList.tsx`** is a 10-column table (Title / Type / Status / Priority / Owner-Created by /
  Environment / Production effect / Requires approval / Created / Updated), every column equal
  weight, timestamps raw (`t.created_at`, `t.updated_at`).
- **Effect:** it answers "here are all fields of all tasks," not "which tasks are waiting on me /
  blocked / newly delivered." The user's actual job — triage — is unsupported. This is a ticket-grid
  aesthetic, one of the exact anti-patterns the product is meant to transcend.

## Finding 3 — the Workroom reads like a log viewer

- **`TaskWorkroom.tsx` + `.workroom-message`**: messages are uniform cards (same background, same
  border) with a small grey metadata line; the message type is text, not a visual treatment. Human
  messages, agent messages, system events, and clarification questions are nearly
  indistinguishable at a glance.
- **Effect:** the most important and most differentiating surface — the place a human "works with
  the AI team" — looks like scrolling a plain event log. There is no sense of a conversation, no
  agent presence, no turn-taking, no "the team is waiting on your answer."

## Finding 4 — governance styled as a debug panel

- **Audit evidence** renders as `.workroom-audit-event` muted rows foregrounding `body_hash` and
  `body_length`; **safety** is the raw field bar from Finding 1.
- **Effect:** the governance story — a real strength of the platform — is presented like developer
  diagnostics. Non-technical roles can't parse it; technical roles tune it out as noise. The
  *safety* of the system should read as reassurance ("nothing will run automatically"), not as a
  hash dump.

## Finding 5 — flat, undifferentiated visual field

- **`styles.css` tokens:** `--bg #0f1419`, `--card #1b232b`, `--fg #e6edf3`, `--muted #8b949e`,
  `--line #30363d`. Semantic color (`--b-ok/#56d364`, `--b-warn/#e3b341`, `--b-bad/#ff7b72`) lives
  only inside small `.badge`s. The dominant experience is grey text on near-black with hairline
  borders.
- **Effect:** no visual hierarchy separates "core product" from "supporting ops"; no calm-vs-attention
  contrast tells the eye where to look; nothing feels designed *for a user* rather than *emitted by
  a system*. It is a competent engineer's default theme — which is precisely the feedback.

## Root cause beneath all five — the AI team is invisible

The product's premise is "manage and collaborate with an AI team." Yet in the deployed UI an agent
is only ever a `sender_id` string; there are no agent identities, no team-activity state, no
"working / blocked / waiting on you" signals, no representation that a *team* is doing anything. The
UI describes records; it does not portray a team at work. Fixing the surface styling without adding
this representation would make the app prettier but still not feel like the product it is.

## What is NOT the problem (do not "fix")

- The **7-group IA** (66UI.2) is sound — keep it; this is a visual/interaction problem, not an IA
  problem.
- The **safety semantics** (server-computed, always-off, displayed-as-returned) are correct — the
  problem is *presentation*, not the values or their provenance. Any redesign must keep them
  server-computed and must not hardcode/infer them client-side.
- The **placeholders** are correctly safe — keep the semantics; only the visual polish is open.
- The **plain-text rendering** rule for user/agent content stays; a richer *message treatment* must
  still render bodies as plain text (no markdown-to-HTML, no `dangerouslySetInnerHTML`).

## Which components are too engineering-ish (targets)

| Component / page | Verdict |
| --- | --- |
| `SafetyStatusBar.tsx` | Highest priority — raw 12-field dump on every page |
| `TaskDetail.tsx` `KeyValueTable` dump | Highest priority — literal object dump |
| `TaskWorkroom.tsx` message cards | Highest product upside — log → collaboration |
| `TaskList.tsx` 10-col grid | High — grid → triage list |
| Audit evidence rows | Medium — hashes-first → readable evidence |
| `ExecutiveOverview` KPI cards | Medium — metrics-first → attention-first |
| `PlaceholderPanel.tsx` | Low — safe; light polish only |
| `Nav.tsx`/`NavGroup.tsx` | Low — IA good; visual rhythm polish only |

## Statement

Design analysis only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
