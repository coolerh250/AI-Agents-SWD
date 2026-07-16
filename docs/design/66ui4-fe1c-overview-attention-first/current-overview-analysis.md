# Current Overview Analysis — DESIGN-66UI.4-FE.1C

> Owner: Claude Design. What the deployed Overview (`ExecutiveOverview.tsx`, `main` @ `77ab4e0`)
> actually is today, and why it reads as engineering-style. Grounded in the real component + its data
> source.

## What is deployed today

`ExecutiveOverview.tsx` renders a single `<h2>Executive Overview</h2>` and a flat `.grid` of **12
`DataCard`s**, each a label + a value/`StatusBadge`, from one call: `getOverview()` →
`GET /operations/admin-console/overview`. The 12 cards:

```text
Active projects · Delivery packages · Ready for review · Latest pilot · Latest package ·
Acceptance gate · Human acceptance · Safety · Production executed · Full regression ·
Ready for admin console · Backup gaps
```

Footer: "Operator actions are disabled in Admin Console v0."

## Why it reads engineering-style

1. **It is a flat metrics grid.** 12 equally-weighted cards, no hierarchy, no notion of "what needs
   me." It answers "here are platform numbers," not "what should I do."
2. **It is delivery-pipeline/ops oriented, not AI-team oriented.** Every card is about the legacy
   platform delivery model (projects, packages, regression, backup gaps) — none represents the AI
   team, tasks, clarifications, or human decisions. The product's premise is absent from its home
   page.
3. **Labels are product-ish but values are raw.** `production_executed_true_count` shown as a bare
   badge; "Backup gaps" as a raw number; statuses are backend enum values via `StatusBadge`.
4. **No attention, no activity, no recency, no next-step guidance.** Nothing is foregrounded;
   nothing tells the user where the AI team is blocked or what changed.

## What is genuinely fine (keep / reuse)

- The single `getOverview()` call and its 12 fields are real, working data — **reused**, just
  demoted to a secondary "Platform & delivery metrics" section (metrics demotion, not deletion).
- `DataCard`, `StatusBadge`, the FE.1A visual tokens — reused as-is.
- The read-only, no-operator-actions posture — unchanged.

## The gap FE.1C fills

The Overview has no "AI Team Command Center" layer: no attention queue, no AI-team activity, no
recent task movement, no calm posture summary, no next-step. FE.1C adds those **from existing data**
(tasks list, agent executions, overview fields, FE.1B posture) and demotes the current 12-card grid
beneath them. It does **not** invent metrics or add backend.

## Important distinction to avoid conflation

The overview field `ready_for_review_packages_count` is the **legacy delivery-package** model
(Category H / Step 57–65), **not** the Step 66D task-linked "Deliveries to review." FE.1C must not
present the legacy package count as if it were the (not-yet-built) 66D delivery-review queue. The
legacy count stays in the demoted metrics section labelled as delivery *packages*; the 66D
"Deliveries to review" attention item is an honest **placeholder**. See `existing-data-mapping.md`.

## Statement

Design analysis only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
