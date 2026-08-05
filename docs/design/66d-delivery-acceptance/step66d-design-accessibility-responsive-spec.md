# Step 66D-DESIGN — Accessibility and Responsive Specification (FROZEN)

> **Design specification only. No implementation. `production_executed_true_count: 0`.**

```text
CANONICAL_BASELINE: main 9c5210d190b82b76575ba8d456b5d2005c2867d2
POSTURE:            Desktop-first; responsive down to tablet; mobile observation only
BREAKPOINT COUNT:   4 (measured: manifest breakpoints list)
```

## 1. Breakpoints (frozen)

| Breakpoint | Target | Control Center | Delivery Inbox | Delivery Review (write-heavy) |
| --- | --- | --- | --- | --- |
| 1440px | desktop | full two-column sections | full table | fully supported |
| 1280px | laptop | full, tighter gutters | full table | fully supported |
| 1024px | compact / tablet landscape | stacked sections, lifecycle scrolls horizontally with labels retained | reduced columns (Project, Version, Status, Due, CTA) | supported with stacked panels |
| 768px | tablet portrait | fully stacked | stacked cards | supported with stacked panels; confirmation dialogs full-width |
| < 768px | small mobile | read-only summary | read-only list | **read-only**; write actions replaced by an explicit unsupported-action message |

Frozen rule: **status, blocking reason and decision history are never hidden at any breakpoint.**
Reducing columns is allowed; removing a blocking reason, a status, or decision history is not. On
small mobile, the write region renders:

```text
Recording a review action or a final decision is not supported on this screen size.
Open this review on a larger screen to continue.
```

This is an explicit message, never a silently disabled or hidden control.

## 2. Keyboard and focus (frozen)

```text
keyboard navigation      every action, filter, sort, tab, anchor, row CTA and dialog control is
                         reachable and operable by keyboard alone
logical focus order      DOM order matches visual order per section; section anchors move focus to
                         the section heading (not just scroll)
visible focus state      always visible; never removed; uses the existing Admin Console focus token
minimum target size      >= 24x24 CSS px with adequate spacing for all interactive controls
skip affordance          a skip link to the main region and to "Needs attention"
```

A keyboard-only user must be able to complete every legal review flow end to end (acceptance
criterion AC-15 in the frontend handoff).

## 3. Semantics and assistive technology (frozen)

```text
semantic headings        one h1 per page; sections use h2; panels h3 - no level skipping
landmarks                banner / navigation / main / complementary used once each as appropriate
accessible tables        Inbox and traceability use real table semantics with a caption, scoped
                         headers, and sort state exposed via aria-sort
form labels              every control has a programmatically associated visible label; placeholder
                         text is never the only label
error association        each field error is associated with its control (aria-describedby) and the
                         form exposes an error summary that links to each invalid field
status announcements     freshness changes, refresh completion, conflict detection and submit
                         results are announced via a polite live region; a blocking conflict uses an
                         assertive announcement
non-color status         every status / severity / blocking / freshness / evidence-health value is
                         conveyed by text + icon in addition to color
icons                    decorative icons are hidden from AT; meaningful icons carry text
                         alternatives
reduced motion           prefers-reduced-motion honored; no essential information conveyed only by
                         motion; skeleton loaders remain static under reduced motion
```

## 4. Dialog / confirmation behavior (frozen)

Applies to the ACCEPT / REJECT / REQUEST_CHANGES / RERUN_QA / ESCALATE / ARCHIVE confirmations and
the conflict-recovery dialog:

```text
role=dialog with aria-modal, an accessible name, and a description
focus trap correct       focus moves into the dialog on open and cycles only within it
cancellable             Escape and an explicit Cancel both close without submitting
focus return            on close, focus returns to the control that opened it
first-error focus       on validation failure, focus moves to the first invalid field
no tooltip-only rules   any rule that changes what a user may do (blocking follow-up, QA rerun
                        limit, expiry, identity not verified) is stated in visible body text, never
                        only in a tooltip or title attribute
```

## 5. Specific accessibility rules for this domain

```text
Review Gate Action vs Product Owner Decision are two separate, separately-labelled regions with
  distinct headings, so a screen-reader user hears them as two different things (66D-D01).
Disabled actions expose their reason in text (e.g. "QA rerun limit reached", "expired",
  "identity not verified") - not only as a visual disabled state.
The QA rerun quota ("1 of 1 used") is text, announced, and never conveyed only by a disabled
  button appearance.
UNKNOWN / MISSING / STALE evidence health is announced as such - never rendered as PASS, healthy,
  or zero for AT users.
`production_executed_true_count = 0` is exposed as read-only text with an accessible name; no
  interactive control can alter it.
Decision history, including superseded decisions, remains in the accessible reading order at every
  breakpoint.
```

## 6. Contrast and visual tokens

Reuse the existing Admin Console tokens (`apps/admin-console/src/styles.css`). Requirements:

```text
text and meaningful non-text contrast meet the established Admin Console accessibility baseline
status colors are paired with a text label in every instance
no new palette is introduced by this stage
```

---
_Non-production only. No production action. No production data. Do not include internal IP
addresses, SSH aliases, private hostnames, real tokens, credentials, private URLs, or environment
secrets — use neutral labels such as "test host", "internal test runtime", "admin console local
tunnel", "sandbox repo"._

<!-- staging-safety: staging-only=false non-production=true production-action=false production-deploy=false production-sync=false production-secret=false external-write=false github-merge=false image-push=false production-ready=false credential-storage=false public-exposure=false live-integrations=disabled -->
