# Overview Dashboard Spec — DESIGN-66UI.4 Phase 1

> Owner: Claude Design. Attention-first Overview, applying Direction A (command-center framing) +
> Direction C (plain language, calm). Reuses/extends the existing `ExecutiveOverview.tsx` +
> `/operations/admin-console/overview` data. No new endpoint.

## Problem (deployed today)

`ExecutiveOverview` is a grid of KPI cards (uppercase muted key + big number). It answers "here are
platform metrics," not the question a user actually opens the app to answer: **"what does the AI
team need from me, and where is it blocked?"**

## Design: three stacked bands, attention-first

### Band 1 — "Needs you" (the reason to open the app)

A row of large, plain-language action tiles. Each is a **queue** (click → filtered list), not a raw
metric:

```text
┌─ Decisions waiting ─┐ ┌─ Deliveries to review ┐ ┌─ Blocked tasks ┐ ┌─ Approvals ┐
│  3                   │ │  2                     │ │  1              │ │  0          │
│  agents waiting on   │ │  ready for your        │ │  waiting on an  │ │  none need  │
│  your answer         │ │  acceptance            │ │  input          │ │  approval   │
└──────────────────────┘ └────────────────────────┘ └─────────────────┘ └────────────┘
```

- Tiles with a non-zero, action-needed count use `--surface-raised` (attention); zero/clear tiles
  stay calm/quiet — the eye is drawn only to what needs action.
- **Data dependency honesty:** counts that depend on not-yet-built stages must not be fabricated.
  - "Decisions waiting" (clarifications) — from existing task/clarification data where available.
  - "Deliveries to review" — **placeholder until Step 66D**; show "—" with a "Requires Step 66D"
    caption, not a fake number.
  - "Blocked tasks" — from existing task status where available.
  - "Approvals" — **placeholder until Step 66D**; same honest-placeholder treatment.
  - Any tile without a real backing value shows a labeled placeholder, never invented data.

### Band 2 — AI team activity + safety posture

- **Team activity strip** (Direction A): which agents are active and on what, using agent identity
  chips (Intake / Requirement / Development / QA / DevOps + activity state). Sourced from existing
  agent-execution data; states server-derived. Where live activity data isn't available yet, show a
  calm "No active agent runs" rather than empty space.
- **Calm safety posture** (from `calm-safety-posture-spec.md`) shown here as a compact reassurance
  card, not the raw field bar.

### Band 3 — Metrics (kept, demoted)

The existing platform metrics (throughput, counts, health) remain — but **below** the action and
activity bands, in comfortable-but-secondary cards. They inform; they no longer lead.

## Language

All tile and card copy in product language (see `product-microcopy-guide.md`): "Decisions waiting,"
"Deliveries to review," "Blocked tasks," "All systems safe" — never raw field names or
`snake_case`.

## Role-awareness

- The default Overview is the same for all roles; role-based landing (66UI.2) still routes some roles
  elsewhere (e.g. Agent Operator → Operator Center). The Overview itself does not gate content
  client-side; server-side RBAC governs what data returns.

## What stays the same

- The `/operations/admin-console/overview` endpoint and its data — no new endpoint; this is a
  presentation/composition change over existing data plus honest placeholders for 66D-gated counts.
- No safety value inferred client-side.

## Accessibility

- Tiles are real links/buttons with visible focus; counts paired with descriptive text (not a bare
  number); attention conveyed by treatment + label, not color alone.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
