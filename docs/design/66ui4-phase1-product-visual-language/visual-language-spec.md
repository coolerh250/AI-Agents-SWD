# Visual Language Spec — DESIGN-66UI.4 Phase 1

> Owner: Claude Design. Concrete design-language system refining the **existing** dark tokens in
> `apps/admin-console/src/styles.css`. Additive/refinement — no new palette, no theme change.

## Existing tokens (baseline — keep)

```css
--bg: #0f1419;   --card: #1b232b;   --fg: #e6edf3;   --muted: #8b949e;   --line: #30363d;
/* semantic (currently only inside .badge): */
b-ok #56d364 · b-warn #e3b341 · b-bad #ff7b72 · b-neutral #adbac7
/* accent: link #58a6ff · active border #388bfd */
```

## 1. Surface elevation (new — encodes importance)

Today every card is the same `--card`+`--line`, so nothing reads as more important. Introduce three
surface levels as tokens:

```css
--surface-raised: #202b35;   /* live / attention content (decisions waiting, blocked, active agent) */
--surface-base:   #1b232b;   /* = existing --card; standard content */
--surface-quiet:  #161d24;   /* reference / secondary (Platform Ops tables, collapsed groups) */
```

Rule: elevation communicates "look here first." Reserve `--surface-raised` for genuinely
attention-worthy content; do not raise everything (that would flatten the signal again).

## 2. Density system (two settings)

- **Comfortable** (core product: Overview, Team Work, Workroom, Delivery review): row height and
  padding ~1.5× current; generous `gap`.
- **Compact** (reference/ops: Platform Ops tables, audit logs): approximately today's density.
- Spacing scale (use consistently, `gap`-based): `4 · 8 · 12 · 16 · 24 · 32`.

## 3. Typography scale

Keep the existing `system-ui, -apple-system, "Segoe UI", Roboto` stack (no webfont). Define a scale
and stay on it:

```text
display  20px / 600   — page title / dashboard headline
h2       15px / 600   — section (existing)
h3       13px / 600   — subsection
body     13px / 400   — default
label    12px / 600 / +0.04em uppercase — keys, eyebrows (use sparingly, NOT for raw field names)
caption  11px / 400   — timestamps, secondary metadata
```

Headings get `text-wrap: balance`; numeric columns get `font-variant-numeric: tabular-nums`.

## 4. Color usage — separate LIFECYCLE from SAFETY/RISK

The biggest color problem today: a lifecycle status and a risk flag use the same badge palette, so
"Development" (a normal stage) can read like a warning, and an *off* safety flag (good news) can read
like an alarm.

- **Lifecycle status** (draft / intake / development / qa / delivery / done): a **calm, neutral-to-
  accent** family (e.g. muted blue/grey tones + one "active" accent). Never red/amber for a normal
  stage.
- **Safety / risk state**: semantic family — but with corrected polarity:
  - "Automated actions: off", "No production actions", "Fully audited" → **calm/positive** treatment
    (this is *reassurance*, not danger). An *off* dispatch flag must NOT be red.
  - amber `--b-warn` → genuine "needs your attention" (approval required, clarification open).
  - red `--b-bad` → genuine failure / blocked / rejected only.
- Accent `#58a6ff` stays for interactive/links; it is **not** a status color.

## 5. Badges & chips

- Keep the shape; always pair color with **text and/or icon** (never color alone — accessibility).
- Lifecycle chip, safety chip, and risk chip are visually distinct families (per §4).
- Agent identity chip (introduced for later phases, defined here for consistency): agent name +
  monogram + a small activity dot (idle / working / blocked / waiting-on-human). States come from
  server data; never invented client-side.

## 6. Cards & attention

- Standard content: `--surface-base` + `--line`, radius 8px (existing).
- Attention content: `--surface-raised`, optional 3px left accent stripe **only** for
  decision-needed / blocked (not decorative).
- Reference content: `--surface-quiet`, hairline border.

## 7. Empty / loading / error tone

- Loading: skeletons, no layout shift (existing `.empty`/`.error` refined toward product-warm copy —
  see `product-microcopy-guide.md`).
- Empty: directive and warm ("No messages yet. Start a discussion or ask the AI team a question.").
- Error: what happened + what to do; never a bare code.

## 8. Accessibility

- Contrast: verify all text meets AA on the dark ground (the existing `--muted #8b949e` on
  `--bg #0f1419` is borderline for small text — Phase 1 should nudge muted text slightly lighter
  where it carries meaning, or enlarge it).
- Visible keyboard focus on every interactive element (accent outline).
- State never by color alone; icons carry text alternatives.
- `prefers-reduced-motion`: no non-essential motion.

## 9. What stays exactly the same

- The dark ground and the existing hues (refined, not replaced).
- The 7-group IA and all routes.
- Plain-text rendering of user/agent content.
- Server-computed safety values.

## Statement

Design specification only. No runtime code. No production action.

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
