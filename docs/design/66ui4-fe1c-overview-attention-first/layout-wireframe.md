# Overview Layout Wireframe — DESIGN-66UI.4-FE.1C

> Owner: Claude Design. ASCII wireframe of the attention-first Overview. Structure/intent only —
> not pixel spec, not code. Uses the deployed FE.1A visual language; introduces no new tokens.

## Desktop

```text
┌───────────────────────────────────────────────────────────────────────────┐
│ Overview                                                                    │
│ See what your AI team needs from you and where work stands.                 │
├───────────────────────────────────────────────────────────────────────────┤
│ NEEDS YOUR ATTENTION                                                        │
│ ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐          │
│ │ Decisions waiting │ │ Blocked tasks     │ │ Deliveries to     │          │
│ │        2          │ │        1          │ │ review            │          │
│ │ agents waiting on │ │ waiting on an     │ │  — Not yet avail. │          │
│ │ your answer   →   │ │ input         →   │ │  Requires 66D     │          │
│ └───────────────────┘ └───────────────────┘ └───────────────────┘          │
│ (raised surface only when count>0; placeholder tile is muted/dashed)        │
├───────────────────────────────────────────────────────────────────────────┤
│ AI TEAM ACTIVITY                                                            │
│ ┌─────────────────────────────────────────────────────────────────────┐   │
│ │ Recent agent runs (from existing agent-executions):                   │   │
│ │  • Requirement Agent — completed · <relative time>                    │   │
│ │  • Development Agent — running · <relative time>                       │   │
│ │ (product-readable status; empty → "No recent agent runs.")            │   │
│ └─────────────────────────────────────────────────────────────────────┘   │
├───────────────────────────────────────────────────────────────────────────┤
│ CURRENT WORK                                                                │
│ ┌─────────────────────────────────────────────────────────────────────┐   │
│ │ Recently updated tasks (from existing /tasks):                        │   │
│ │  • Build SaaS User Management Module — Clarification needed · 2h ago →│   │
│ │  • <task title> — Development · 5h ago                              → │   │
│ │ (title · product-readable status · relative time; link to task)       │   │
│ └─────────────────────────────────────────────────────────────────────┘   │
├───────────────────────────────────────────────────────────────────────────┤
│ SYSTEM POSTURE                                                              │
│  🛡 Safe — no automated or production actions will run.   View Safety →     │
│  (reuses FE.1B posture summary; does NOT duplicate its detail)              │
├───────────────────────────────────────────────────────────────────────────┤
│ ▸ Platform & delivery metrics  (secondary; collapsed or below the fold)     │
│   [Active projects] [Delivery packages] [Ready for review] [Latest pilot]   │
│   [Latest package] [Acceptance gate] [Human acceptance] [Safety]            │
│   [Production executed] [Full regression] [Ready for admin console]         │
│   [Backup gaps]        ← the existing 12 getOverview() cards, demoted       │
├───────────────────────────────────────────────────────────────────────────┤
│ FUTURE CAPABILITIES                                                         │
│  • Delivery Review — Not yet available. Requires Step 66D.                  │
│  • Reminder / Expiry — Not yet available. Requires Step 66C.4.              │
│  • Notifications / Action Center — Future.                                  │
│  • Pipeline view — Future (read-only only; no drag/drop).                   │
│  Each: "No workflow action available from this screen."                     │
└───────────────────────────────────────────────────────────────────────────┘
```

## Tablet / mobile

- Attention tiles stack vertically; sections keep the same top-to-bottom priority order.
- "Platform & delivery metrics" collapses by default on small screens (it is secondary).
- Safety posture summary stays visible near the top of the content on all widths.

## Interaction

- Attention tiles with a real count are links to the relevant filtered list (e.g. Decisions waiting
  → Tasks filtered to clarification-needed). Placeholder tiles are **not** links and expose **no**
  control.
- "View Safety →" links to the Governance / Safety Center page.
- Current-work rows link to the task. No mutation, dispatch, resume, or approval control anywhere on
  the Overview.

## Accessibility

- Every tile/row is a real link/button with visible focus; counts paired with descriptive text;
  attention conveyed by surface + label (not color alone); respects `prefers-reduced-motion`.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
