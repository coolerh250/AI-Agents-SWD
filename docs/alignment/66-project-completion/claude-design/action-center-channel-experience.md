# Action Center & Channel Experience — M4 (Step 66ALIGN.1, Claude Design)

> Owner: Claude Design. How Action Center and Notification Center divide responsibility, and how
> external channels stay safely deferred. Analysis only.

## The distinction (the core M4 question)

They are two different things and must not be merged into one confusing feed:

| | **Notification Center** | **Action Center** |
| --- | --- | --- |
| Purpose | a chronological **feed of what happened** | an aggregated **queue of what needs a decision/action from you** |
| Content | informational + actionable events, time-ordered | only items requiring human action, grouped by kind |
| Item lifecycle | read / unread | open / resolved (resolved when the action is taken elsewhere) |
| Example | "Requirement Agent requested a clarification (2h ago)" | "3 decisions waiting · 2 deliveries to review · 1 approval" |
| Relationship | the feed *records* the event | the queue *aggregates the still-open actionable ones* |

Rule of thumb: **Notification Center answers "what happened?"; Action Center answers "what do I need
to do now?"** An item can appear in both (the notification records it; the Action Center keeps it
until acted on), but they are distinct surfaces with distinct states.

## Action Center

- Aggregates real actionable items across the product loop: **decisions waiting** (clarifications),
  **deliveries to review** (M2), **approvals** (M3), **needs-recovery / DLQ** (M3),
  **overdue/expiring** (66C.4). Each links to the surface where the action is actually taken.
- The Overview "Needs your attention" band (shipped in FE.1C) is the **seed** of the Action Center;
  M4 promotes it into a full, cross-surface queue. Until each contributing capability exists, its
  tile is an honest placeholder (no fabricated counts) — exactly as the Overview already does.
- **Never performs the action inline in a way that bypasses the real surface's safety/confirmation**
  — it routes you to the decision, it is not a shortcut around approval/consequence UX.

## Notification Center

- In-app, chronological, read/unread. References the agent/task that raised each event in product
  language (no raw event ids as the headline; ids under "Technical details").
- **In-app only in M4's first version.**

## Channels (external) — deferred and safe

- Slack / Discord / Telegram / email are **external send** — they stay **placeholder/disabled** with
  "not connected" until explicitly authorized (matches the shipped Settings/Integrations
  placeholders and the safety posture). No external action is implied or active before authorization.
- When authorized (later), each channel is opt-in per-connector with clear "connected/disabled"
  state; sending is an explicit, audited action.

## Pages / states / decision points (M4)

- **Pages:** Notification Center (feed); Action Center (queue). Both currently exist only as the
  Overview seed + "Notifications" nav placeholder (badged "Soon").
- **States:** unread/read (notifications); open/resolved (actions); connected/disabled (channels).
- **Empty/error/loading:** "You're all caught up"; "No channels connected"; role-restricted.
- **Human decision points:** act on an Action Center item (routes to the real surface); later,
  connect a channel.

## Agent visibility

Notifications and action items name the agent/task that raised them, reinforcing the team model.

## Product-language & accessibility

"N need your attention"; "You're all caught up"; badges carry text; feed and queue keyboard-navigable;
unread state not conveyed by color alone.

## Product Owner validation (M4)

```text
- In-app notifications work and read as product events, not raw logs.
- Action Center aggregates the real open actions across the loop and routes to each.
- Action Center never bypasses a surface's safety/confirmation.
- External channels are clearly NOT active until explicitly authorized.
```

## What must remain placeholder-only

- **All external channel send** (Slack/Discord/Telegram/email) until explicitly authorized.
- Any Action Center tile whose contributing capability (M2 delivery, M3 approvals/DLQ, 66C.4
  overdue) isn't live yet — honest placeholder, no fabricated count.

## Statement

Design analysis only. No runtime code. No production action. No merge. No Codex authorization.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
